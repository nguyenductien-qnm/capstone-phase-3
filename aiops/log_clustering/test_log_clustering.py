#!/usr/bin/env python3
"""
Test suite cho Log Clustering module (Drain3).
Chạy: python -m pytest test_log_clustering.py -v
"""

import json
import os
import sys
import tempfile
import pytest

# Thêm thư mục cha vào path để import module
sys.path.insert(0, os.path.dirname(__file__))

from log_clustering import (
    preprocess,
    build_drain3_miner,
    cluster_logs,
    detect_anomalies,
    _get_sample_logs,
    _is_error_template,
    save_results,
    ALERT_KEYWORDS,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def fresh_miner():
    """Luôn trả về miner mới không có state cũ."""
    return build_drain3_miner(state_file=None)


@pytest.fixture
def sample_logs():
    return _get_sample_logs()


# ─────────────────────────────────────────────────────────────────────────────
# Tests: preprocess()
# ─────────────────────────────────────────────────────────────────────────────

class TestPreprocess:

    def test_replaces_ip_address(self):
        msg = "Connection refused to 10.0.1.5:5432"
        result = preprocess(msg)
        assert "10.0.1.5" not in result
        assert "<IP>" in result

    def test_replaces_product_id(self):
        msg = "Receive GetProductReviews for product id:OLJCESPC7Z"
        result = preprocess(msg)
        # Product ID 10 ký tự IN HOA số sẽ bị thay
        assert "OLJCESPC7Z" not in result
        assert "<PRODUCT_ID>" in result

    def test_replaces_numbers(self):
        msg = "Error code: 429 - Rate limit reached after 3 retries"
        result = preprocess(msg)
        assert "429" not in result
        assert "3" not in result
        assert "<NUM>" in result

    def test_preserves_keywords(self):
        msg = "ERROR: connection failed"
        result = preprocess(msg)
        # Keyword "ERROR" phải giữ nguyên
        assert "ERROR" in result
        assert "connection" in result

    def test_empty_string(self):
        assert preprocess("") == ""

    def test_replaces_uuid(self):
        msg = "Request ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890 failed"
        result = preprocess(msg)
        assert "a1b2c3d4-e5f6-7890-abcd-ef1234567890" not in result
        assert "<UUID>" in result


# ─────────────────────────────────────────────────────────────────────────────
# Tests: cluster_logs() – Drain3
# ─────────────────────────────────────────────────────────────────────────────

class TestClusterLogs:

    def test_clusters_similar_logs_together(self, fresh_miner):
        """Các log cùng pattern phải vào cùng một cluster."""
        logs = [
            {"timestamp": "t1", "service": "product-reviews", "severity": "INFO",
             "message": "Receive GetProductReviews for product id:OLJCESPC7Z"},
            {"timestamp": "t2", "service": "product-reviews", "severity": "INFO",
             "message": "Receive GetProductReviews for product id:L9ECAV7KIM"},
            {"timestamp": "t3", "service": "product-reviews", "severity": "INFO",
             "message": "Receive GetProductReviews for product id:2ZYFJ3GM2N"},
        ]
        _, cluster_stats = cluster_logs(fresh_miner, logs)
        # Cả 3 dòng phải thuộc cùng 1 cluster
        assert len(cluster_stats) == 1
        cid = list(cluster_stats.keys())[0]
        assert cluster_stats[cid]["count"] == 3

    def test_different_logs_in_different_clusters(self, fresh_miner):
        """Log hoàn toàn khác biệt phải vào các cluster riêng."""
        logs = [
            {"timestamp": "t1", "service": "product-reviews", "severity": "ERROR",
             "message": "ERROR: connection to postgresql failed"},
            {"timestamp": "t2", "service": "llm", "severity": "INFO",
             "message": "Received a chat completion request"},
        ]
        _, cluster_stats = cluster_logs(fresh_miner, logs)
        assert len(cluster_stats) == 2

    def test_cluster_stats_has_correct_service(self, fresh_miner):
        """cluster_stats phải ghi đúng service nguồn."""
        logs = [
            {"timestamp": "t1", "service": "llm", "severity": "INFO",
             "message": "llmInaccurateResponse feature flag: True"},
        ]
        _, cluster_stats = cluster_logs(fresh_miner, logs)
        assert len(cluster_stats) == 1
        stats = list(cluster_stats.values())[0]
        assert "llm" in stats["services"]

    def test_cluster_stats_has_correct_severity(self, fresh_miner):
        """cluster_stats phải ghi đúng severity."""
        logs = [
            {"timestamp": "t1", "service": "product-reviews", "severity": "ERROR",
             "message": "Caught Exception: Error code: 429 - Rate limit reached"},
        ]
        _, cluster_stats = cluster_logs(fresh_miner, logs)
        stats = list(cluster_stats.values())[0]
        assert "ERROR" in stats["severities"]

    def test_error_rate_limit_logs_cluster_together(self, fresh_miner):
        """Các lỗi 429 lặp lại nhiều lần phải về cùng 1 cluster."""
        logs = [
            {"timestamp": "t1", "service": "product-reviews", "severity": "ERROR",
             "message": "Caught Exception: Error code: 429 - Rate limit reached. Please try again later."},
            {"timestamp": "t2", "service": "product-reviews", "severity": "ERROR",
             "message": "Caught Exception: Error code: 429 - Rate limit reached. Please try again later."},
            {"timestamp": "t3", "service": "product-reviews", "severity": "ERROR",
             "message": "Caught Exception: Error code: 429 - Rate limit reached. Please try again later."},
        ]
        _, cluster_stats = cluster_logs(fresh_miner, logs)
        # Tất cả phải là 1 cluster, count = 3
        assert len(cluster_stats) == 1
        stats = list(cluster_stats.values())[0]
        assert stats["count"] == 3

    def test_empty_logs_returns_empty(self, fresh_miner):
        """Input rỗng phải trả về cấu trúc rỗng."""
        clustered, stats = cluster_logs(fresh_miner, [])
        assert clustered == []
        assert stats == {}

    def test_sample_logs_produce_multiple_clusters(self, fresh_miner, sample_logs):
        """Sample logs đa dạng phải sinh ra nhiều cluster."""
        _, cluster_stats = cluster_logs(fresh_miner, sample_logs)
        assert len(cluster_stats) >= 5  # nhiều loại log khác nhau

    def test_new_template_detected_on_first_run(self, fresh_miner):
        """Khi miner hoàn toàn mới, mọi log đầu tiên đều là new template."""
        existing_ids = set(c.cluster_id for c in fresh_miner.drain.id_to_cluster.values())
        logs = [
            {"timestamp": "t1", "service": "llm", "severity": "ERROR",
             "message": "Error: The file './product-review-summaries.json' was not found."},
        ]
        _, cluster_stats = cluster_logs(fresh_miner, logs)
        new_ids = set(cluster_stats.keys()) - existing_ids
        assert len(new_ids) == 1


# ─────────────────────────────────────────────────────────────────────────────
# Tests: detect_anomalies()
# ─────────────────────────────────────────────────────────────────────────────

class TestDetectAnomalies:

    def _make_stats(self, template, count, severities, services, is_new):
        cid = 1
        stats = {
            cid: {
                "template": template,
                "count": count,
                "severities": set(severities),
                "services": set(services),
                "first_seen": "2026-07-09T00:00:00Z",
                "last_seen": "2026-07-09T00:00:00Z",
                "sample_messages": [f"sample of {template}"],
            }
        }
        new_ids = {cid} if is_new else set()
        return stats, new_ids

    def test_new_error_template_triggers_alert(self):
        """Template lỗi MỚI phải sinh ra alert NEW_ERROR_TEMPLATE."""
        stats, new_ids = self._make_stats(
            "ERROR connection to postgresql failed",
            count=2, severities=["ERROR"], services=["product-reviews"], is_new=True
        )
        alerts = detect_anomalies(stats, new_ids)
        assert len(alerts) == 1
        assert alerts[0]["alert_type"] == "NEW_ERROR_TEMPLATE"

    def test_oom_new_template_triggers_alert(self):
        """OOM template mới phải bị phát hiện."""
        stats, new_ids = self._make_stats(
            "OOM Killed container product-reviews exceeded memory limit",
            count=1, severities=["CRITICAL"], services=["product-reviews"], is_new=True
        )
        alerts = detect_anomalies(stats, new_ids)
        assert any(a["alert_type"] == "NEW_ERROR_TEMPLATE" for a in alerts)

    def test_new_info_template_no_alert(self):
        """Template INFO mới không phải lỗi → không sinh alert."""
        stats, new_ids = self._make_stats(
            "Receive GetProductReviews for product id <PRODUCT_ID>",
            count=5, severities=["INFO"], services=["product-reviews"], is_new=True
        )
        alerts = detect_anomalies(stats, new_ids)
        assert len(alerts) == 0

    def test_old_error_template_spike_triggers_alert(self):
        """Template lỗi CŨ tần suất cao phải sinh alert ERROR_SPIKE."""
        stats, new_ids = self._make_stats(
            "Caught Exception Error code <NUM> Rate limit reached",
            count=10, severities=["ERROR"], services=["product-reviews"], is_new=False
        )
        alerts = detect_anomalies(stats, new_ids)
        assert len(alerts) == 1
        assert alerts[0]["alert_type"] == "ERROR_SPIKE"

    def test_old_error_template_low_count_no_alert(self):
        """Template lỗi cũ nhưng tần suất thấp (< threshold) không bị alert."""
        stats, new_ids = self._make_stats(
            "Caught Exception Error code <NUM> Rate limit reached",
            count=2, severities=["ERROR"], services=["product-reviews"], is_new=False
        )
        # threshold mặc định là 5
        os.environ["SPIKE_THRESHOLD"] = "5"
        alerts = detect_anomalies(stats, new_ids)
        assert len(alerts) == 0

    def test_no_logs_no_alerts(self):
        """Không có cluster → không có alert."""
        alerts = detect_anomalies({}, set())
        assert alerts == []

    def test_5xx_template_triggers_alert(self):
        """Log 5xx cascade phải bị phát hiện."""
        stats, new_ids = self._make_stats(
            "5xx cascade upstream connect error or disconnect",
            count=3, severities=["ERROR"], services=["llm"], is_new=True
        )
        alerts = detect_anomalies(stats, new_ids)
        assert len(alerts) >= 1


# ─────────────────────────────────────────────────────────────────────────────
# Tests: _is_error_template()
# ─────────────────────────────────────────────────────────────────────────────

class TestIsErrorTemplate:

    def test_detects_error_keyword_in_template(self):
        assert _is_error_template("ERROR connection failed", {"INFO"}) is True

    def test_detects_oom_in_template(self):
        assert _is_error_template("OOM Killed container", {"CRITICAL"}) is True

    def test_detects_timeout_in_template(self):
        assert _is_error_template("connection timeout after <NUM> ms", {"ERROR"}) is True

    def test_detects_by_severity(self):
        assert _is_error_template("Something happened", {"ERROR"}) is True

    def test_normal_template_not_error(self):
        assert _is_error_template("Receive GetProductReviews for product id", {"INFO"}) is False

    def test_critical_severity_triggers(self):
        assert _is_error_template("Memory usage high", {"CRITICAL"}) is True


# ─────────────────────────────────────────────────────────────────────────────
# Tests: save_results()
# ─────────────────────────────────────────────────────────────────────────────

class TestSaveResults:

    def test_saves_json_file(self, fresh_miner, sample_logs):
        _, cluster_stats = cluster_logs(fresh_miner, sample_logs)
        alerts = [{"alert_type": "TEST", "cluster_id": 1, "template": "test"}]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "report.json")
            save_results(cluster_stats, alerts, output_path)

            assert os.path.exists(output_path)
            with open(output_path, "r") as f:
                data = json.load(f)

            assert "clusters" in data
            assert "alerts" in data
            assert data["total_alerts"] == 1
            assert data["total_clusters"] == len(cluster_stats)

    def test_output_is_valid_json(self, fresh_miner, sample_logs):
        _, cluster_stats = cluster_logs(fresh_miner, sample_logs)
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "report.json")
            save_results(cluster_stats, [], output_path)
            with open(output_path, "r") as f:
                data = json.load(f)  # không ném exception = valid JSON
            assert isinstance(data, dict)


