from unittest.mock import Mock

import eval_mandate06_prod
import jaeger_client


TRACE_ID = "0123456789abcdef0123456789abcdef"


def test_jaeger_ui_base_accepts_origin_or_full_path():
    assert jaeger_client.jaeger_ui_base("https://jaeger.example") == (
        "https://jaeger.example/jaeger/ui"
    )
    assert jaeger_client.jaeger_ui_base("https://jaeger.example/jaeger/ui/") == (
        "https://jaeger.example/jaeger/ui"
    )


def test_jaeger_links_include_configured_base_path():
    assert jaeger_client.jaeger_ui_link(TRACE_ID, "https://jaeger.example") == (
        f"https://jaeger.example/jaeger/ui/trace/{TRACE_ID}"
    )


def test_fetch_trace_polls_until_exported(monkeypatch):
    pending = Mock(status_code=404)
    ready = Mock(status_code=200)
    ready.json.return_value = {
        "data": [{"spans": [{"operationName": "shopping_copilot.chat", "tags": []}]}]
    }
    get = Mock(side_effect=[pending, ready])
    monkeypatch.setattr(jaeger_client.requests, "get", get)
    monkeypatch.setattr(jaeger_client.time, "sleep", lambda _: None)

    result = jaeger_client.fetch_trace(
        TRACE_ID,
        "https://jaeger.example/jaeger/ui",
        wait_timeout=1,
    )

    assert result == ready.json.return_value
    assert get.call_count == 2
    assert get.call_args.args[0] == (
        f"https://jaeger.example/jaeger/ui/api/traces/{TRACE_ID}"
    )


def test_fetch_trace_waits_for_request_span(monkeypatch):
    partial = Mock(status_code=200)
    partial.json.return_value = {
        "data": [{"spans": [{"operationName": "guardrail_input", "tags": []}]}]
    }
    complete = Mock(status_code=200)
    complete.json.return_value = {
        "data": [{"spans": [
            {"operationName": "guardrail_input", "tags": []},
            {"operationName": "shopping_copilot.chat", "tags": []},
        ]}]
    }
    get = Mock(side_effect=[partial, complete])
    monkeypatch.setattr(jaeger_client.requests, "get", get)
    monkeypatch.setattr(jaeger_client.time, "sleep", lambda _: None)

    result = jaeger_client.fetch_trace(
        TRACE_ID, "https://jaeger.example", wait_timeout=1
    )

    assert result == complete.json.return_value
    assert get.call_count == 2


def test_span_count_is_not_limited_to_known_summary_spans():
    trace_json = {
        "data": [{
            "spans": [
                {"operationName": "shopping_copilot.chat", "tags": []},
                {"operationName": "grpc.server", "tags": []},
            ]
        }]
    }

    assert jaeger_client.count_spans(trace_json) == 2
    assert jaeger_client.summarize_spans(trace_json) == [
        {"name": "shopping_copilot.chat", "attributes": {}}
    ]


def test_eval_reads_protobuf_camel_case_response_fields():
    text, trace_id, citations = eval_mandate06_prod.extract_response_fields({
        "response": "Grounded answer",
        "traceId": TRACE_ID,
        "citations": [{"reviewId": "alice", "snippet": "Good", "score": "5"}],
    })

    assert text == "Grounded answer"
    assert trace_id == TRACE_ID
    assert len(citations) == 1


def test_eval_keeps_snake_case_compatibility_and_has_citation_probe():
    _, trace_id, _ = eval_mandate06_prod.extract_response_fields({"trace_id": TRACE_ID})
    assert trace_id == TRACE_ID
    citation_cases = [case for case in eval_mandate06_prod.build_cases()
                      if case[0] == "citation_0" and case[1] == "CITATION"]
    assert len(citation_cases) == 1
    assert eval_mandate06_prod.EVAL_PRODUCT_ID in citation_cases[0][2]


def test_fetch_trace_falls_back_to_origin_api_endpoint(monkeypatch):
    ui_404 = Mock(status_code=404)
    ui_404.json.side_effect = ValueError("HTML 404 page")
    origin_200 = Mock(status_code=200)
    origin_200.json.return_value = {
        "data": [{"spans": [{"operationName": "shopping_copilot.chat", "tags": []}]}]
    }
    get = Mock(side_effect=[ui_404, origin_200])
    monkeypatch.setattr(jaeger_client.requests, "get", get)
    monkeypatch.setattr(jaeger_client.time, "sleep", lambda _: None)

    result = jaeger_client.fetch_trace(
        TRACE_ID,
        "http://127.0.0.1:16686",
        wait_timeout=1,
    )

    assert result == origin_200.json.return_value
    assert get.call_count == 2
    assert get.call_args_list[0].args[0] == f"http://127.0.0.1:16686/jaeger/ui/api/traces/{TRACE_ID}"
    assert get.call_args_list[1].args[0] == f"http://127.0.0.1:16686/api/traces/{TRACE_ID}"


