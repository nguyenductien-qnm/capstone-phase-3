"""In-pod bench (Phase 3).
Runbook:
1. kubectl cp docs/ai/evals/mandate06_cases.py techx-tf1/<shopping-copilot-pod>:/app/
2. kubectl cp docs/ai/evals/inpod_bench.py techx-tf1/<shopping-copilot-pod>:/app/
3. kubectl exec -it -n techx-tf1 <shopping-copilot-pod> -- python3 /app/inpod_bench.py
4. kubectl cp techx-tf1/<shopping-copilot-pod>:/app/inpod_bench_report.md docs/ai/evals/
"""
import time
import urllib.request
import json
import statistics
import mandate06_cases as cases
import os
import sys
sys.path.append("/app")
from bedrock_client import create_bedrock_runtime_client

try:
    import boto3
    from botocore.config import Config
    import guardrails as g
except ImportError:
    pass

ML_GUARD_URL = os.environ.get("ML_GUARD_URL", "http://ml-guard:8090/v1/grounding")

def run_ml_guard():
    print("Running ML Guard T1 latency...")
    lat = []
    for ans, exp, cat in cases.GROUNDING_CASES:
        payload = {
            "source": cases.GROUNDING_SOURCE,
            "answer": ans
        }
        t0 = time.time()
        try:
            req = urllib.request.Request(
                ML_GUARD_URL,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            resp = urllib.request.urlopen(req, timeout=5)
            if resp.getcode() == 200:
                dt = (time.time() - t0) * 1000
                lat.append(dt)
        except Exception as e:
            print(f"Error calling ML Guard: {e}")
    if lat:
        print(f"ML Guard p50: {statistics.median(lat):.0f}ms")
    return lat

def run_nova_judge():
    print("Running Nova Judge T2 latency...")
    lat = []
    try:
        region = os.environ.get("AWS_REGION", "us-east-1")
        client = create_bedrock_runtime_client(region_name=region,
                              config=Config(connect_timeout=3, read_timeout=20, retries={"max_attempts": 2}))
        
        # Override to force T2 evaluation
        original_url = getattr(g, "ML_GUARD_URL", None)
        g.ML_GUARD_URL = ""
        
        for ans, exp, cat in cases.GROUNDING_CASES:
            t0 = time.time()
            g.apply_guardrail_output(client, ans, cases.GROUNDING_SOURCE, "test")
            dt = (time.time() - t0) * 1000
            lat.append(dt)
            
        g.ML_GUARD_URL = original_url
        if lat:
            print(f"Nova Judge p50: {statistics.median(lat):.0f}ms")
    except Exception as e:
        print(f"Error calling Nova Judge: {e}")
    return lat

if __name__ == "__main__":
    lat1 = run_ml_guard()
    lat2 = run_nova_judge()
    with open("inpod_bench_report.md", "w", encoding="utf-8") as f:
        f.write("# In-pod bench\n")
        f.write(f"- ML Guard T1 p50: {statistics.median(lat1):.0f}ms\n" if lat1 else "- ML Guard T1 failed\n")
        f.write(f"- Nova Judge T2 p50: {statistics.median(lat2):.0f}ms\n" if lat2 else "- Nova Judge T2 failed\n")
    print("Report written to inpod_bench_report.md")
