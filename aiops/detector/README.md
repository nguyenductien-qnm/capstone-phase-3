# AIOps Error-Detection & Alerting — TF1-53 [AIOps-W1-T5]

Script/tool phát hiện lỗi vận hành và gửi cảnh báo cho on-call. Đây là mắt **"Monitor / Trigger"** — cửa vào của closed-loop trong [`docs/ai/specs/anomaly_remediation.md`](../../docs/ai/specs/anomaly_remediation.md).

> **Phạm vi:** CHỈ phát hiện + cảnh báo. **Không** tự khắc phục (đó là TF1-50 Remediation). **Không** gỡ/đổi hướng flagd (vi phạm = disqualify).

## Nó làm gì

Mỗi `poll_interval_seconds`, đọc telemetry **có sẵn** rồi bắn alert nếu vượt ngưỡng:

| Nguồn | Tín hiệu phát hiện |
|---|---|
| **Prometheus** (metric) | p95 latency > 1s · 5xx error rate > 0.5% · checkout error > 1% |
| **OpenSearch** (log) | LLM 429 (`llmRateLimitError`) · DB pool cạn (INC-1) · OOM (INC-2) · DNS error |

Ngưỡng bám `onboarding/SLO.md`. Rule khai trong [`rules.yaml`](rules.yaml) — thêm/sửa tín hiệu không cần đụng code.

## Kiến trúc

```
rules.yaml ─► detector.py ─┬─► sources.PrometheusClient ─► GET /api/v1/query
                           ├─► sources.OpenSearchClient ─► POST otel-logs-*/_search
                           └─► alerter.Alerter ─► Slack/Discord webhook (dedup + cooldown)
```

- **Config-driven:** mọi ngưỡng/keyword ở `rules.yaml`.
- **Dedup + cooldown:** cùng 1 rule + 1 service tối đa 1 alert / `cooldown_seconds` → không spam on-call.
- **Không hardcode secret:** URL + webhook đọc từ env (xem `.env.example`).
- **Không tự sập:** lỗi 1 nguồn được log và bỏ qua, vòng lặp vẫn sống.

## Chạy (Tuần 1 — local)

```sh
pip install -r requirements.txt

# Trỏ tới stack đang chạy (docker-compose ps để lấy port, hoặc kubectl port-forward)
export PROM_URL=http://localhost:9090
export OPENSEARCH_URL=http://localhost:9200
export ALERT_WEBHOOK_URL=<slack-hoặc-discord-webhook>   # để trống -> in ra stdout

python detector.py            # chạy liên tục
python detector.py --once     # 1 vòng rồi thoát (test/CI)
python detector.py --dry-run  # in alert ra stdout, không gọi webhook
```

Với EKS:
```sh
kubectl -n <ns> port-forward svc/prometheus 9090:9090 &
kubectl -n <ns> port-forward svc/opensearch 9200:9200 &
```

## Test end-to-end (tạo số MTTD cho pitch/ops-review)

1. Dựng hệ thống + chạy `load-generator` để có traffic.
2. **Kích sự cố thật qua flagd** — bật `llmRateLimitError` (local: flagd-ui, hoặc sửa `demo.flagd.json` **ở local của bạn**). KHÔNG đụng nguồn flag central trên EKS.
3. `product-reviews` bắt đầu trả 429 → log vào OpenSearch → detector bắt rule `llm-rate-limit-429` → **alert bắn ra**.
4. Ghi **MTTD** = thời gian từ lúc bật flag đến lúc alert. Chụp màn hình alert.
5. **Tắt lại flag ở local** sau khi test.

Kiểm tra nhanh không cần webhook:
```sh
python detector.py --once --dry-run
```

## Deploy in-cluster (Tuần 2)

```sh
docker build -t <ECR>/techx-corp:1.0-aiops-detector .
docker push <ECR>/techx-corp:1.0-aiops-detector
kubectl -n <ns> create secret generic aiops-alert --from-literal=webhook=<webhook-url>
kubectl -n <ns> apply -f deploy/deployment.yaml
```

## Ranh giới với các task AIOps khác

| Task | Quan hệ |
|---|---|
| TF1-49 Golden Signal (EWMA) | Nâng cấp ngưỡng tĩnh → EWMA α=0.2, 3σ (thay `threshold` ở rule metric) |
| TF1-52 Drain3 Log Clustering | Nâng cấp rule log keyword → gom cụm template lạ |
| TF1-50 Remediation | Nhận alert từ tool này làm đầu vào cho vòng tự khắc phục |
| TF1-51 Telemetry Audit | Đảm bảo metric/log tool này query không bị đứt đoạn |

## Lưu ý field/metric (đã verify với repo)

- Prometheus: `http://prometheus:9090`, metric `http_server_request_duration_seconds_*`, label `service_namespace="techx-corp"`, `service_name`.
- OpenSearch: `http://opensearch:9200`, index `otel-logs-*`, message field `body`, time field `observedTimestamp` (theo `grafana/provisioning/datasources/opensearch.yaml`).
- Nếu tên metric/label khác sau khi cắm LLM thật hoặc đổi phiên bản collector → chỉnh trong `rules.yaml`, không sửa code.
