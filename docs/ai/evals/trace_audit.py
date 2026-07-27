import os
import sys
import glob
import json
import argparse
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Audit evidence trace files.")
    parser.add_argument("--dirs", nargs="+", help="Specific directories to audit")
    parser.add_argument("--all", action="store_true", help="Audit all directories (warning: spans multiple runs)")
    
    args = parser.parse_args()
    
    base_dir = Path(__file__).parent / "evidence"
    
    if not base_dir.exists() or not base_dir.is_dir():
        print(f"Base evidence directory {base_dir} not found.")
        sys.exit(1)
        
    all_dirs = sorted([d for d in base_dir.iterdir() if d.is_dir()], key=lambda x: x.name)
    
    if not all_dirs:
        print("No evidence directory found.")
        sys.exit(1)
        
    dirs_to_audit = []
    
    if args.dirs:
        for d in args.dirs:
            dp = Path(d)
            if not dp.is_absolute():
                dp = Path.cwd() / d
            if dp.is_dir():
                dirs_to_audit.append(dp)
            else:
                print(f"Directory not found: {dp}")
                sys.exit(1)
        print(f"Auditing evidence in specified directories: {[d.name for d in dirs_to_audit]}")
    elif args.all:
        print("Warning: Auditing all directories. Results will span multiple runs!")
        dirs_to_audit = all_dirs
    else:
        # Latest dir only
        latest_dir = all_dirs[-1]
        dirs_to_audit = [latest_dir]
        print(f"Auditing evidence in latest directory: {latest_dir.name}")
        
    checks = {
        "semantic_search": None,
        "no_keyword_fallback": True,
        "titan_called": None,
        "intent_6": None,
        "input_blocked": None,
        "output_rail": None,
        "cost_measured": None,
        "citation_real": None,
    }
    
    has_grounding = False
    keyword_fallback_failed_dir = None

    for d in dirs_to_audit:
        files = list(d.glob("*.json"))
        try:
            dir_name_str = str(d.relative_to(base_dir.parent))
        except ValueError:
            dir_name_str = str(d)
        
        for fpath in files:
            with open(fpath, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    continue
            
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
                if s.get("name") == "oteldemo.ProductCatalogService/SearchProducts":
                    mode = str(s.get("attributes", {}).get("app.search.mode", "")).lower()
                    count = int(s.get("attributes", {}).get("app.products_search.count", 0) or 0)
                    if mode == "semantic" and count > 0:
                        has_semantic = True
                    elif mode == "keyword":
                        has_keyword = True
                        
            if has_semantic and checks["semantic_search"] is None:
                checks["semantic_search"] = dir_name_str
                
            if category == "grounding":
                has_grounding = True
                if has_keyword:
                    checks["no_keyword_fallback"] = False
                    if not keyword_fallback_failed_dir:
                        keyword_fallback_failed_dir = dir_name_str
                        
            # Titan
            for s in spans:
                if s.get("name") == "bedrock_embed":
                    tokens = int(s.get("attributes", {}).get("gen_ai.usage.input_tokens", 0) or 0)
                    if tokens > 0 and checks["titan_called"] is None:
                        checks["titan_called"] = dir_name_str
                        
            # Intent 6
            has_currency = False
            has_shipping = False
            for s in spans:
                if s.get("name") == "tool_call":
                    tname = s.get("attributes", {}).get("tool.name", "")
                    tsuccess = str(s.get("attributes", {}).get("tool.succeeded", "")).lower() == "true"
                    if tsuccess:
                        if tname == "convert_currency":
                            has_currency = True
                        elif tname == "get_shipping_quote":
                            has_shipping = True
                            
            if has_currency and has_shipping and checks["intent_6"] is None:
                checks["intent_6"] = dir_name_str
                
            # Nhánh chặn input
            for s in spans:
                if s.get("name") == "guardrail_input":
                    blocked = str(s.get("attributes", {}).get("guardrail.blocked", "")).lower() == "true"
                    if blocked and checks["input_blocked"] is None:
                        checks["input_blocked"] = dir_name_str
                        
            # Rail output (case có tool)
            has_tool = any(s.get("name") == "tool_call" for s in spans)
            if has_tool:
                for s in spans:
                    if s.get("name") == "guardrail_output_grounding" and checks["output_rail"] is None:
                        checks["output_rail"] = dir_name_str
                        
            # Chi phí đo được (case không bị chặn)
            is_blocked = any(s.get("name") == "guardrail_input" and str(s.get("attributes", {}).get("guardrail.blocked", "")).lower() == "true" for s in spans)
            if not is_blocked:
                for s in spans:
                    if s.get("name") in ("bedrock_converse", "bedrock_embed"):
                        tokens = int(s.get("attributes", {}).get("gen_ai.usage.input_tokens", 0) or 0)
                        if tokens > 0 and checks["cost_measured"] is None:
                            checks["cost_measured"] = dir_name_str
                            
            # Citation
            if category == "citation":
                citations = response.get("citations", [])
                if len(citations) >= 1 and checks["citation_real"] is None:
                    checks["citation_real"] = dir_name_str

    if not has_grounding:
        print("Warning: No grounding cases found, skipping no_keyword_fallback check")
        checks["no_keyword_fallback"] = True

    failed = []
    
    for k, v in checks.items():
        if k == "no_keyword_fallback":
            if v:
                print(f"Check {k}: ✅ (All checked)")
            else:
                print(f"Check {k}: ❌ ({keyword_fallback_failed_dir})")
                failed.append(k)
        else:
            if v is not None:
                print(f"Check {k}: ✅ ({v})")
            else:
                print(f"Check {k}: ❌")
                failed.append(k)
                
    if failed:
        print(f"\nAudit failed for: {', '.join(failed)}")
        sys.exit(1)
        
    print("\nAll trace audits passed!")
    sys.exit(0)

if __name__ == "__main__":
    main()
