# Vấn đề hiện tại và đề xuất khắc phục - Observability

Thời điểm ghi nhận: 2026-07-08

Người phụ trách: Observability Engineer / On-Call Captain

## Tóm tắt ngắn

Hệ thống application và observability public endpoint đang sống. Lỗi `kubectl` local đã được xử lý, nhưng vẫn còn một số vấn đề observability cần xử lý trước khi có thể đánh dấu Week 1 Bootstrap là hoàn tất.

Các vấn đề chính:

1. `kubectl` local đã được khắc phục: nguyên nhân là dòng `aws_session_token=` rỗng trong `~/.aws/credentials`.
2. Prometheus scraping chưa đạt "tất cả UP": hiện có 11/12 targets `UP`, 1 target `DOWN`.
3. SLO alert group `SLOs` và Grafana dashboard `Cost Estimate` đã có trong repo nhưng chưa thấy trên runtime, khả năng chưa được ArgoCD/Helm sync.
4. Metric `kafka_consumer_group_lag` hiện query được nhưng trả 0 series, cần verify lại sau khi Kafka workload/collector hoạt động có lag data.

## 1. Lỗi `kubectl` local đã được khắc phục

Trạng thái hiện tại: ĐÃ KHẮC PHỤC.

### Nguyên nhân thực tế

File AWS credentials local có dòng session token rỗng:

```ini
aws_session_token=
```

Vì đây là long-term IAM access key/secret key, không được cấu hình `aws_session_token`. Dòng rỗng này làm `aws eks get-token` sinh EKS token có tham số `X-Amz-Security-Token` rỗng. Kubernetes API/EKS authenticator reject token đó và trả `401 Unauthorized`.

Sau khi tạo backup file credentials và xóa dòng `aws_session_token=` rỗng:

```text
EKS token metadata: security_token=ABSENT
kubectl get nodes: PASS
kubectl get ns: PASS
kubectl get pods -n techx-tf1: PASS
```

### Cập nhật mới nhất từ TechLead

TechLead đã gửi bằng chứng chạy được:

```powershell
kubectl get pods
kubectl get pods -n techx-tf1
```

Kết quả phía TechLead:

- Namespace mặc định không có resource, đây là bình thường.
- Namespace `techx-tf1` có đầy đủ pod application và observability đang `Running`, gồm `frontend`, `checkout`, `payment`, `grafana`, `jaeger`, `kafka`, `opensearch`, `otel-collector`, `prometheus`.

Kết luận từ bằng chứng này: cluster và workload không chết. Điều này cũng giúp khoanh vùng lỗi về cấu hình local AWS credentials trên máy người phụ trách.

### Triệu chứng trước khi sửa

Chạy lệnh:

```powershell
kubectl get ns
```

Kết quả:

```text
401 Unauthorized
You must be logged in to the server
```

Lỗi tương tự xảy ra với:

```powershell
kubectl -n techx-tf1 get pods
kubectl -n techx-tf1 get svc prometheus
kubectl get --raw=/version
```

Trước khi sửa, đã thử cả namespace đúng theo TechLead:

```powershell
kubectl -n techx-tf1 get pods
```

Kết quả vẫn là:

```text
You must be logged in to the server
the server has asked for the client to provide credentials
```

### Những gì đã kiểm tra trước khi tìm ra nguyên nhân

AWS CLI đang dùng đúng IAM user:

```text
arn:aws:iam::265808836805:user/phase3/cdo/hoangplt
```

Lệnh TechLead hướng dẫn đã chạy thành công:

```powershell
aws eks update-kubeconfig --region us-east-1 --name techx-eks-dev
```

Kube context hiện tại:

```text
arn:aws:eks:us-east-1:265808836805:cluster/techx-eks-dev
```

EKS cluster:

```text
name: techx-eks-dev
status: ACTIVE
authMode: API_AND_CONFIG_MAP
region: us-east-1
```

EKS access entry cho user `hoangplt` có tồn tại:

```text
arn:aws:iam::265808836805:user/phase3/cdo/hoangplt
```

Associated policy hiện có:

```text
arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy
scope: cluster
```

`aws eks get-token` tạo token thành công.

Đã kiểm tra thêm:

```text
AWS CLI: aws-cli/2.34.55
kubectl client: v1.34.1
Default AWS region: ap-southeast-1
Kubeconfig exec region: us-east-1
```

Default AWS region là `ap-southeast-1`, nhưng kubeconfig đã ghi rõ `--region us-east-1`, nên đây không phải nguyên nhân trực tiếp.

Đã thử bypass kube credential cache bằng cache tạm:

