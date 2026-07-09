# Biên bản verify telemetry pipeline

Lần kiểm tra gần nhất: 2026-07-08 17:20 ICT

Người phụ trách: Kỹ sư Observability / On-Call Captain

## Trạng thái hiện tại

Runtime verification qua `kubectl` đã truy cập được EKS cluster từ máy local sau khi sửa AWS credentials. Nguyên nhân lỗi trước đó là file `~/.aws/credentials` có dòng `aws_session_token=` rỗng. Dòng này làm `aws eks get-token` sinh EKS token có `X-Amz-Security-Token` rỗng, khiến Kubernetes API trả `401 Unauthorized`.

TechLead cũng đã cung cấp public ELB endpoint nên có thể verify thêm một phần telemetry qua Storefront, Grafana và Jaeger mà không cần port-forward.

Trạng thái hiện tại:

- Storefront public URL truy cập được.
- Grafana public URL truy cập được.
- Jaeger public URL truy cập được.
- Prometheus query được trực tiếp qua `kubectl port-forward svc/prometheus`.
- OpenSearch logs query được thông qua Grafana datasource proxy.
- `kubectl` trên máy local đã truy cập được EKS cluster.
- `kubectl get nodes` trả về 3 node `Ready`.
- `kubectl get ns` trả về namespace `techx-tf1` và các namespace hệ thống.
- `kubectl get pods -n techx-tf1` xác nhận các pod application và observability đang `Running`.
- Prometheus targets hiện có 11/12 target `UP`; 1 target `DOWN` là Jaeger metrics endpoint `:8888`.
- Prometheus runtime chưa có alert group `SLOs`.
- Metric `kafka_consumer_group_lag` hiện trả 0 series.

## Kiểm tra phía repository

| Hạng mục kiểm tra | Trạng thái | Bằng chứng |
|---|---|---|
| Observability stack đã được bật trong chart | ĐẠT | `techx-corp-chart/values.yaml` bật `opentelemetry-collector`, `jaeger`, `prometheus`, `grafana` và `opensearch`. |
| Có values file cho observability-only deployment | ĐẠT | `deploy/values-observability.yaml` bật telemetry stack và tắt app components cho shared observability deployment. |
| OTel Collector export traces | ĐẠT | `techx-corp-chart/values.yaml` gửi traces tới `otlp/jaeger` và spanmetrics. |
| OTel Collector export metrics | ĐẠT | `techx-corp-chart/values.yaml` gửi metrics tới `http://prometheus:9090/api/v1/otlp`. |
| OTel Collector export logs | ĐẠT | `techx-corp-chart/values.yaml` gửi logs tới `http://opensearch:9200`. |
| Grafana datasources đã có | ĐẠT | `techx-corp-chart/grafana/provisioning/datasources/` có datasource cho Prometheus, Jaeger và OpenSearch. |
| Cost dashboard tồn tại và parse được JSON | ĐẠT | `techx-corp-chart/grafana/provisioning/dashboards/cost-dashboard.json` parse thành công; title là `Cost Estimate`. |
| SLO alert rules đã có | ĐẠT | `techx-corp-chart/values.yaml` có `CheckoutHighErrorRate`, `BrowseHighLatency` và `KafkaConsumerLag`. |
| Alert runbooks đã có | ĐẠT | `docs/observability/runbooks.md`. |
| On-call schedule đã có | ĐẠT | `docs/observability/on-call-schedule.md`. |

## Lần thử runtime verification

Các lệnh đã thử:

```powershell
aws sts get-caller-identity
aws eks describe-cluster --name techx-eks-dev --region us-east-1
aws eks list-associated-access-policies --cluster-name techx-eks-dev --principal-arn arn:aws:iam::265808836805:user/phase3/cdo/hoangplt --region us-east-1
aws eks get-token --cluster-name techx-eks-dev --region us-east-1
aws eks update-kubeconfig --name techx-eks-dev --region us-east-1
kubectl config current-context
kubectl get ns
kubectl -n techx-tf1 get pods
```

Kết quả quan sát được:

