import os
import json
import glob

PRICING = {
    "amazon.nova-pro-v1:0": (0.80, 3.20),
    "amazon.nova-lite-v1:0": (0.06, 0.24),
    "amazon.nova-micro-v1:0": (0.035, 0.14),
    "amazon.titan-embed-text-v2:0": (0.02, 0.0),
}

EVIDENCE_DIR = os.path.join(os.path.dirname(__file__), "evidence")
REPORT_PATH = os.path.join(os.path.dirname(__file__), "cost_latency_report.md")

def process_dir(d):
    run_name = os.path.basename(d)
    date_str = run_name # roughly represents date
    
    files = glob.glob(os.path.join(d, "*.json"))
    cases = len(files)
    if cases == 0:
        return None
    
    passes = 0
    latencies = []
    has_spans = True
    
    total_in = 0
    total_out = 0
    total_embed = 0
    total_cost = 0.0
    
    for f in files:
        with open(f, 'r') as fp:
            try:
                data = json.load(fp)
            except:
                continue
            
            if isinstance(data, list):
                # Older format where the whole file is just a list of spans
                has_spans = True
                spans_to_process = data
            else:
                if data.get("passed") == True:
                    passes += 1
                if "latency" in data:
                    latencies.append(data["latency"])
                elif "latency_s" in data:
                    latencies.append(data["latency_s"])
                
                # Check if spans exist
                if "spans" not in data:
                    has_spans = False
                
                spans_to_process = data.get("spans", []) if "spans" in data else []
            
            for span in spans_to_process:
                attrs = span.get("attributes", {})
                model = attrs.get("gen_ai.request.model", "")
                if not model and "embed" in span.get("name", ""):
                    model = "amazon.titan-embed-text-v2:0" # default if not specified
                if not model:
                    model = attrs.get("model", "")
                
                tok_in = attrs.get("gen_ai.usage.input_tokens", 0)
                tok_out = attrs.get("gen_ai.usage.output_tokens", 0)
                if tok_in == 0 and "input_tokens" in attrs:
                    tok_in = attrs["input_tokens"]
                if tok_out == 0 and "output_tokens" in attrs:
                    tok_out = attrs["output_tokens"]
                
                if "embed" in span.get("name", "").lower() or "embed" in model.lower():
                    total_embed += tok_in
                else:
                    total_in += tok_in
                    total_out += tok_out
                    
                if model in PRICING:
                    c_in, c_out = PRICING[model]
                    total_cost += (tok_in / 1_000_000.0) * c_in
                    total_cost += (tok_out / 1_000_000.0) * c_out
                        
    pass_rate = (passes / cases) * 100 if cases > 0 else 0
    latencies.sort()
    
    def percentile(data_sorted, p):
        if not data_sorted: return 0
        k = (len(data_sorted) - 1) * p
        f = int(k)
        c = f + 1
        if c >= len(data_sorted): return data_sorted[-1]
        return data_sorted[f] + (k - f) * (data_sorted[c] - data_sorted[f])
        
    p50 = percentile(latencies, 0.5)
    p95 = percentile(latencies, 0.95)
    
    usd_per_req = total_cost / cases if cases > 0 else 0
    
    return {
        "run": run_name,
        "cases": cases,
        "pass_rate": pass_rate,
        "p50": p50,
        "p95": p95,
        "total_in": total_in,
        "total_out": total_out,
        "total_embed": total_embed,
        "usd_per_req": usd_per_req,
        "has_spans": has_spans
    }

def main():
    if not os.path.exists(EVIDENCE_DIR):
        print(f"No evidence directory found at {EVIDENCE_DIR}")
        # We will just write a dummy table for now
        results = []
    else:
        dirs = [os.path.join(EVIDENCE_DIR, d) for d in os.listdir(EVIDENCE_DIR) if os.path.isdir(os.path.join(EVIDENCE_DIR, d))]
        dirs.sort()
        
        results = []
        for d in dirs:
            res = process_dir(d)
            if res:
                results.append(res)
            
    table_lines = [
        "| Run | Ngày | Cases | Pass | p50 (s) | p95 (s) | Token In | Token Out | Embed Token | USD/req |",
        "|---|---|---|---|---|---|---|---|---|---|"
    ]
    
    if not results:
        table_lines.append("| (sẽ được điền bởi script) | | | | | | | | | |")
    else:
        for r in results:
            run = r["run"]
            date = run
            cases = r["cases"]
            pass_rate = f"{r['pass_rate']:.1f}%"
            p50 = f"{r['p50']:.2f}"
            p95 = f"{r['p95']:.2f}"
            
            if not r["has_spans"]:
                tok_in = "n/a (harness cũ không lưu span)"
                tok_out = "n/a (harness cũ không lưu span)"
                tok_embed = "n/a (harness cũ không lưu span)"
                usd = "n/a (harness cũ không lưu span)"
            else:
                tok_in = str(r["total_in"])
                tok_out = str(r["total_out"])
                tok_embed = str(r["total_embed"])
                usd = f"{r['usd_per_req']:.6f}"
                
            table_lines.append(f"| {run} | {date} | {cases} | {pass_rate} | {p50} | {p95} | {tok_in} | {tok_out} | {tok_embed} | {usd} |")

    table_md = "\n".join(table_lines)
    print(table_md)
    
    report_content = f"""# Before/After Cost & Latency Report (MANDATE-14)

> Sinh tự động bởi `cost_before_after.py`. Mọi số liệu dưới đây đo được từ evidence JSON,
> áp cùng một bảng giá Bedrock on-demand us-east-1 (tra 2026-07-26).
> Chạy `python3 cost_before_after.py` để cập nhật.

## Bảng giá áp dụng
| Model | Input ($/1M) | Output ($/1M) |
|---|---|---|
| Nova Pro | 0.80 | 3.20 |
| Nova Lite | 0.06 | 0.24 |
| Nova Micro | 0.035 | 0.14 |
| Titan Embed v2 | 0.02 | 0.00 |

## So sánh theo run
*(Chạy `python3 cost_before_after.py` để sinh bảng thật)*

{table_md}

## Nguyên nhân thay đổi
- Sửa cách chấm điểm (scoring rubric chuẩn hóa)
- Đưa Titan Embed vào sổ chi phí (trước đó span `bedrock_embed` chưa được đo)
- Sửa timeout frontend-proxy (giảm 504)
- **Không** quy công cho "dùng Nova Lite" — model router đã có từ trước
"""
    with open(REPORT_PATH, 'w') as f:
        f.write(report_content)
    print(f"\\nReport written to {REPORT_PATH}")

if __name__ == "__main__":
    main()
