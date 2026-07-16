# TF1-53 [AIOps-W1-T5] - Clients doc telemetry co san (CHI DOC, khong ghi).
# Prometheus HTTP API + OpenSearch _search. Khong dung SDK nang, chi requests.
import math
import logging
import requests

log = logging.getLogger("aiops.sources")


class PrometheusClient:
    """Query Prometheus instant API. Tra ve danh sach series (value, labels)."""

    def __init__(self, base_url, timeout=5):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def query(self, promql):
        """Chay 1 PromQL instant query.

        Return: list[(float value, dict labels)]. Bo qua NaN/Inf.
        Nem exception neu goi API that bai -> detector se log & tiep tuc.
        """
        resp = requests.get(
            f"{self.base_url}/api/v1/query",
            params={"query": promql},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("status") != "success":
            raise RuntimeError(f"Prometheus tra loi khong success: {payload.get('error')}")

        results = []
        for series in payload["data"].get("result", []):
            raw = series.get("value", [None, None])[1]
            try:
                value = float(raw)
            except (TypeError, ValueError):
                continue
            if math.isnan(value) or math.isinf(value):
                continue
            results.append((value, series.get("metric", {})))
        return results


class OpenSearchClient:
    """Dem log khop cum tu (match_phrase) trong 1 cua so thoi gian."""

    def __init__(self, base_url, index="otel-logs-*",
                 message_field="body", time_field="observedTimestamp", timeout=5):
        self.base_url = base_url.rstrip("/")
        self.index = index
        self.message_field = message_field
        self.time_field = time_field
        self.timeout = timeout

    def count_matches(self, phrases, window_minutes):
        """Dem log co message chua BAT KY phrase nao trong `phrases` (OR), trong
        `window_minutes` phut gan nhat.

        `phrases`: str hoac list[str].
        Return: (int count, str sample_message | None).
        """
        if isinstance(phrases, str):
            phrases = [phrases]
        should = [{"match_phrase": {self.message_field: p}} for p in phrases]
        body = {
            "size": 1,  # lay 1 sample de dua vao alert cho de chan doan
            "track_total_hits": True,
            "query": {
                "bool": {
                    "must": [
                        {"range": {self.time_field: {"gte": f"now-{window_minutes}m"}}},
                    ],
                    "should": should,
                    "minimum_should_match": 1,
                }
            },
            "sort": [{self.time_field: {"order": "desc"}}],
        }
        resp = requests.post(
            f"{self.base_url}/{self.index}/_search",
            json=body,
            timeout=self.timeout,
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()

        total = data.get("hits", {}).get("total", 0)
        if isinstance(total, dict):  # OpenSearch/ES 7+ tra ve {"value": N}
            total = total.get("value", 0)

        sample = None
        hits = data.get("hits", {}).get("hits", [])
        if hits:
            src = hits[0].get("_source", {})
            sample = src.get(self.message_field)
        return int(total), sample
