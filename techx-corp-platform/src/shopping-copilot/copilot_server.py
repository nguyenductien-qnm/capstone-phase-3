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
import hashlib
import redis
import os
import time
import uuid
from concurrent import futures

import grpc
from grpc_health.v1 import health, health_pb2, health_pb2_grpc
from opentelemetry import trace

import agent
import tools
from botocore.config import Config
from bedrock_client import create_bedrock_runtime_client
from guardrails import apply_guardrail_input, redact_pii
import model_router
import shopping_copilot_pb2 as pb
import shopping_copilot_pb2_grpc as pb_grpc
import demo_pb2
from memory import extract_user_preferences, save_user_memory, load_user_memory, format_memory_for_prompt, fetch_catalog_fingerprint, get_semantic_cache, insert_semantic_cache

tracer = trace.get_tracer_provider().get_tracer("shopping-copilot")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("shopping-copilot")

PORT = os.environ.get("SHOPPING_COPILOT_PORT", "50051")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
MAIN_MODEL = os.environ.get(
    "LLM_COPILOT_MODEL",
    os.environ.get("LLM_COPILOT_MAIN_MODEL", "amazon.nova-pro-v1:0"),
)
MAX_WORKERS = int(os.environ.get("COPILOT_MAX_WORKERS", "10"))
CONFIRM_TTL_SECONDS = int(os.environ.get("COPILOT_CONFIRM_TTL", "300"))
# Keep session context bounded — most recent turns only (context engineering, L4).
MAX_SESSION_MESSAGES = int(os.environ.get("COPILOT_MAX_SESSION_MESSAGES", "20"))
COPILOT_CACHE_TTL = int(os.environ.get("COPILOT_CACHE_TTL", "3600"))
SESSION_TTL = int(os.environ.get("COPILOT_SESSION_TTL", "3600"))
SEMANTIC_CACHE_MIN_SIM = float(os.environ.get("SEMANTIC_CACHE_MIN_SIM", "0.93"))


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
    def __init__(self, bedrock_client, valkey_client):
        self._bedrock = bedrock_client
        self._valkey = valkey_client
        self._sessions_fallback: dict[str, list] = {}
        self._pending = _PendingStore(CONFIRM_TTL_SECONDS)

    def _get_session(self, session_id: str, user_id: str) -> list:
        if self._valkey:
            try:
                val = self._valkey.get(f"copilot:session:{session_id}")
                if val:
                    data = json.loads(val)
                    if data.get("owner_user_id") == user_id:
                        return data.get("messages", [])
            except Exception as e:
                logger.error("Valkey get session failed: %s", e)
        return self._sessions_fallback.get(session_id, [])

    def _save_session(self, session_id: str, user_id: str, messages: list):
        if len(messages) > MAX_SESSION_MESSAGES:
            messages = messages[-MAX_SESSION_MESSAGES:]
        if self._valkey:
            try:
                data = json.dumps({"owner_user_id": user_id, "messages": messages})
                self._valkey.setex(f"copilot:session:{session_id}", SESSION_TTL, data)
                return
            except Exception as e:
                logger.error("Valkey set session failed: %s", e)
        self._sessions_fallback[session_id] = messages

    def ChatWithCopilot(self, request, context):
        # --- Phase 2: user approved a pending write -> execute it, skip the LLM.
        if request.confirmation_token:
            return self._execute_confirmed(request)

        # --- Phase 1: normal agent turn.
        session_id = request.session_id or request.user_id
        session = self._get_session(session_id, request.user_id)
        
        trace_steps = []
        
        # MANDATE-06: Unified Input Guardrail
        start_in = time.time()
        with tracer.start_as_current_span("guardrail_input") as input_span:
            blocked, sanitized_question = apply_guardrail_input(self._bedrock, request.question)
            input_span.set_attribute("guardrail.blocked", blocked)
        lat_in = int((time.time() - start_in) * 1000)
        trace_steps.append(demo_pb2.TraceStep(
            step_name="Input Guardrail (PII/Prompt Guard)",
            latency_ms=lat_in,
            status="blocked" if blocked else "pass",
            detail=redact_pii(json.dumps({"question": request.question, "blocked": blocked}))
        ))
        if blocked:
            logger.warning("[Guardrail] Blocked input for session=%s", session_id)
            # Trả kèm trace_id + trace_steps: đây chính là nhánh cần bằng chứng nhất
            # (MANDATE-14 chấm quyết định chặn bằng span guardrail.blocked). Bỏ trống
            # trace_id thì eval buộc phải đoán qua chuỗi ký tự trong câu trả lời.
            blocked_resp = pb.ChatWithCopilotResponse(
                response="Xin lỗi, tôi không thể xử lý yêu cầu này do vi phạm quy định an toàn.",
                degraded=False,
                trace_id=format(trace.get_current_span().get_span_context().trace_id, "032x"),
                cache_status="bypass",
                source_fingerprint="",
                similarity=0.0
            )
            blocked_resp.trace_steps.extend(trace_steps)
            return blocked_resp


        # Load long-term memory
        long_term_mem = load_user_memory(request.user_id)
        mem_context = format_memory_for_prompt(long_term_mem)
        
        if mem_context and not any(m.get("role") == "user" and mem_context in m["content"][0]["text"] for m in session):
             enriched_question = mem_context + "\\n\\n" + sanitized_question
        else:
             enriched_question = sanitized_question

        # Caching logic
        cache_status = "miss"
        cached_response = None
        similarity = 0.0
        catalog_fp = fetch_catalog_fingerprint()
        question_fp = hashlib.md5(enriched_question.encode()).hexdigest()[:12]
        
        model_ver = MAIN_MODEL.replace(":", "-")
        prompt_ver = "v1"
        
        l1_key = f"copilot:answer:{request.user_id}:{model_ver}:{prompt_ver}:{catalog_fp}:{question_fp}"
        scope_key = f"copilot:{request.user_id}:{model_ver}:{prompt_ver}:{catalog_fp}"

        if self._valkey:
            try:
                val = self._valkey.get(l1_key)
                if val:
                    cached_response = val
                    cache_status = "hit_exact"
            except Exception as e:
                logger.error("Valkey get cache failed: %s", e)

        embedding = None
        if not cached_response:
            # Try L2 Semantic Cache
            try:
                embed_resp = self._bedrock.invoke_model(
                    modelId="amazon.titan-embed-text-v2:0",
                    body=json.dumps({"inputText": sanitized_question})
                )
                embedding = json.loads(embed_resp["body"].read())["embedding"]
                
                ans, sim = get_semantic_cache(scope_key, embedding, threshold=1.0 - SEMANTIC_CACHE_MIN_SIM)
                if ans:
                    cached_response = ans
                    cache_status = "hit_semantic"
                    similarity = sim
            except Exception as e:
                logger.error("L2 Semantic cache failed: %s", e)

        session.append({"role": "user", "content": [{"text": enriched_question}]})

        routed_model = model_router.get_routed_model("copilot", MAIN_MODEL)
        logger.info(f"Routed model for copilot: {routed_model}")

        if cached_response:
            text_resp = cached_response
            degraded = False
            trace_id = ""
            actions = []
            citations = []
            pending = None
        else:
            start_llm = time.time()
            result = agent.run_agent(self._bedrock, routed_model, session, request.user_id)
            lat_llm = int((time.time() - start_llm) * 1000)
            trace_steps.append(demo_pb2.TraceStep(
                step_name="Model Gateway & Bedrock Nova",
                latency_ms=lat_llm,
                status="ok",
                detail=redact_pii(json.dumps({"routed_model": routed_model}))
            ))
            
            for ts in result.trace_steps:
                trace_steps.append(demo_pb2.TraceStep(
                    step_name=ts.get("step_name", ""),
                    latency_ms=ts.get("latency_ms", 0),
                    status=ts.get("status", ""),
                    detail=ts.get("detail", "")
                ))
            text_resp = result.text
            degraded = result.degraded
            trace_id = result.trace_id
            actions = result.actions_taken
            citations = result.citations
            pending = result.pending

        session.append({"role": "assistant", "content": [{"text": text_resp}]})
        self._save_session(session_id, request.user_id, session)
        
        # Save long-term memory
        prefs = extract_user_preferences(sanitized_question, text_resp)
        if prefs:
             redacted_prefs = {k: redact_pii(v) for k, v in prefs.items()}
             save_user_memory(request.user_id, redacted_prefs)

        resp = pb.ChatWithCopilotResponse(response=text_resp, degraded=degraded,
                                           trace_id=trace_id, trace_steps=trace_steps,
                                           cache_status=cache_status, similarity=similarity,
                                           source_fingerprint=catalog_fp)
        resp.actions_taken.extend(_to_records(actions))
        for c in citations:
            resp.citations.add(review_id=c.get("review_id", ""), snippet=c.get("snippet", ""),
                                score=str(c.get("score", "")))
        if pending is not None:
            token, expires_at = self._pending.put(
                request.user_id,
                pending.arguments["product_id"],
                pending.arguments["quantity"],
            )
            resp.pending_confirmation.CopyFrom(pb.PendingConfirmation(
                tool_name=pending.tool_name,
                arguments_json=json.dumps(pending.arguments),
                human_prompt=pending.human_prompt,
                confirmation_token=token,
                expires_at_unix=expires_at,
            ))
            
        # Save to cache if miss and no pending action (bypass cart ops)
        has_cart_op = any(a.tool_name in ["add_item_to_cart", "get_cart"] for a in actions)
        if cache_status == "miss":
            if has_cart_op or pending:
                resp.cache_status = "bypass"
            else:
                if self._valkey:
                    try:
                        self._valkey.setex(l1_key, COPILOT_CACHE_TTL, text_resp)
                    except Exception as e:
                        logger.error("Valkey set cache failed: %s", e)
                if embedding:
                    insert_semantic_cache(scope_key, sanitized_question, embedding, text_resp)

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
    main_timeout = float(os.environ.get('LLM_COPILOT_TIMEOUT', '6.9'))
    primary_config = Config(connect_timeout=1.0, read_timeout=main_timeout, retries={'max_attempts': 0})
    bedrock = create_bedrock_runtime_client(region_name=AWS_REGION, config=primary_config)

    valkey_addr = os.environ.get('VALKEY_ADDR', 'valkey-cart:6379')
    try:
        valkey_host, valkey_port = valkey_addr.split(':')
        valkey_port = int(valkey_port)
    except Exception:
        valkey_host = 'valkey-cart'
        valkey_port = 6379
    
    valkey_password = os.environ.get('VALKEY_AUTH_TOKEN', None)
    valkey_ssl = os.environ.get('VALKEY_TLS', 'false').lower() == 'true'
    valkey_client = redis.Redis(host=valkey_host, port=valkey_port, decode_responses=True,
                                socket_timeout=0.5, socket_connect_timeout=0.5,
                                password=valkey_password, ssl=valkey_ssl)

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=MAX_WORKERS))
    pb_grpc.add_ShoppingCopilotServiceServicer_to_server(
        ShoppingCopilotServicer(bedrock, valkey_client), server)
    health_servicer = health.HealthServicer()
    health_pb2_grpc.add_HealthServicer_to_server(health_servicer, server)
    health_servicer.set("", health_pb2.HealthCheckResponse.SERVING)
    health_servicer.set(
        "shopping_copilot.ShoppingCopilotService",
        health_pb2.HealthCheckResponse.SERVING,
    )
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
