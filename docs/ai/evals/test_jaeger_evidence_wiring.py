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
    assert any(case_id == "citation_0" and rail == "CITATION"
               for case_id, rail, *_ in eval_mandate06_prod.build_cases())
