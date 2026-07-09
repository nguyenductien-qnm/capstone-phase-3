#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[AIOps-W1-T4] Log Clustering using Drain3
===========================================
Thu thập log thô từ OpenSearch (product-reviews, llm), phân cụm bằng Drain3,
và phát hiện các log template lỗi mới lạ (OOM, DB timeout, 5xx) để cảnh báo.

Author: AIO03 - TF1
"""

import os
import sys
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

# Fix UTF-8 output trên Windows (tránh UnicodeEncodeError khi print tiếng Việt)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from drain3 import TemplateMiner
from drain3.template_miner_config import TemplateMinerConfig
from opensearchpy import OpenSearch

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────

OPENSEARCH_HOST = os.getenv("OPENSEARCH_HOST", "localhost")
OPENSEARCH_PORT = int(os.getenv("OPENSEARCH_PORT", "9200"))
OPENSEARCH_USER = os.getenv("OPENSEARCH_USER", "admin")
OPENSEARCH_PASS = os.getenv("OPENSEARCH_PASS", "admin")
OPENSEARCH_INDEX_PATTERN = os.getenv("OPENSEARCH_INDEX_PATTERN", "otel-v1-apm-service-*")

# Cửa sổ thời gian: số phút nhìn ngược lại
LOOKBACK_MINUTES = int(os.getenv("LOOKBACK_MINUTES", "60"))

# Service cần giám sát tầng GenAI
TARGET_SERVICES = os.getenv(
    "TARGET_SERVICES",
    "product-reviews,llm"
).split(",")

# File lưu trạng thái Drain3 (dùng khi chạy liên tục)
STATE_FILE = os.getenv("STATE_FILE", "/tmp/drain3_state.bin")

# Từ khóa trigger cảnh báo
ALERT_KEYWORDS = ["ERROR", "CRITICAL", "OOM", "timeout", "connection refused",
                  "5xx", "rate limit", "OutOfMemory", "FATAL", "traceback",
                  "exception", "killed", "oom_kill"]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger("log_clustering")


# ─────────────────────────────────────────────────────────────────────────────
# 1. Fetch logs từ OpenSearch
# ─────────────────────────────────────────────────────────────────────────────

def build_opensearch_client() -> OpenSearch:
    """Tạo kết nối OpenSearch."""
    return OpenSearch(
        hosts=[{"host": OPENSEARCH_HOST, "port": OPENSEARCH_PORT}],
        http_auth=(OPENSEARCH_USER, OPENSEARCH_PASS),
        use_ssl=False,
        verify_certs=False,
        ssl_show_warn=False,
    )


def fetch_logs_from_opensearch(
    client: OpenSearch,
    services: list[str],
    lookback_minutes: int = 60,
    max_docs: int = 5000,
) -> list[dict]:
    """
    Lấy log thô từ OpenSearch cho các service chỉ định trong cửa sổ thời gian.

    Returns:
        Danh sách dict chứa: timestamp, service_name, log_message
    """
    since = (datetime.now(tz=timezone.utc) - timedelta(minutes=lookback_minutes)).isoformat()

    query = {
        "size": max_docs,
        "sort": [{"@timestamp": {"order": "asc"}}],
        "_source": ["@timestamp", "resource.attributes.service.name",
                    "Body", "SeverityText", "Attributes"],
        "query": {
            "bool": {
                "must": [
                    {"range": {"@timestamp": {"gte": since}}},
                    {"terms": {"resource.attributes.service.name": services}}
                ]
            }
        }
    }

    try:
        resp = client.search(index=OPENSEARCH_INDEX_PATTERN, body=query)
    except Exception as e:
        logger.warning(f"OpenSearch query failed: {e}. Falling back to sample logs.")
        return _get_sample_logs()

    hits = resp.get("hits", {}).get("hits", [])
    logger.info(f"Fetched {len(hits)} log records from OpenSearch (last {lookback_minutes}m)")

    logs = []
    for hit in hits:
        src = hit.get("_source", {})
        body = src.get("Body", "") or ""
        attrs = src.get("Attributes", {}) or {}
        extra = attrs.get("exception.message", "") or attrs.get("exception.type", "")
        message = f"{body} {extra}".strip()

        if not message:
            continue

        logs.append({
            "timestamp": src.get("@timestamp", ""),
            "service": src.get("resource.attributes.service.name", "unknown"),
            "severity": src.get("SeverityText", "INFO"),
            "message": message,
        })

    return logs


def _get_sample_logs() -> list[dict]:
    """
    Sample log offline – dùng khi không có OpenSearch (test / CI).
    Mô phỏng các loại log thực tế từ product-reviews và llm.
    """
    now = datetime.now(tz=timezone.utc).isoformat()
    return [
        # ── product-reviews ──────────────────────────────────────────────────
        {"timestamp": now, "service": "product-reviews", "severity": "INFO",
         "message": "Receive GetProductReviews for product id:OLJCESPC7Z"},
        {"timestamp": now, "service": "product-reviews", "severity": "INFO",
         "message": "Receive GetProductReviews for product id:L9ECAV7KIM"},
        {"timestamp": now, "service": "product-reviews", "severity": "INFO",
         "message": "Receive GetProductReviews for product id:2ZYFJ3GM2N"},
        {"timestamp": now, "service": "product-reviews", "severity": "ERROR",
         "message": "ERROR: connection to server at 'postgresql' (10.0.1.5), port 5432 failed: FATAL: remaining connection slots are reserved for non-replication superuser connections"},
        {"timestamp": now, "service": "product-reviews", "severity": "ERROR",
         "message": "ERROR: connection to server at 'postgresql' (10.0.1.5), port 5432 failed: FATAL: remaining connection slots are reserved for non-replication superuser connections"},
        {"timestamp": now, "service": "product-reviews", "severity": "ERROR",
         "message": "Caught Exception: Error code: 429 - Rate limit reached. Please try again later."},
        {"timestamp": now, "service": "product-reviews", "severity": "ERROR",
         "message": "Caught Exception: Error code: 429 - Rate limit reached. Please try again later."},
        {"timestamp": now, "service": "product-reviews", "severity": "ERROR",
         "message": "Caught Exception: Error code: 429 - Rate limit reached. Please try again later."},
        {"timestamp": now, "service": "product-reviews", "severity": "INFO",
         "message": "llmRateLimitError feature flag: True"},
        {"timestamp": now, "service": "product-reviews", "severity": "INFO",
         "message": "llmRateLimitError feature flag: False"},
        {"timestamp": now, "service": "product-reviews", "severity": "ERROR",
         "message": "grpc._channel._InactiveRpcError: StatusCode.UNAVAILABLE: failed to connect to all addresses; last error: UNKNOWN: ipv4:10.0.2.3:8080: Failed to connect to remote host: Connection refused"},
        {"timestamp": now, "service": "product-reviews", "severity": "CRITICAL",
         "message": "OOM Killed: container product-reviews exceeded memory limit 512Mi, killed by kernel oom_kill_process"},
        # ── llm ──────────────────────────────────────────────────────────────
        {"timestamp": now, "service": "llm", "severity": "INFO",
         "message": "Received a chat completion request for product ID:OLJCESPC7Z"},
        {"timestamp": now, "service": "llm", "severity": "INFO",
         "message": "Received a chat completion request for product ID:L9ECAV7KIM"},
        {"timestamp": now, "service": "llm", "severity": "INFO",
         "message": "Returning a rate limit error"},
        {"timestamp": now, "service": "llm", "severity": "ERROR",
         "message": "Error: The file './product-review-summaries.json' was not found."},
        {"timestamp": now, "service": "llm", "severity": "ERROR",
         "message": "Error: The file './product-review-summaries.json' was not found."},
        {"timestamp": now, "service": "llm", "severity": "ERROR",
         "message": "An unexpected error occurred: [Errno 13] Permission denied: './product-review-summaries.json'"},
        {"timestamp": now, "service": "llm", "severity": "INFO",
         "message": "product_review_summary is: Customers love the build quality and fast charging."},
        {"timestamp": now, "service": "llm", "severity": "ERROR",
         "message": "Traceback (most recent call last): File 'app.py', line 111, in chat_completions product_id = parse_product_id(last_message) ValueError: product ID not found in input message"},
        {"timestamp": now, "service": "llm", "severity": "ERROR",
         "message": "Traceback (most recent call last): File 'app.py', line 111, in chat_completions product_id = parse_product_id(last_message) ValueError: product ID not found in input message"},
        {"timestamp": now, "service": "llm", "severity": "ERROR",
         "message": "5xx cascade: upstream connect error or disconnect/reset before headers. reset reason: connection termination"},
    ]


# ─────────────────────────────────────────────────────────────────────────────
# 2. Tiền xử lý log
# ─────────────────────────────────────────────────────────────────────────────

# Các pattern thay thế trước khi đưa vào Drain3 để tăng tỷ lệ gom nhóm
_PREPROCESS_PATTERNS = [
    (re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I), "<UUID>"),
    (re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?\b"), "<IP>"),
    (re.compile(r"\b[A-Z0-9]{10}\b"), "<PRODUCT_ID>"),         # product IDs kiểu OLJCESPC7Z
    (re.compile(r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?\b"), "<TIMESTAMP>"),
    (re.compile(r"\b\d+\.\d+\b"), "<FLOAT>"),
    (re.compile(r"\b\d+\b"), "<NUM>"),
]


def preprocess(message: str) -> str:
    """Chuẩn hóa log message để Drain3 gom cụm hiệu quả hơn."""
    msg = message.strip()
    for pattern, replacement in _PREPROCESS_PATTERNS:
        msg = pattern.sub(replacement, msg)
    return msg


# ─────────────────────────────────────────────────────────────────────────────
# 3. Drain3 – phân cụm log
# ─────────────────────────────────────────────────────────────────────────────

def build_drain3_miner(state_file: Optional[str] = None) -> TemplateMiner:
    """
    Khởi tạo Drain3 TemplateMiner.

    Nếu state_file đang tồn tại, load trạng thái cũ để duy trì tính liên tục
    giữa các lần chạy (incremental clustering).
    """
    config = TemplateMinerConfig()

    # ── Drain parameters ──────────────────────────────────────────────────────
    # sim_th: ngưỡng tương đồng (0.0 – 1.0). Cao = gom chặt, thấp = nhóm rộng.
    config.drain_sim_th = 0.5
    # max_children: số nhánh tối đa của cây prefix.
    config.drain_max_children = 100
    # max_clusters: giới hạn số template sinh ra.
    config.drain_max_clusters = 1000
    # Depth của prefix tree: giá trị cao giúp phân biệt tốt hơn.
    config.drain_depth = 4

    # ── Persistence ──────────────────────────────────────────────────────────
    if state_file and os.path.exists(state_file):
        config.snapshot_compress_state = True
        miner = TemplateMiner(config=config, context=state_file)
        logger.info(f"Loaded Drain3 state from: {state_file}")
    else:
        miner = TemplateMiner(config=config)
        logger.info("Initialized fresh Drain3 TemplateMiner")

    return miner


def cluster_logs(
    miner: TemplateMiner,
    logs: list[dict],
) -> tuple[list[dict], dict]:
    """
    Đưa tất cả log qua Drain3, thu về danh sách kết quả phân loại
    và bảng thống kê cluster.

    Returns:
        clustered_logs: mỗi bản ghi kèm cluster_id, template, is_new_template
        cluster_stats:  dict[cluster_id] -> {template, count, services, severities}
    """
    clustered_logs: list[dict] = []
    cluster_stats: dict[int, dict] = {}

    for entry in logs:
        raw_msg = entry["message"]
        normalized = preprocess(raw_msg)

        result = miner.add_log_message(normalized)
        cluster_id = result["cluster_id"]
        template = result["template_mined"]
        is_new = result["change_type"] in ("none", "cluster_created")
        is_new_template = result["change_type"] == "cluster_created"

        clustered_entry = {
            **entry,
            "normalized_message": normalized,
            "cluster_id": cluster_id,
            "template": template,
            "is_new_template": is_new_template,
        }
        clustered_logs.append(clustered_entry)

        # Cập nhật thống kê
        if cluster_id not in cluster_stats:
            cluster_stats[cluster_id] = {
                "template": template,
                "count": 0,
                "services": set(),
                "severities": set(),
                "first_seen": entry["timestamp"],
                "last_seen": entry["timestamp"],
                "sample_messages": [],
            }
        stats = cluster_stats[cluster_id]
        stats["count"] += 1
        stats["services"].add(entry.get("service", "unknown"))
        stats["severities"].add(entry.get("severity", "INFO"))
        stats["last_seen"] = entry["timestamp"]
        if len(stats["sample_messages"]) < 3:
            stats["sample_messages"].append(raw_msg)

    return clustered_logs, cluster_stats


# ─────────────────────────────────────────────────────────────────────────────
# 4. Phát hiện log template lỗi bất thường
# ─────────────────────────────────────────────────────────────────────────────

def _is_error_template(template: str, severities: set[str]) -> bool:
    """Kiểm tra một cluster có phải là lỗi nghiêm trọng không."""
    template_lower = template.lower()
    has_error_keyword = any(kw.lower() in template_lower for kw in ALERT_KEYWORDS)
    has_error_severity = bool(severities & {"ERROR", "CRITICAL", "FATAL"})
    return has_error_keyword or has_error_severity


def detect_anomalies(
    cluster_stats: dict,
    new_template_ids: set[int],
) -> list[dict]:
    """
    Phát hiện các cluster bất thường theo 2 tiêu chí:
      1. Template MỚI (chưa từng thấy) + chứa từ khóa lỗi → alert "NEW_ERROR_TEMPLATE"
      2. Template CŨ nhưng tần suất tăng đột biến (count > threshold) → alert "SPIKE"

    Returns:
        Danh sách alert dict
    """
    alerts: list[dict] = []
    SPIKE_THRESHOLD = int(os.getenv("SPIKE_THRESHOLD", "5"))

    for cid, stats in cluster_stats.items():
        template = stats["template"]
        severities = stats["severities"]
        count = stats["count"]

        is_new = cid in new_template_ids
        is_error = _is_error_template(template, severities)

        if is_new and is_error:
            alerts.append({
                "alert_type": "NEW_ERROR_TEMPLATE",
                "cluster_id": cid,
                "template": template,
                "count": count,
                "services": list(stats["services"]),
                "severities": list(severities),
                "first_seen": stats["first_seen"],
                "sample_message": stats["sample_messages"][0] if stats["sample_messages"] else "",
                "description": (
                    f"⚠️  [NEW_ERROR_TEMPLATE] Phát hiện log template lỗi MỚI CHƯA TỪNG THẤY "
                    f"trong service {list(stats['services'])}. "
                    f"Template: \"{template}\". "
                    f"Xuất hiện {count} lần. Kiểm tra ngay!"
                ),
            })
        elif not is_new and is_error and count >= SPIKE_THRESHOLD:
            alerts.append({
                "alert_type": "ERROR_SPIKE",
                "cluster_id": cid,
                "template": template,
                "count": count,
                "services": list(stats["services"]),
                "severities": list(severities),
                "first_seen": stats["first_seen"],
                "sample_message": stats["sample_messages"][0] if stats["sample_messages"] else "",
                "description": (
                    f"🔥 [ERROR_SPIKE] Template lỗi đã biết xuất hiện {count} lần "
                    f"(ngưỡng = {SPIKE_THRESHOLD}) trong service {list(stats['services'])}. "
                    f"Template: \"{template}\""
                ),
            })

    return alerts


# ─────────────────────────────────────────────────────────────────────────────
# 5. Xuất kết quả
# ─────────────────────────────────────────────────────────────────────────────

def print_cluster_report(cluster_stats: dict, alerts: list[dict]) -> None:
    """In báo cáo tóm tắt ra stdout."""
    print("\n" + "=" * 80)
    print("  DRAIN3 LOG CLUSTERING REPORT")
    print("=" * 80)
    print(f"  Tổng số cluster phát hiện: {len(cluster_stats)}")
    print(f"  Tổng số alert:             {len(alerts)}")
    print("=" * 80)

    print("\n📋 DANH SÁCH TẤT CẢ CLUSTER:\n")
    for cid, stats in sorted(cluster_stats.items()):
        sev_str = ", ".join(sorted(stats["severities"]))
        svc_str = ", ".join(sorted(stats["services"]))
        print(f"  [Cluster {cid:>4}]  count={stats['count']:<5}  sev={sev_str:<15}  svc={svc_str}")
        print(f"              template: {stats['template']}")
        print()

    if alerts:
        print("\n🚨 ALERTS – CẦN XEM XÉT NGAY:\n")
        for alert in alerts:
            print(f"  {'─' * 76}")
            print(f"  {alert['description']}")
            print(f"  Sample: {alert['sample_message'][:120]}")
        print(f"  {'─' * 76}\n")
    else:
        print("\n✅ Không phát hiện anomaly trong cửa sổ thời gian này.\n")


def save_results(cluster_stats: dict, alerts: list[dict], output_path: str) -> None:
    """Lưu kết quả ra file JSON để tích hợp với pipeline cảnh báo."""
    # Serialize set → list để JSON serialize được
    serializable_stats = {}
    for cid, stats in cluster_stats.items():
        serializable_stats[str(cid)] = {
            **stats,
            "services": list(stats["services"]),
            "severities": list(stats["severities"]),
        }

    output = {
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "lookback_minutes": LOOKBACK_MINUTES,
        "target_services": TARGET_SERVICES,
        "total_clusters": len(cluster_stats),
        "total_alerts": len(alerts),
        "clusters": serializable_stats,
        "alerts": alerts,
    }

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    logger.info(f"Results saved to: {output_path}")

    # Export to CSV files (top_templates.csv and template_counts.csv)
    import csv
    results_dir = os.path.dirname(output_path) or "."
    sorted_clusters = sorted(cluster_stats.items(), key=lambda x: x[1]["count"], reverse=True)

    # 1. template_counts.csv
    template_counts_path = os.path.join(results_dir, "template_counts.csv")
    try:
        with open(template_counts_path, "w", encoding="utf-8", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["cluster_id", "template", "count", "services", "severities"])
            for cid, stat in sorted_clusters:
                writer.writerow([
                    cid,
                    stat["template"],
                    stat["count"],
                    ",".join(stat["services"]),
                    ",".join(stat["severities"])
                ])
        logger.info(f"Exported template counts to {template_counts_path}")
    except Exception as e:
        logger.error(f"Error exporting template_counts.csv: {e}")

    # 2. top_templates.csv
    top_templates_path = os.path.join(results_dir, "top_templates.csv")
    try:
        with open(top_templates_path, "w", encoding="utf-8", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["rank", "cluster_id", "count", "template"])
            for rank, (cid, stat) in enumerate(sorted_clusters[:10], 1):
                writer.writerow([
                    rank,
                    cid,
                    stat["count"],
                    stat["template"]
                ])
        logger.info(f"Exported top templates to {top_templates_path}")
    except Exception as e:
        logger.error(f"Error exporting top_templates.csv: {e}")



# ─────────────────────────────────────────────────────────────────────────────
# 6. Entrypoint
# ─────────────────────────────────────────────────────────────────────────────

def run(output_path: str = "results/log_clustering_report.json") -> list[dict]:
    """
    Pipeline chính:
      1. Lấy log từ OpenSearch (hoặc sample nếu không kết nối được)
      2. Tiền xử lý
      3. Phân cụm với Drain3
      4. Phát hiện anomaly
      5. Xuất report

    Returns:
        Danh sách alerts (dùng khi gọi từ pipeline khác)
    """
    logger.info(f"Starting log clustering | services={TARGET_SERVICES} | window={LOOKBACK_MINUTES}m")

    # ── Bước 1: Fetch logs ──────────────────────────────────────────────────
    try:
        client = build_opensearch_client()
        logs = fetch_logs_from_opensearch(client, TARGET_SERVICES, LOOKBACK_MINUTES)
    except Exception as e:
        logger.warning(f"Could not connect to OpenSearch ({e}), using sample logs.")
        logs = _get_sample_logs()

    if not logs:
        logger.info("No logs found in the time window. Exiting.")
        return []

    logger.info(f"Processing {len(logs)} log entries...")

    # ── Bước 2: Drain3 miner ────────────────────────────────────────────────
    miner = build_drain3_miner(state_file=STATE_FILE if os.path.exists(STATE_FILE) else None)

    # Ghi nhận cluster_id đang tồn tại TRƯỚC khi add log
    existing_cluster_ids = set(c.cluster_id for c in miner.drain.id_to_cluster.values())

    # ── Bước 3: Phân cụm ────────────────────────────────────────────────────
    clustered_logs, cluster_stats = cluster_logs(miner, logs)

    # Template MỚI = cluster_id chưa có trước bước 3
    new_template_ids = set(cluster_stats.keys()) - existing_cluster_ids

    logger.info(
        f"Clustering complete: {len(cluster_stats)} clusters total, "
        f"{len(new_template_ids)} new templates"
    )

    # ── Bước 4: Anomaly detection ────────────────────────────────────────────
    alerts = detect_anomalies(cluster_stats, new_template_ids)

    # ── Bước 5: Xuất kết quả ────────────────────────────────────────────────
    print_cluster_report(cluster_stats, alerts)
    save_results(cluster_stats, alerts, output_path)

    # Lưu state Drain3 cho lần chạy tiếp theo (incremental)
    try:
        miner.save_state(STATE_FILE)
        logger.info(f"Drain3 state saved to: {STATE_FILE}")
    except Exception as e:
        logger.warning(f"Could not save Drain3 state: {e}")

    return alerts


if __name__ == "__main__":
    import sys
    output = sys.argv[1] if len(sys.argv) > 1 else "results/log_clustering_report.json"
    alerts = run(output_path=output)
    # Exit code non-zero khi có alert (hữu ích cho CI/CD pipeline)
    sys.exit(1 if alerts else 0)
