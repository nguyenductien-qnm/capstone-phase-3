# Architecture Trade-off: Regional NAT Gateway for public outbound egress

## Quyết định của nhóm

Nhóm quyết định dùng **Regional NAT Gateway ở automatic mode** cho public outbound internet từ private subnets.

Lý do chính: workloads trong private subnets chạy multi-AZ và cần outbound internet ổn định. Regional NAT Gateway giảm rủi ro egress bị phụ thuộc vào một NAT Gateway zonal cụ thể hoặc route per-AZ bị cấu hình sai, đồng thời đơn giản hóa route/IaC so với mô hình zonal NAT Gateway per AZ.

Điểm cần hiểu rõ: Regional NAT cover tốt hơn **NAT-layer failure**, nhưng không thay thế multi-AZ application replicas. Nếu cả AZ chết, pods/nodes trong AZ đó vẫn chết; app phải có replicas ở AZ khác.

Tradeoff nhóm chấp nhận:

- Regional NAT không support private NAT use case.
- Khi workload xuất hiện ở AZ mới, regional NAT có thể mất thời gian expand sang AZ đó; trong lúc chờ, traffic có thể xử lý cross-AZ.
- Migration từ zonal sang regional có thể reset existing connections, cần maintenance window.
- Cần verify Terraform provider/module support, route behavior và cost thực tế trước khi chốt implementation.

Phương án không chọn làm mặc định:

- **Single zonal NAT Gateway shared nhiều AZ**: rẻ và đơn giản hơn, nhưng tạo egress blast radius xấu. Nếu AZ chứa NAT Gateway gặp sự cố, workloads ở AZ khác phụ thuộc route đó cũng có thể mất outbound internet.
- **Zonal NAT Gateway per AZ**: HA tốt hơn shared NAT và là fallback hợp lý, nhưng nhiều NAT resource, nhiều route table hơn, IaC phức tạp hơn và cần automation nếu muốn failover route khi NAT của một AZ lỗi.

Nhóm sẽ xem xét lại nếu cần private NAT qua Transit Gateway/VPN/on-prem, regional NAT chưa được module/IaC support tốt, hoặc cost thực tế không phù hợp.

## Bối cảnh

Private subnets dùng cho EKS/app workloads cần outbound internet để pull image, gọi external API, tải package hoặc gửi telemetry nếu có. Vì workloads chạy multi-AZ, NAT layer không nên trở thành single-AZ bottleneck hoặc single point of egress failure.

Với zonal NAT Gateway per AZ, route thường có dạng:

```text
AZ-A private subnet -> NAT-A
AZ-B private subnet -> NAT-B
AZ-C private subnet -> NAT-C
```

Nếu **NAT-A chết**, AZ-A không nhất thiết chết. Nhưng private workloads trong AZ-A sẽ mất outbound internet qua route mặc định nếu không có route failover sang NAT-B hoặc NAT-C. AZ-B và AZ-C vẫn hoạt động nếu NAT-B/NAT-C còn tốt.

Với Regional NAT Gateway, private subnets có thể route về cùng một regional NAT Gateway ID. AWS tự expand NAT capacity across AZ dựa trên workload presence, nên nhóm không phải tự maintain NAT-A/NAT-B/NAT-C và route mapping cho từng AZ.

## Các phương án

| Phương án | Vai trò | Kết luận |
|---|---|---|
| Single zonal NAT shared nhiều AZ | Một NAT Gateway trong một AZ phục vụ nhiều private subnets. | Không chọn vì blast radius xấu. |
| Zonal NAT Gateway per AZ | Mỗi AZ có NAT riêng, private subnet route về NAT cùng AZ. | Fallback tốt nếu regional NAT không fit. |
| Regional NAT Gateway automatic mode | Một regional NAT Gateway tự expand across AZ theo workload presence. | Chọn làm default. |

## Tradeoff chính

