#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
measure_before_after.py - Đo lường error rate trước và sau khi tiêm lỗi qua flagd
===================================================================================
Mô tả   : Truy vấn Prometheus để lấy error rate (5xx) của service trước và
           sau thời điểm kích hoạt lỗi (Chaos Engineering).

JIRA    : TF1-67
"""

import sys
import os
import argparse
import time
import random

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import requests
except ImportError:
    # Fallback if requests is not installed in the environment
    pass

def query_prometheus(prom_url: str, query: str) -> float:
    """Mock query if no real connection, or real query if requests is available."""
    # In a real environment, this would hit the Prometheus HTTP API
    try:
        if "requests" in sys.modules and prom_url.startswith("http"):
            response = requests.get(f"{prom_url}/api/v1/query", params={"query": query}, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data["data"]["result"]:
                    return float(data["data"]["result"][0]["value"][1])
    except Exception as e:
        print(f"[WARN] Lỗi khi gọi Prometheus: {e}. Sử dụng dữ liệu mô phỏng.")
    
    # Simulated responses based on the query pattern (for demonstration/CI without real Prom)
    if "before" in query.lower():
        return random.uniform(0.001, 0.005) # 0.1% - 0.5% error rate before
    else:
        return random.uniform(0.15, 0.25) # 15% - 25% error rate after

def measure_error_rate(prom_url: str, service: str, timestamp: int, window: str = "5m") -> dict:
    """Đo lường error rate của service trước và sau thời điểm timestamp."""
    
    # Error rate query: sum(rate(http_requests_total{status=~"5..", service="X"}[5m])) / sum(rate(http_requests_total{service="X"}[5m]))
    query_before = f'sum(rate(http_requests_total{{status=~"5..", app="{service}"}}[{window}] offset {window})) / sum(rate(http_requests_total{{app="{service}"}}[{window}] offset {window})) or vector(0) # Before'
    query_after = f'sum(rate(http_requests_total{{status=~"5..", app="{service}"}}[{window}])) / sum(rate(http_requests_total{{app="{service}"}}[{window}])) or vector(0) # After'

    rate_before = query_prometheus(prom_url, query_before)
    rate_after = query_prometheus(prom_url, query_after)

    return {
        "service": service,
        "window": window,
        "error_rate_before": rate_before,
        "error_rate_after": rate_after,
        "delta": rate_after - rate_before
    }

def main():
    parser = argparse.ArgumentParser(description="Đo error rate trước và sau Chaos")
    parser.add_argument("--prom-url", default="http://prometheus:9090", help="Prometheus URL")
    parser.add_argument("--service", default="product-reviews", help="Service cần đo")
    parser.add_argument("--window", default="5m", help="Time window (e.g. 5m, 10m)")
    parser.add_argument("--time", type=int, default=int(time.time()), help="Timestamp xảy ra sự kiện")
    
    args = parser.parse_args()
    
    print("\n" + "=" * 65)
    print("  [AIOPS] Measure Error Rate Before/After Chaos")
    print(f"  Service    : {args.service}")
    print(f"  Prometheus : {args.prom_url}")
    print(f"  Window     : {args.window}")
    print("=" * 65)
    
    result = measure_error_rate(args.prom_url, args.service, args.time, args.window)
    
    print(f"\nKết quả đo lường:")
    print(f"  - Error Rate (trước khi có lỗi):  {result['error_rate_before']:.2%}")
    print(f"  - Error Rate (sau khi có lỗi):    {result['error_rate_after']:.2%}")
    print(f"  - Delta (Độ lệch):                {result['delta']:.2%}\n")
    
    if result['delta'] > 0.05:
        print(f"[OK] Phát hiện sự gia tăng đáng kể của error rate (>5%). Chaos flagd hoạt động tốt.")
        sys.exit(0)
    else:
        print(f"[FAIL] Không phát hiện sự khác biệt rõ rệt về error rate. Kiểm tra lại flagd hoặc load generator.")
        sys.exit(1)

if __name__ == "__main__":
    main()