# ─────────────────────────────────────────────────────────────────────────────
# Integration test: full pipeline
# ─────────────────────────────────────────────────────────────────────────────

class TestFullPipeline:

    def test_sample_logs_detect_alerts(self, fresh_miner, sample_logs):
        """
        Với sample logs (chứa nhiều lỗi OOM, DB timeout, 429),
        pipeline phải phát hiện ít nhất 1 alert.
        """
        existing_ids = set(c.cluster_id for c in fresh_miner.drain.id_to_cluster.values())
        _, cluster_stats = cluster_logs(fresh_miner, sample_logs)
        new_ids = set(cluster_stats.keys()) - existing_ids
        alerts = detect_anomalies(cluster_stats, new_ids)
        assert len(alerts) >= 1, "Phải phát hiện ít nhất 1 alert với sample logs lỗi"

    def test_rate_limit_errors_detected(self, fresh_miner):
        """Lỗi 429 từ llm phải bị phát hiện là anomaly."""
        logs = [
            {"timestamp": "t1", "service": "product-reviews", "severity": "ERROR",
             "message": "Caught Exception: Error code: 429 - Rate limit reached. Please try again later."},
            {"timestamp": "t2", "service": "product-reviews", "severity": "ERROR",
             "message": "Caught Exception: Error code: 503 - Service unavailable. Please try again."},
            {"timestamp": "t3", "service": "product-reviews", "severity": "ERROR",
             "message": "Caught Exception: Error code: 429 - Rate limit reached. Please try again later."},
        ]
        existing_ids = set(c.cluster_id for c in fresh_miner.drain.id_to_cluster.values())
        _, cluster_stats = cluster_logs(fresh_miner, logs)
        new_ids = set(cluster_stats.keys()) - existing_ids
        alerts = detect_anomalies(cluster_stats, new_ids)
        alert_types = [a["alert_type"] for a in alerts]
        assert "NEW_ERROR_TEMPLATE" in alert_types

    def test_incremental_clustering_recognizes_old_template(self):
        """Chạy pipeline 2 lần: lần 2 không được coi log cũ là template mới."""
        miner = build_drain3_miner(state_file=None)
        logs_round1 = [
            {"timestamp": "t1", "service": "product-reviews", "severity": "ERROR",
             "message": "ERROR: connection to postgresql failed FATAL slots reserved"},
        ]
        existing_ids = set(c.cluster_id for c in miner.drain.id_to_cluster.values())
        _, stats1 = cluster_logs(miner, logs_round1)
        new_ids_r1 = set(stats1.keys()) - existing_ids

        # Lần 2: cùng loại log
        logs_round2 = [
            {"timestamp": "t2", "service": "product-reviews", "severity": "ERROR",
             "message": "ERROR: connection to postgresql failed FATAL slots reserved"},
        ]
        existing_before_r2 = set(c.cluster_id for c in miner.drain.id_to_cluster.values())
        _, stats2 = cluster_logs(miner, logs_round2)
        new_ids_r2 = set(stats2.keys()) - existing_before_r2

        # Template cũ không phải new trong lần 2
        assert len(new_ids_r2) == 0, "Log quen thuộc không nên là new_template ở lần chạy 2"
