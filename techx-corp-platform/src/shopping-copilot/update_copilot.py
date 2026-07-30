import re

with open('src/shopping-copilot/copilot_server.py', 'r') as f:
    content = f.read()

# 1. Imports
imports = """import json
import logging
import hashlib
import redis
import os
import time
import uuid"""
content = re.sub(r'import json\nimport logging\nimport os\nimport time\nimport uuid', imports, content, count=1)

imports2 = """import demo_pb2
from memory import extract_user_preferences, save_user_memory, load_user_memory, format_memory_for_prompt, fetch_catalog_fingerprint, get_semantic_cache, insert_semantic_cache"""
content = re.sub(r'import demo_pb2', imports2, content, count=1)

# 2. Env vars
env_vars = """MAX_SESSION_MESSAGES = int(os.environ.get("COPILOT_MAX_SESSION_MESSAGES", "20"))
COPILOT_CACHE_TTL = int(os.environ.get("COPILOT_CACHE_TTL", "3600"))
SESSION_TTL = int(os.environ.get("COPILOT_SESSION_TTL", "3600"))
SEMANTIC_CACHE_MIN_SIM = float(os.environ.get("SEMANTIC_CACHE_MIN_SIM", "0.93"))"""
content = re.sub(r'MAX_SESSION_MESSAGES = int\(os.environ.get\("COPILOT_MAX_SESSION_MESSAGES", "20"\)\)', env_vars, content, count=1)

# 3. Class init
init_code = """class ShoppingCopilotServicer(pb_grpc.ShoppingCopilotServiceServicer):
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
        self._sessions_fallback[session_id] = messages"""
content = re.sub(r'class ShoppingCopilotServicer\(pb_grpc.ShoppingCopilotServiceServicer\):\n    def __init__\(self, bedrock_client\):\n        self._bedrock = bedrock_client\n        self._sessions: dict\[str, list\] = \{\}\n        self._pending = _PendingStore\(CONFIRM_TTL_SECONDS\)', init_code, content, count=1)

# 4. ChatWithCopilot up to blocked
chat_code = """        # --- Phase 1: normal agent turn.
        session_id = request.session_id or request.user_id
        session = self._get_session(session_id, request.user_id)"""
content = re.sub(r'        # --- Phase 1: normal agent turn.\n        session = self._sessions.setdefault\(request.session_id or request.user_id, \[\]\)\n        session_id = request.session_id or request.user_id', chat_code, content, count=1)

# 5. blocked response
blocked_resp = """            blocked_resp = pb.ChatWithCopilotResponse(
                response="Xin lỗi, tôi không thể xử lý yêu cầu này do vi phạm quy định an toàn.",
                degraded=False,
                trace_id=format(trace.get_current_span().get_span_context().trace_id, "032x"),
                cache_status="bypass",
                source_fingerprint="",
                similarity=0.0
            )"""
content = re.sub(r'            blocked_resp = pb.ChatWithCopilotResponse\(\n                response="Xin lỗi, tôi không thể xử lý yêu cầu này do vi phạm quy định an toàn.",\n                degraded=False,\n                trace_id=format\(trace.get_current_span\(\).get_span_context\(\).trace_id, "032x"\),\n            \)', blocked_resp, content, count=1)

# 6. Main logic replacement
main_logic = """
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

        return resp"""
        
content = re.sub(r'        session.append\(\{"role": "user", "content": \[\{"text": sanitized_question\}\]\}\)\n\n        routed_model = model_router.get_routed_model\("copilot", MAIN_MODEL\)\n        logger.info\(f"Routed model for copilot: \{routed_model\}"\)\n\n        start_llm = time.time\(\)\n        result = agent.run_agent\(self._bedrock, routed_model, session, request.user_id\)\n        lat_llm = int\(\(time.time\(\) - start_llm\) \* 1000\)\n        trace_steps.append\(demo_pb2.TraceStep\(\n            step_name="Model Gateway & Bedrock Nova",\n            latency_ms=lat_llm,\n            status="ok",\n            detail=redact_pii\(json.dumps\(\{"routed_model": routed_model\}\)\)\n        \)\)\n        \n        for ts in result.trace_steps:\n            trace_steps.append\(demo_pb2.TraceStep\(\n                step_name=ts.get\("step_name", ""\),\n                latency_ms=ts.get\("latency_ms", 0\),\n                status=ts.get\("status", ""\),\n                detail=ts.get\("detail", ""\)\n            \)\)\n\n        session.append\(\{"role": "assistant", "content": \[\{"text": result.text\}\]\}\)\n        # Bound the stored context so old turns don\'t crowd the window.\n        if len\(session\) > MAX_SESSION_MESSAGES:\n            del session\[:-MAX_SESSION_MESSAGES\]\n\n        resp = pb.ChatWithCopilotResponse\(response=result.text, degraded=result.degraded,\n                                           trace_id=result.trace_id, trace_steps=trace_steps\)\n        resp.actions_taken.extend\(_to_records\(result.actions_taken\)\)\n        for c in result.citations:\n            resp.citations.add\(review_id=c.get\("review_id", ""\), snippet=c.get\("snippet", ""\),\n                                score=str\(c.get\("score", ""\)\)\)\n        if result.pending is not None:\n            token, expires_at = self._pending.put\(\n                request.user_id,\n                result.pending.arguments\["product_id"\],\n                result.pending.arguments\["quantity"\],\n            \)\n            resp.pending_confirmation.CopyFrom\(pb.PendingConfirmation\(\n                tool_name=result.pending.tool_name,\n                arguments_json=json.dumps\(result.pending.arguments\),\n                human_prompt=result.pending.human_prompt,\n                confirmation_token=token,\n                expires_at_unix=expires_at,\n            \)\)\n        return resp', main_logic, content, count=1)


# 7. serve function Valkey init
serve_logic = """def serve():
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
        ShoppingCopilotServicer(bedrock, valkey_client), server)"""
content = re.sub(r'def serve\(\):\n    main_timeout = float\(os.environ.get\(\'LLM_COPILOT_TIMEOUT\', \'6.9\'\)\)\n    primary_config = Config\(connect_timeout=1.0, read_timeout=main_timeout, retries=\{\'max_attempts\': 0\}\)\n    bedrock = create_bedrock_runtime_client\(region_name=AWS_REGION, config=primary_config\)\n    server = grpc.server\(futures.ThreadPoolExecutor\(max_workers=MAX_WORKERS\)\)\n    pb_grpc.add_ShoppingCopilotServiceServicer_to_server\(\n        ShoppingCopilotServicer\(bedrock\), server\)', serve_logic, content, count=1)


with open('src/shopping-copilot/copilot_server.py', 'w') as f:
    f.write(content)
