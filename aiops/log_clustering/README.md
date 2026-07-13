# Log Clustering - Drain3

Module AIOps phân cụm log thô từ các service GenAI (`product-reviews`, `llm`) bằng thuật toán **Drain3**, phát hiện nhanh log template lỗi mới lạ và tần suất lỗi tăng đột biến.

> **Task:** [AIOps-W1-T4] / Backlog item TF1-52  
> **Team:** AIO03 – TF1  
> **Trụ:** Observability / AIOps

---

## Vấn đề cần giải quyết

Khi hệ thống có sự cố (OOM, DB connection timeout, LLM 429 rate limit), log thô từ OpenSearch có thể lên tới **hàng nghìn dòng mỗi phút**. Không thể đọc thủ công và rất dễ bỏ sót culprit thực sự.

**Drain3 Log Clustering** giải quyết bằng cách:
1. **Gom** hàng nghìn log dòng → **vài chục template** đặc trưng.
2. **Phát hiện** template lỗi *chưa từng thấy* (dấu hiệu sự cố mới bắt đầu).
3. **Cảnh báo** khi một template lỗi đã biết tăng đột biến tần suất.

---

## Kiến trúc

```
OpenSearch (logs)
        │
        ▼ fetch (rolling window, mặc định 60 phút)
   Raw Log Entries  [service, severity, message]
        │
        ▼ preprocess()   — chuẩn hóa: thay IP/ID/số → token
   Normalized Messages
        │
        ▼ Drain3 TemplateMiner.add_log_message()
   Clustered Logs   [cluster_id, template, is_new_template]
        │
        ▼ detect_anomalies()
   Alerts           [NEW_ERROR_TEMPLATE | ERROR_SPIKE]
        │
        ▼ stdout report + results/log_clustering_report.json
```

---

## Cài đặt

```bash
cd aiops/log_clustering
pip install -r requirements.txt
```

---

## Chạy nhanh (offline – dùng sample logs)

```bash
python log_clustering.py
```

Kết quả xuất ra `results/log_clustering_report.json`.

---

## Chạy với OpenSearch thật

```bash
export OPENSEARCH_HOST=<host>
export OPENSEARCH_PORT=9200
export OPENSEARCH_USER=admin
export OPENSEARCH_PASS=<password>
export LOOKBACK_MINUTES=60
export TARGET_SERVICES=product-reviews,llm
export STATE_FILE=/tmp/drain3_state.bin   # incremental state

python log_clustering.py results/report.json
```

### Biến môi trường

| Biến | Mặc định | Mô tả |
|---|---|---|
| `OPENSEARCH_HOST` | `localhost` | Host OpenSearch |
| `OPENSEARCH_PORT` | `9200` | Port |
| `OPENSEARCH_USER` | `admin` | Username |
| `OPENSEARCH_PASS` | `admin` | Password |
| `OPENSEARCH_INDEX_PATTERN` | `otel-v1-apm-service-*` | Index OTel |
| `LOOKBACK_MINUTES` | `60` | Cửa sổ thời gian nhìn ngược |
| `TARGET_SERVICES` | `product-reviews,llm` | Service cần giám sát |
| `STATE_FILE` | `/tmp/drain3_state.bin` | File lưu state Drain3 (incremental) |
| `SPIKE_THRESHOLD` | `5` | Số lần xuất hiện kích hoạt alert SPIKE |

---

## Chạy tests

```bash
pip install pytest
pytest test_log_clustering.py -v
```

### Coverage các case quan trọng:
- `preprocess()`: chuẩn hóa IP, Product ID, số, UUID
- `cluster_logs()`: gom các log tương đồng vào cùng cluster; log khác nhau vào cluster khác
- `detect_anomalies()`: phát hiện NEW_ERROR_TEMPLATE, ERROR_SPIKE, bỏ qua INFO
- `_is_error_template()`: phân loại đúng template lỗi
- Integration: pipeline đầu-cuối với sample logs
- Incremental: chạy lần 2 không coi log cũ là new template

---

## Loại Alert

| Alert Type | Khi nào | Hành động gợi ý |
|---|---|---|
| `NEW_ERROR_TEMPLATE` | Template lỗi chưa từng xuất hiện trong cửa sổ thời gian | Kiểm tra ngay log gốc, xác định culprit service |
| `ERROR_SPIKE` | Template lỗi đã biết xuất hiện ≥ `SPIKE_THRESHOLD` lần | Kiểm tra tần suất, xem xét escalate on-call |

---

## Tích hợp vào pipeline AIOps

Module này có thể được gọi từ vòng lặp AIOps auto-remediation:

```python
from aiops.log_clustering.log_clustering import run

alerts = run(output_path="results/report.json")
if alerts:
    # Gửi alert lên Slack / PagerDuty
    # Kích hoạt bước kiểm tra an toàn (dry-run)
    for alert in alerts:
        handle_alert(alert)
```

Exit code = `1` nếu có alert (để CI/CD pipeline bắt được).

---

## Cấu trúc output JSON

```json
{
  "generated_at": "2026-07-09T02:00:00Z",
  "lookback_minutes": 60,
  "target_services": ["product-reviews", "llm"],
  "total_clusters": 8,
  "total_alerts": 2,
  "clusters": {
    "1": {
      "template": "ERROR connection to postgresql <IP> port <NUM> failed",
      "count": 5,
      "services": ["product-reviews"],
      "severities": ["ERROR"],
      "first_seen": "...",
      "sample_messages": ["ERROR: connection to..."]
    }
  },
  "alerts": [
    {
      "alert_type": "NEW_ERROR_TEMPLATE",
      "cluster_id": 3,
      "template": "OOM Killed container product-reviews exceeded memory limit <NUM>",
      "count": 1,
      "services": ["product-reviews"],
      "description": "⚠️ [NEW_ERROR_TEMPLATE] ..."
    }
  ]
}
```

---

## Drain3 parameters

| Param | Giá trị | Ý nghĩa |
|---|---|---|
| `sim_th` | `0.4` | Ngưỡng tương đồng để gộp cluster (0=rất rộng, 1=rất chặt) |
| `max_children` | `100` | Số nhánh tối đa của prefix tree |
| `max_clusters` | `1000` | Số template tối đa |
| `depth` | `4` | Độ sâu prefix tree |

> Chỉnh `sim_th` lên cao nếu muốn template chặt hơn (ít nhầm hơn); hạ xuống nếu muốn gom rộng hơn (ít alert nhiễu hơn).

---

## Tham khảo

- [Drain3 GitHub](https://github.com/logpai/Drain3)
- Paper gốc: *Drain: An Online Log Parsing Approach with Fixed Depth Tree* (He et al., ICWS 2017)
- Spec AIOps: [docs/ai/03_specs/anomaly_remediation.md](../../docs/ai/03_specs/anomaly_remediation.md)
