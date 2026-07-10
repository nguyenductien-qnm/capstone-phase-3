# Architecture Trade-off: NLB in front of Envoy frontend-proxy

## Owner

- Team: Infrastructure
- Nhóm chịu trách nhiệm : CDO05-CD09
- Người chịu trách nhiệm : Thành Đạt

## Quyết định của nhóm

Nhóm quyết định đặt **NLB trước Envoy/frontend-proxy**.

Lý do chính: `frontend-proxy` hiện là gateway của project và đang giữ nhiều behavior L7 như routing, rewrite, redirect, WebSocket/filter, route cho observability UI, OTLP browser endpoint và OpenTelemetry gateway telemetry. NLB chỉ cần làm public edge entrypoint và forward traffic vào gateway.

Tradeoff nhóm chấp nhận:

- NLB health check phản ánh sức khỏe gateway, không phản ánh trực tiếp từng business service phía sau Envoy.
- Gateway vẫn là thành phần trong cluster, nên phải vận hành replicas, PDB, readiness và observability cho `frontend-proxy`.
- Không lấy hết L7 capability của ALB ở edge như WAF/auth/header/path rules nếu chưa có requirement rõ.

Phương án không chọn làm mặc định:

- **ALB/Ingress thay Envoy**: phải migrate nhiều route và làm mất hoặc phải dựng lại pipeline observability gateway đang có ở Envoy.
- **ALB/Ingress trước Envoy**: giữ Envoy nhưng thêm một lớp L7 phía trước, dễ duplicate routing và debug phức tạp hơn.

Nhóm sẽ xem xét lại nếu có yêu cầu cụ thể về WAF/auth/host-path routing tại AWS edge hoặc muốn AWS quản lý L7 routing thay vì Envoy.

## Bối cảnh

Repo đang có `frontend-proxy` làm gateway chính. Browser và service path hiện giả định traffic đi qua Envoy cho nhiều endpoint, bao gồm frontend, image, feature flag, observability UI và OTLP HTTP.

Vì vậy quyết định không chỉ là chọn load balancer. Quyết định thực chất là giữ gateway behavior trong project hay chuyển dần sang AWS-managed L7.

## Các phương án

| Phương án | Vai trò | Kết luận |
|---|---|---|
| NLB trước Envoy | AWS edge L4/L7-lite, Envoy làm app gateway. | Chọn làm default. |
| ALB/Ingress thay Envoy | ALB/Ingress nhận toàn bộ routing L7. | Không chọn vì phải migrate gateway behavior. |
| ALB/Ingress trước Envoy | ALB làm edge L7, Envoy vẫn làm gateway trong cluster. | Chỉ chọn nếu có requirement AWS edge L7 cụ thể. |

## Tradeoff chính

| Khía cạnh     | NLB trước Envoy                                     | ALB/Ingress thay Envoy                                     | ALB/Ingress trước Envoy                        |
| ------------- | --------------------------------------------------- | ---------------------------------------------------------- | ---------------------------------------------- |
| Fit với repo  | Cao, giữ `frontend-proxy` làm gateway.              | Thấp hơn, phải migrate route/behavior.                     | Trung bình, giữ Envoy nhưng thêm lớp L7.       |
| Routing L7    | Envoy xử lý path/rewrite/redirect/WebSocket/filter. | ALB/Ingress xử lý bằng rule/annotation.                    | Routing có thể bị duplicate giữa ALB và Envoy. |
| Observability | Giữ Envoy OTel trace/access log vào OTel Collector. | Chuyển nhiều telemetry sang AWS-side metrics/logs.         | Có thêm telemetry nhưng debug nhiều lớp hơn.   |
| Portability   | Gateway behavior nằm trong chart/app layer.         | Phụ thuộc nhiều hơn vào AWS ALB annotations/rules.         | Phụ thuộc cả AWS edge và Envoy.                |
| Failure mode  | NLB chỉ biết gateway target healthy.                | ALB có thể health check từng service nếu expose trực tiếp. | Cần debug cả ALB rule và Envoy route.          |

## Lý do giữ Envoy

Nhóm không bỏ Envoy trong phase này vì Envoy không chỉ là reverse proxy đơn giản. Nó đang encode behavior cụ thể của project. Nếu chuyển sang ALB/Ingress, nhóm phải migrate lại route như `/otlp-http/`, `/grafana/`, `/jaeger/`, `/images/`, `/flagservice/`, `/feature`, redirect path và WebSocket behavior.

Điểm quan trọng nhất là observability. Envoy hiện có OpenTelemetry tracing và access log đưa về OTel Collector. Nếu bỏ Envoy, gateway telemetry sẽ chuyển sang AWS-side telemetry hoặc cần thêm pipeline chuyển đổi.

## Guardrail vận hành

- `frontend-proxy` cần tối thiểu 2 replicas nếu public traffic đi qua NLB.
- Có PDB và readiness/liveness probe cho gateway.
- Nếu dùng target-type `ip`, NLB register pod IP của `frontend-proxy`, không register từng business service.
- Health sâu của business services phải dựa vào Kubernetes readiness, service metrics, traces và alerts, không dựa riêng vào NLB target health.
- TLS termination phải được quyết định rõ: ở NLB, ở Envoy, hoặc pass-through. Không để cấu hình mơ hồ.

## Rollback và điều kiện đổi quyết định

Chuyển sang ALB/Ingress hợp lý nếu nhóm cần WAF, auth ở load balancer layer, host/path routing ở AWS edge, header/path rule trước khi traffic vào cluster, hoặc muốn expose health check từng app service trực tiếp từ AWS layer.

Nếu chỉ cần public entrypoint ổn định và vẫn muốn giữ gateway behavior/telemetry trong project, NLB trước Envoy vẫn là đường ít đổi behavior nhất.

## Verification

- NLB target group healthy khi `frontend-proxy` healthy.
- Route qua Envoy vẫn hoạt động cho frontend, image, feature flag, observability UI và OTLP HTTP.
- Envoy access log/traces vẫn đi vào OTel Collector.
- Khi kill một `frontend-proxy` pod, traffic vẫn qua pod còn lại.
- Business service lỗi phải hiện qua app metrics/traces/alerts, không bị che bởi NLB target health.