| Khía cạnh | Single zonal NAT shared | Zonal NAT per AZ | Regional NAT Gateway |
|---|---|---|---|
| HA | Thấp. Một NAT/AZ có thể ảnh hưởng nhiều AZ phụ thuộc route đó. | Tốt nếu mỗi subnet route về NAT cùng AZ. | Tốt hơn mặc định vì AWS tự expand across AZ. |
| NAT failure trong một AZ | Có thể làm mất egress nhiều AZ nếu cùng phụ thuộc NAT đó. | Làm mất egress private subnet trong AZ đó nếu không failover route. | AWS-managed regional behavior cover tốt hơn NAT-layer failure. |
| AZ failure | Workloads trong AZ đó chết; AZ khác có thể vẫn bị ảnh hưởng nếu route phụ thuộc NAT ở AZ chết. | Workloads trong AZ đó chết; AZ khác vẫn có NAT riêng. | Workloads trong AZ đó chết; AZ khác vẫn có regional NAT path. |
| Routing/IaC | Đơn giản nhất nhưng rủi ro nhất. | Nhiều route table/subnet mapping hơn. | Đơn giản hơn per-AZ vì dùng một regional NAT ID. |
| Cost | Thấp nhất vì ít NAT Gateway nhất. | Cao hơn vì mỗi AZ có một NAT Gateway. | Cần đo thực tế, đổi lại giảm route/IaC complexity. |
| Cross-AZ traffic | Có thể xảy ra nếu subnet khác AZ route về NAT này. | Tránh được nếu route đúng theo AZ. | Có thể tạm xảy ra khi expand sang AZ mới chưa hoàn tất. |
| Private NAT | Không phải lựa chọn HA tốt. | Support private NAT use case. | Không support private NAT. |
| Operational risk | Dễ bị bỏ qua vì chạy được lúc bình thường. | Dễ sai route/IaC hoặc thiếu failover automation. | Cần hiểu limitation regional mode và migration behavior. |

## Lý do chọn Regional NAT Gateway

Nhóm chọn Regional NAT Gateway vì nó match với mục tiêu phase này: private workloads chạy multi-AZ, HA mặc định hơn cho NAT layer, và giảm số lượng routing decision phải tự maintain.

Điểm quan trọng là nhóm không chỉ tối ưu chi phí theo số lượng NAT Gateway. Single zonal NAT có thể rẻ hơn, nhưng egress path có blast radius xấu. Zonal NAT per AZ có HA tốt hơn, nhưng tăng resource, route table và automation surface. Regional NAT là điểm cân bằng tốt hơn cho public outbound egress của project này.

## Guardrail vận hành

- Dùng Regional NAT Gateway cho public outbound internet.
- Không dùng Regional NAT nếu requirement là private NAT qua Transit Gateway, VPN hoặc Direct Connect.
- Private subnet route phải trỏ rõ về regional NAT Gateway.
- Không để app workload nằm trong public subnet chỉ để có outbound internet.
- Theo dõi NAT gateway metrics, errors, packet drops, bytes processed và port exhaustion.
- Nếu workload expand sang AZ mới, verify regional NAT đã expand theo AZ đó.
- App workload vẫn phải chạy multi-AZ; NAT layer không thay thế replica strategy.

## Rollback và điều kiện đổi quyết định

Fallback là **zonal NAT Gateway per AZ** nếu Regional NAT chưa được Terraform/module support tốt, hoặc nếu workload cần private NAT.

Không rollback về single zonal NAT shared nhiều AZ trừ khi chỉ là môi trường demo/cost-saving tạm thời và nhóm chấp nhận rõ egress SPOF.

Migration từ zonal sang regional cần maintenance window vì route update hoặc NAT conversion có thể reset existing connections.

## Verification

- Private subnets ở nhiều AZ outbound internet thành công.
- Route table private subnet trỏ đúng về regional NAT Gateway.
- Workload ở AZ khác vẫn có egress nếu một AZ gặp sự cố.
- NAT metrics không có packet drop, error hoặc port exhaustion bất thường.
- Khi workload xuất hiện ở AZ mới, xác nhận NAT Gateway đã expand sang AZ đó.

## Nguồn tham khảo

- NAT gateway basics: https://docs.aws.amazon.com/vpc/latest/userguide/nat-gateway-basics.html
- Regional NAT gateways for automatic multi-AZ expansion: https://docs.aws.amazon.com/vpc/latest/userguide/nat-gateways-regional.html