```powershell
kubectl --cache-dir=E:\XBrain\Phase3\capstone-phase-3\.tmp-kube-cache get pods -n techx-tf1
```

Kết quả vẫn `401 Unauthorized`, nên không phải do cache cũ.

Đã thử lấy token bằng `aws eks get-token` rồi đưa token trực tiếp cho `kubectl`; kết quả vẫn `401 Unauthorized`. Sau đó kiểm tra metadata của token mới phát hiện `security_token=EMPTY_PRESENT`.

### Kết luận

Lỗi không phải do chưa tạo access key, chưa chạy `update-kubeconfig`, dùng sai namespace, cache cũ, hay thiếu EKS access entry. Nguyên nhân là AWS credentials local có `aws_session_token` rỗng, làm token EKS bị reject.

Không cần recreate EKS access entry sau khi đã xóa dòng session token rỗng.

### Cách khắc phục đã thực hiện

Đã tạo backup file credentials rồi xóa dòng rỗng:

```text
C:\Users\hoang\.aws\credentials.bak-20260708171514
```

Sau khi sửa, đã chạy lại:

```powershell
aws eks update-kubeconfig --region us-east-1 --name techx-eks-dev
kubectl get ns
kubectl -n techx-tf1 get pods
```

Kết quả:

```text
kubectl get nodes: 3 nodes Ready
kubectl get ns: thấy namespace techx-tf1
kubectl -n techx-tf1 get pods: các pod chính Running
```

## 2. Public runtime đang hoạt động

TechLead cung cấp public endpoint:

```text
Storefront: http://a8a223bbedfc14d20b6213aa27bad031-578576522.us-east-1.elb.amazonaws.com:8080/
Grafana:    http://a8a223bbedfc14d20b6213aa27bad031-578576522.us-east-1.elb.amazonaws.com:8080/grafana/
Jaeger UI:  http://a8a223bbedfc14d20b6213aa27bad031-578576522.us-east-1.elb.amazonaws.com:8080/jaeger/ui/
```

Kết quả kiểm tra:

| Hạng mục | Kết quả |
|---|---|
| Storefront | HTTP 200 |
| Grafana | HTTP 200 |
| Grafana health | `database: ok` |
| Jaeger UI | HTTP 200 |
| Grafana datasources | Có Prometheus, Jaeger, OpenSearch |
| Jaeger services | Có 19 services, gồm `frontend`, `checkout`, `payment`, `product-catalog`, `cart` |
| Jaeger traces | Có trace data cho `frontend` |
| OpenSearch logs | Có index `otel-logs-2026-07-08`, query log trả dữ liệu từ `frontend-proxy` |
| Prometheus metrics | Query `target_info`, HTTP metrics, RPC metrics có data |

Kết luận: application và observability stack public endpoint đang sống. Vấn đề `kubectl` là vấn đề truy cập Kubernetes API, không phải dấu hiệu hệ thống app chết.

## 3. Prometheus target Jaeger metrics đang DOWN

### Triệu chứng

Prometheus targets qua Grafana proxy:

```text
TOTAL=12
UP=11
NOT_UP=1
```

Target đang DOWN:

```text
job: kubernetes-pods
namespace: techx-tf1
pod: jaeger-66bcfd69c8-j5hjw
instance: 10.0.3.124:8888
health: down
lastError: connect: connection refused
```

### Nguyên nhân

Jaeger chart tự gắn annotation:

```yaml
prometheus.io/scrape: "true"
prometheus.io/port: "8888"
```

Nhưng cấu hình Jaeger trước đó chỉ push metrics bằng OTLP về collector, chưa bật pull metrics endpoint cho Prometheus trên port `8888`. Vì vậy Prometheus scrape vào `:8888` bị `connection refused`.

### Đã sửa trong repo

Đã cập nhật `techx-corp-chart/values.yaml` để bật Jaeger Prometheus pull metrics endpoint:

```yaml
jaeger:
  userconfig:
    service:
      telemetry:
        metrics:
          readers:
            - pull:
                exporter:
                  prometheus:
                    host: 0.0.0.0
                    port: 8888
```

### Cần làm tiếp

Sau khi push và ArgoCD/Helm sync, kiểm tra lại:

```text
Grafana -> Prometheus datasource -> /api/v1/targets
```

Kỳ vọng:

```text
TOTAL=12
UP=12
NOT_UP=0
```

Nếu vẫn DOWN, cần kiểm tra pod Jaeger có thực sự listen port `8888` không.

## 4. SLO alert rules và Cost dashboard chưa thấy trên runtime

### Triệu chứng

