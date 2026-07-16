"""Shopping Copilot gRPC server (TF1-59).

Implements ``ShoppingCopilotService.ChatWithCopilot`` on ``:50051`` (spec §1).
Envoy (frontend-proxy) routes gRPC-Web storefront requests here.

State owned by the server (not the agent):
- **Session history** keyed by ``session_id`` — the server loads context; the
  client never sends chat history (proto field 3 is deprecated to close a
  prompt-injection vector).
- **Pending-confirmation store** keyed by ``confirmation_token`` — the two-phase
  confirmation gate. Turn 1: agent asks to add to cart → server stashes the
  action + returns a token, executing nothing. Turn 2: client re-sends the token
  → server executes the real ``CartService.AddItem``, bypassing the LLM.

ponytail: both stores are in-memory dicts — correct for a single replica. Move
to Valkey (keyed by session_id / token) if the deployment scales past one pod.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from concurrent import futures

import boto3
import grpc

import agent
import tools
from guardrails import sanitize_text, detect_prompt_injection_llm   # MANDATE-06: L1 / L2 input guardrail
import shopping_copilot_pb2 as pb
import shopping_copilot_pb2_grpc as pb_grpc

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("shopping-copilot")

PORT = os.environ.get("SHOPPING_COPILOT_PORT", "50051")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
MAIN_MODEL = os.environ.get("LLM_COPILOT_MODEL", "amazon.nova-pro-v1:0")
MAX_WORKERS = int(os.environ.get("COPILOT_MAX_WORKERS", "10"))
CONFIRM_TTL_SECONDS = int(os.environ.get("COPILOT_CONFIRM_TTL", "300"))
# Keep session context bounded — most recent turns only (context engineering, L4).
MAX_SESSION_MESSAGES = int(os.environ.get("COPILOT_MAX_SESSION_MESSAGES", "20"))


class _PendingStore:
    """token -> (user_id, product_id, quantity, expires_at). In-memory, TTL'd."""

    def __init__(self, ttl: int):
        self._ttl = ttl
        self._data: dict[str, dict] = {}

    def put(self, user_id: str, product_id: str, quantity: int) -> tuple[str, int]:
        token = uuid.uuid4().hex
        expires_at = int(time.time()) + self._ttl
        self._data[token] = {"user_id": user_id, "product_id": product_id,
                             "quantity": quantity, "expires_at": expires_at}
        return token, expires_at

    def take(self, token: str) -> dict | None:
        """Pop a pending action if present and unexpired (single-use)."""
        entry = self._data.pop(token, None)
        if entry is None or entry["expires_at"] < time.time():
            return None
        return entry


class ShoppingCopilotServicer(pb_grpc.ShoppingCopilotServiceServicer):
    def __init__(self, bedrock_client):
        self._bedrock = bedrock_client
        self._sessions: dict[str, list] = {}
        self._pending = _PendingStore(CONFIRM_TTL_SECONDS)

    def ChatWithCopilot(self, request, context):
        # --- Phase 2: user approved a pending write -> execute it, skip the LLM.
        if request.confirmation_token:
            return self._execute_confirmed(request)

        # --- Phase 1: normal agent turn.
        session = self._sessions.setdefault(request.session_id or request.user_id, [])
        # MANDATE-06 L1 Input Guardrail: chặn injection + lọc PII trước khi vào LLM.
        sanitized_question = sanitize_text(request.question)

        import model_router
        # MANDATE-06 L2 Input Guardrail: Bedrock LLM-judge bắt paraphrase/reorder mà L1 regex miss.
        # Tái dùng self._bedrock đã có sẵn — không thêm model/dependency mới.
        if model_router.check_feature_flag("llmGuardrailLlmJudge") and detect_prompt_injection_llm(self._bedrock, sanitized_question):
            logger.warning("[Guardrail L2] LLM-judge flagged user input for session=%s", request.session_id or request.user_id)
            sanitized_question = "[filtered]"

        session.append({"role": "user", "content": [{"text": sanitized_question}]})

        routed_model = model_router.get_routed_model("copilot", MAIN_MODEL)
        logger.info(f"Routed model for copilot: {routed_model}")

        result = agent.run_agent(self._bedrock, routed_model, session, request.user_id)

        session.append({"role": "assistant", "content": [{"text": result.text}]})
        # Bound the stored context so old turns don't crowd the window.
        if len(session) > MAX_SESSION_MESSAGES:
            del session[:-MAX_SESSION_MESSAGES]

        resp = pb.ChatWithCopilotResponse(response=result.text, degraded=result.degraded)
        resp.actions_taken.extend(_to_records(result.actions_taken))
        if result.pending is not None:
            token, expires_at = self._pending.put(
                request.user_id,
                result.pending.arguments["product_id"],
                result.pending.arguments["quantity"],
            )
            resp.pending_confirmation.CopyFrom(pb.PendingConfirmation(
                tool_name=result.pending.tool_name,
                arguments_json=json.dumps(result.pending.arguments),
                human_prompt=result.pending.human_prompt,
                confirmation_token=token,
                expires_at_unix=expires_at,
            ))
        return resp

    def _execute_confirmed(self, request):
        entry = self._pending.take(request.confirmation_token)
        if entry is None:
            return pb.ChatWithCopilotResponse(
                response="Xác nhận đã hết hạn hoặc không hợp lệ. Vui lòng thử thêm lại.")
        started = time.time()
        out = tools.execute_add_item(entry["user_id"], entry["product_id"], entry["quantity"])
        ok = '"error"' not in out
        args_json = json.dumps({"product_id": entry["product_id"], "quantity": entry["quantity"]})
        logger.info("audit confirmed-write tool=add_item_to_cart args=%s ok=%s", args_json, ok)
        resp = pb.ChatWithCopilotResponse(
            response=(f"✅ Đã thêm {entry['quantity']}x {entry['product_id']} vào giỏ hàng."
                      if ok else "❌ Không thể thêm vào giỏ. Vui lòng thử lại."))
        resp.actions_taken.append(pb.ToolCallRecord(
            tool_name="add_item_to_cart",
            arguments_json=args_json,
            succeeded=ok,
            started_at_unix=int(started),
            duration_ms=int((time.time() - started) * 1000),
        ))
        return resp


def _to_records(actions: list[agent.ToolCall]) -> list:
    return [pb.ToolCallRecord(
        tool_name=a.tool_name, arguments_json=a.arguments_json, succeeded=a.succeeded,
        started_at_unix=a.started_at_unix, duration_ms=a.duration_ms) for a in actions]


def serve():
    bedrock = boto3.client("bedrock-runtime", region_name=AWS_REGION)
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=MAX_WORKERS))
    pb_grpc.add_ShoppingCopilotServiceServicer_to_server(
        ShoppingCopilotServicer(bedrock), server)
    server.add_insecure_port(f"[::]:{PORT}")
    
    import signal
    def handle_sigterm(signum, frame):
        logger.info("Received SIGTERM, initiating graceful shutdown...")
        server.stop(grace=10)

    signal.signal(signal.SIGTERM, handle_sigterm)
    signal.signal(signal.SIGINT, handle_sigterm)

    server.start()
    logger.info("Shopping Copilot gRPC server listening on :%s (model=%s)", PORT, MAIN_MODEL)
    server.wait_for_termination()
    logger.info("Server stopped.")


if __name__ == "__main__":
    serve()
