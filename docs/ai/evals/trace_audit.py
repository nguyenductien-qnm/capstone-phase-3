import os
import sys
import glob
import json
from pathlib import Path

def main():
    if len(sys.argv) > 1:
        evidence_dir = Path(sys.argv[1])
        print(f"Auditing evidence in {evidence_dir}")
        files = list(evidence_dir.glob("*.json"))
    else:
        # Check all evidence dirs
        base_dir = Path(__file__).parent / "evidence"
        dirs = [d for d in base_dir.iterdir() if d.is_dir()]
        if not dirs:
            print("No evidence directory found.")
            sys.exit(1)
        print(f"Auditing evidence in all directories under {base_dir}")
        files = []
        for d in dirs:
            files.extend(d.glob("*.json"))

    if not files:
        print("No json files found in evidence dir.")
        sys.exit(1)

    checks = {
        "semantic_search": False,
        "no_keyword_fallback": True,
        "titan_called": False,
        "intent_6": False,
        "input_blocked": False,
        "output_rail": False,
        "cost_measured": False,
        "citation_real": False,
    }

    has_grounding = False

    for fpath in files:
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        if not isinstance(data, dict):
            continue

        category = data.get("category", "")
        spans = data.get("spans", [])
        response = data.get("response", {})
        
        if not isinstance(response, dict):
            response = {}

        # Semantic search
        has_semantic = False
        has_keyword = False
        for s in spans:
            if s["name"] == "oteldemo.ProductCatalogService/SearchProducts":
                mode = str(s["attributes"].get("app.search.mode", "")).lower()
                count = int(s["attributes"].get("app.products_search.count", 0) or 0)
                if mode == "semantic" and count > 0:
                    has_semantic = True
                elif mode == "keyword":
                    has_keyword = True
        
        if has_semantic:
            checks["semantic_search"] = True
            
        if category == "grounding":
            has_grounding = True
            if has_keyword:
                checks["no_keyword_fallback"] = False
                
        # Titan
        for s in spans:
            if s["name"] == "bedrock_embed":
                tokens = int(s["attributes"].get("gen_ai.usage.input_tokens", 0) or 0)
                if tokens > 0:
                    checks["titan_called"] = True
                    
        # Intent 6
        for s in spans:
            if s["name"] == "tool_call":
                tname = s["attributes"].get("tool.name", "")
                tsuccess = str(s["attributes"].get("tool.succeeded", "")).lower() == "true"
                if tname in ("convert_currency", "get_shipping_quote") and tsuccess:
                    checks["intent_6"] = True
                    
        # Nhánh chặn input
        for s in spans:
            if s["name"] == "guardrail_input":
                blocked = str(s["attributes"].get("guardrail.blocked", "")).lower() == "true"
                if blocked:
                    checks["input_blocked"] = True
                    
        # Rail output (case có tool)
        has_tool = any(s["name"] == "tool_call" for s in spans)
        if has_tool:
            for s in spans:
                if s["name"] == "guardrail_output_grounding":
                    checks["output_rail"] = True
                    
        # Chi phí đo được (case không bị chặn)
        is_blocked = any(s["name"] == "guardrail_input" and str(s["attributes"].get("guardrail.blocked", "")).lower() == "true" for s in spans)
        if not is_blocked:
            for s in spans:
                if s["name"] in ("bedrock_converse", "bedrock_embed"):
                    tokens = int(s["attributes"].get("gen_ai.usage.input_tokens", 0) or 0)
                    if tokens > 0:
                        checks["cost_measured"] = True
                        
        # Citation
        if category == "citation":
            citations = response.get("citations", [])
            if len(citations) >= 1:
                checks["citation_real"] = True

    if not has_grounding:
        print("Warning: No grounding cases found, skipping no_keyword_fallback check")
        checks["no_keyword_fallback"] = True

    failed = []
    for k, v in checks.items():
        print(f"Check {k}: {'✅' if v else '❌'}")
        if not v:
            failed.append(k)
            
    if failed:
        print(f"\nAudit failed for: {', '.join(failed)}")
        sys.exit(1)
        
    print("\nAll trace audits passed!")
    sys.exit(0)

if __name__ == "__main__":
    main()