```text
AWS identity: arn:aws:iam::265808836805:user/phase3/cdo/hoangplt
EKS cluster: techx-eks-dev, status ACTIVE, auth mode API_AND_CONFIG_MAP
EKS access entry: present for hoangplt
Associated EKS policy: AmazonEKSClusterAdminPolicy, cluster scope
Kube context: arn:aws:eks:us-east-1:265808836805:cluster/techx-eks-dev
Root cause fixed: removed empty aws_session_token from ~/.aws/credentials
EKS token metadata after fix: security_token=ABSENT
kubectl get nodes: PASS, 3 nodes Ready
kubectl get ns: PASS
kubectl get pods -n techx-tf1: PASS, workload pods Running
```

Kết luận: lỗi local `kubectl` đã được xử lý. Hiện có thể dùng `kubectl` và `port-forward` từ máy local để tiếp tục verify runtime.

## Kiểm tra runtime trực tiếp qua `kubectl`

Sau khi sửa AWS credentials local, đã chạy:

```powershell
kubectl get nodes
kubectl get ns
kubectl get pods -n techx-tf1
kubectl get svc -n techx-tf1
kubectl get deploy -n techx-tf1
kubectl -n techx-tf1 port-forward svc/prometheus 19090:9090
```

Kết quả:

| Hạng mục | Kết quả | Ghi chú |
|---|---|---|
| Nodes | ĐẠT | 3 node `Ready`. |
| Namespaces | ĐẠT | Có namespace `techx-tf1`. |
| Pods `techx-tf1` | ĐẠT | Các pod application và observability đang `Running`. |
| Deployments `techx-tf1` | ĐẠT | Các deployment chính `AVAILABLE 1/1`. |
| Services `techx-tf1` | ĐẠT | Có `prometheus`, `grafana`, `jaeger`, `opensearch`, `otel-collector`, `frontend-proxy`. |
| Prometheus targets | CHƯA ĐẠT HOÀN TOÀN | 12 active targets, 11 `UP`, 1 `DOWN`. |
| Target DOWN | CHƯA ĐẠT | `jaeger-66bcfd69c8-j5hjw` scrape `http://10.0.3.124:8888/metrics`, lỗi `connection refused`. |
| HTTP metrics | ĐẠT | `http_server_request_duration_seconds_count` có 20 series. |
| RPC metrics | ĐẠT | `rpc_server_duration_milliseconds_count` có 4 series. |
| Kafka lag metric | CHƯA ĐẠT | `kafka_consumer_group_lag` có 0 series. |
| Prometheus SLO group runtime | CHƯA SYNC | `/api/v1/rules` chưa có group `SLOs`. |

## Kiểm tra runtime qua public ELB

TechLead cung cấp các URL public:

```text
Storefront: http://a8a223bbedfc14d20b6213aa27bad031-578576522.us-east-1.elb.amazonaws.com:8080/
Grafana:    http://a8a223bbedfc14d20b6213aa27bad031-578576522.us-east-1.elb.amazonaws.com:8080/grafana/
Jaeger UI:  http://a8a223bbedfc14d20b6213aa27bad031-578576522.us-east-1.elb.amazonaws.com:8080/jaeger/ui/
```

Kết quả kiểm tra:

