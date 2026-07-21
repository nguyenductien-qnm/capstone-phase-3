import requests

def fetch_trace(trace_id, base_url):
    url = f"{base_url}/jaeger/ui/api/traces/{trace_id}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None

def summarize_spans(trace_json):
    if not trace_json or "data" not in trace_json or not trace_json["data"]:
        return []
    
    known_spans = {
        "guardrail_input",
        "bedrock_converse",
        "tool_call",
        "guardrail_citation_validation",
        "guardrail_output_grounding"
    }
    
    summary = []
    spans = trace_json["data"][0].get("spans", [])
    for span in spans:
        name = span.get("operationName", "")
        if name in known_spans:
            attrs = {}
            for tag in span.get("tags", []):
                key = tag.get("key", "")
                if key.startswith("guardrail.") or key.startswith("gen_ai.usage."):
                    attrs[key] = tag.get("value")
            summary.append({"name": name, "attributes": attrs})
            
    return summary

def jaeger_ui_link(trace_id, base_url):
    return f"{base_url}/trace/{trace_id}"