Trong repo đã có:

```text
techx-corp-chart/values.yaml
```

với alert group:

```text
SLOs
```

gồm:

- `CheckoutHighErrorRate`
- `BrowseHighLatency`
- `KafkaConsumerLag`

Trong repo cũng có:

```text
techx-corp-chart/grafana/provisioning/dashboards/cost-dashboard.json
```

Dashboard:

```text
Cost Estimate
```

Nhưng runtime hiện tại:

- Prometheus `/api/v1/rules` chưa thấy group `SLOs`.
- Grafana search chưa thấy dashboard `Cost Estimate`.

### Kết luận

Các thay đổi đã có ở repository local, nhưng có thể chưa được commit/push hoặc ArgoCD chưa sync vào cluster.

### Đề xuất khắc phục

1. Commit và push các thay đổi observability.
2. Kiểm tra ArgoCD app `techx-corp` đã sync chưa.
3. Sau khi sync, kiểm tra lại:

```text
Grafana -> Dashboards -> search "Cost"
Prometheus -> /api/v1/rules -> group SLOs
```

Kỳ vọng:

- Grafana có dashboard `Cost Estimate`.
- Prometheus có alert group `SLOs`.
- Alert rules hiển thị đủ 3 alert: `CheckoutHighErrorRate`, `BrowseHighLatency`, `KafkaConsumerLag`.

## 5. Metric `kafka_consumer_group_lag` chưa có series

### Triệu chứng

Query Prometheus:

```promql
kafka_consumer_group_lag
```

Kết quả hiện tại:

```text
0 series
```

### Ý nghĩa

Điều này có thể xảy ra nếu:

- Chưa có consumer lag tại thời điểm query.
- Kafka metrics receiver chưa sinh metric này.
- Metric name thực tế khác với query đang dùng.
- Kafka workload/consumer chưa hoạt động hoặc chưa có traffic.

### Đề xuất khắc phục

Sau khi có `kubectl` hoặc quyền kiểm tra runtime tốt hơn, cần:

1. Kiểm tra OTel Collector config receiver `kafkametrics`.
2. Kiểm tra Kafka service và consumer pods có chạy không.
3. Tìm metric Kafka thực tế trong Prometheus bằng query theo prefix:

```promql
{__name__=~".*kafka.*lag.*"}
```

4. Nếu metric name khác, cập nhật lại:

- Alert `KafkaConsumerLag`
- Cost Estimate dashboard
- Runbook P2

## 6. Checklist cần chạy sau khi khắc phục

### Kiểm tra `kubectl`

```powershell
aws eks update-kubeconfig --region us-east-1 --name techx-eks-dev
kubectl get ns
kubectl -n techx-tf1 get pods
kubectl -n techx-tf1 get svc
```

### Kiểm tra Prometheus targets

```powershell
kubectl -n techx-tf1 port-forward svc/prometheus 9090:9090
curl http://localhost:9090/api/v1/targets
```

Kỳ vọng:

```text
Tất cả target quan trọng UP.
Jaeger target :8888 không còn DOWN.
```

### Kiểm tra Jaeger traces

```powershell
kubectl -n techx-tf1 port-forward svc/frontend-proxy 8080:8080
curl http://localhost:8080/
```

Mở:

```text
http://localhost:8080/jaeger/ui/
```

Kỳ vọng:

```text
Có trace mới sau request.
Trace đi qua frontend và backend services.
```

### Kiểm tra OpenSearch logs

Trong Grafana Explore, chọn OpenSearch và query:

```text
kubernetes.namespace: techx-*
```

Hoặc query theo service namespace:

```text
resource.service.namespace: techx-corp
```

Kỳ vọng:

```text
Có log mới từ các service TechX.
```

### Kiểm tra SLO rules và Cost dashboard

Kỳ vọng:

```text
Prometheus có alert group SLOs.
Grafana có dashboard Cost Estimate.
```

## 7. Trạng thái hiện tại để báo cáo

Có thể báo cáo ngắn như sau:

```text
Public Storefront/Grafana/Jaeger hiện truy cập được và có telemetry data.
Prometheus query được HTTP/RPC metrics, Jaeger có traces, OpenSearch có logs.
Kubectl local đã vào được EKS sau khi xóa dòng aws_session_token rỗng trong ~/.aws/credentials.
Prometheus scraping chưa đạt 100% vì target Jaeger metrics :8888 đang DOWN; đã patch values.yaml để bật endpoint này, cần ArgoCD sync.
SLO alert rules và Cost dashboard đã có trong repo nhưng runtime chưa thấy, cần commit/push và sync.
```