| Hạng mục | Kết quả | Ghi chú |
|---|---|---|
| Storefront | ĐẠT | Public URL trả HTTP 200. |
| Grafana | ĐẠT | Public URL trả HTTP 200; `/grafana/api/health` báo database `ok`. |
| Grafana datasources | ĐẠT | Có `Prometheus`, `Jaeger`, `OpenSearch`. |
| Jaeger UI | ĐẠT | Public URL trả HTTP 200. |
| Jaeger services | ĐẠT | Jaeger API trả về 19 services, gồm `frontend`, `checkout`, `payment`, `product-catalog`, `cart`. |
| Jaeger traces | ĐẠT | Query trace cho `frontend` trả về trace data. |
| OpenSearch logs | ĐẠT | Index `otel-logs-2026-07-08` tồn tại; query log trả về dữ liệu từ `frontend-proxy`. |
| Prometheus metrics | ĐẠT MỘT PHẦN | Query `target_info`, `http_server_request_duration_seconds_count`, `rpc_server_duration_milliseconds_count` có data. Query `kafka_consumer_group_lag` hiện trả 0 series. |
| Prometheus targets | CHƯA ĐẠT HOÀN TOÀN | Có 12 active targets, 11 `UP`, 1 `DOWN`. Target down là Jaeger pod metrics port `8888`, lỗi `connection refused`. |
| SLO alert group runtime | CHƯA SYNC | Prometheus runtime chưa thấy group `SLOs`; rule đã có trong repo nhưng cần ArgoCD/Helm sync. |
| Cost dashboard runtime | CHƯA SYNC | Grafana runtime chưa thấy dashboard `Cost Estimate`; file đã có trong repo nhưng cần ArgoCD/Helm sync. |

Nguyên nhân Prometheus còn 1 target `DOWN`:

- Jaeger chart tự gắn annotation `prometheus.io/scrape: "true"` và `prometheus.io/port: "8888"`.
- Cấu hình Jaeger trước đó chỉ push metrics bằng OTLP về collector, chưa bật pull metrics endpoint cho Prometheus trên port `8888`.
- Đã cập nhật `techx-corp-chart/values.yaml` để bật Jaeger pull metrics endpoint `0.0.0.0:8888`.
- Sau khi ArgoCD sync chart mới, cần kiểm tra lại `/api/v1/targets`; kỳ vọng target Jaeger chuyển sang `UP`.

## Checklist runtime tiếp tục dùng sau khi `kubectl` đã sửa

Set namespace:

```powershell
$NS = "techx-tf1"
```

Kiểm tra workloads chính:

```powershell
kubectl -n $NS get pods
kubectl -n $NS get svc prometheus grafana jaeger opensearch otel-collector frontend-proxy
```

Verify Prometheus targets:

```powershell
kubectl -n $NS port-forward svc/prometheus 9090:9090
curl http://localhost:9090/api/v1/targets
curl "http://localhost:9090/api/v1/query?query=up"
```

Kết quả kỳ vọng:

- Các scrape/OTLP targets quan trọng có `health: up`.
- Prometheus trả về dữ liệu hợp lệ, không phải empty result hoặc connection error.

Verify service metrics:

```powershell
curl "http://localhost:9090/api/v1/query?query=target_info"
curl "http://localhost:9090/api/v1/query?query=http_server_request_duration_seconds_count"
curl "http://localhost:9090/api/v1/query?query=rpc_server_duration_milliseconds_count"
curl "http://localhost:9090/api/v1/query?query=kafka_consumer_group_lag"
```

Verify Grafana và Jaeger thông qua frontend proxy:

```powershell
kubectl -n $NS port-forward svc/frontend-proxy 8080:8080
```

Mở:

- `http://localhost:8080/grafana/`
- `http://localhost:8080/jaeger/ui/`

Tạo một request thật vào storefront:

```powershell
curl http://localhost:8080/
```

Kết quả kỳ vọng:

- Grafana APM dashboard hiển thị `frontend`, `checkout` và các dependent services.
- Jaeger có ít nhất một trace từ `frontend` sang backend services.
- OpenSearch datasource trả về log mới cho `service.namespace=techx-corp`.
- Prometheus Alerts page có alert group `SLOs`.

## Cách đánh dấu kết quả

Chỉ đánh dấu runtime verification là PASS khi các điều kiện sau đều đúng:

- `kubectl` truy cập được namespace `techx-tf1`.
- Prometheus `/api/v1/targets` hiển thị target quan trọng ở trạng thái `UP`.
- Metrics chính query được trong Prometheus.
- Sau khi tạo request storefront, Jaeger có trace mới.
- OpenSearch/Grafana Explore trả về logs mới từ namespace TechX.
- Grafana dashboards không còn trạng thái empty/no data cho các panel chính.

Nếu một trong các phần trên chưa chạy được, giữ trạng thái là BLOCKED hoặc PARTIAL, không ghi là PASS.
