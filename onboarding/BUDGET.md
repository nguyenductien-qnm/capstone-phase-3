# Ngân sách hạ tầng

Vận hành sản phẩm thật thì có trần chi phí. TechX Corp cấp cho mỗi TF một ngân sách hạ tầng AWS cố định - tiêu vượt là vấn đề, đúng như đời thật.

## Trần ngân sách

**~$300 / tuần / TF** cho toàn bộ hạ tầng AWS của TF, gồm:
- Compute: EKS node (EC2), autoscaling.
- Data: RDS / ElastiCache / MSK nếu bạn migrate sang managed; hoặc EBS cho DB in-cluster.
- Mạng: data transfer, NAT, load balancer.
- Phụ trợ: log/metric storage, backup.

## Ràng buộc

- **Vượt trần = vi phạm ràng buộc**, tính vào trụ Cost khi chấm. Không phải cứ chi nhiều là mạnh - **hiệu quả chi phí trên mỗi đơn vị tải** mới là thứ được nhìn.
- Mọi quyết định tốn tiền lớn (bật Multi-AZ, tăng node, lên managed DB) phải **cân với lợi ích** và ghi lại lý do (ADR). Bật Multi-AZ "cho chắc" mà vỡ ngân sách là một quyết định tồi.

## Cách theo dõi

- **AWS Cost Explorer** - xem chi tiêu theo service/ngày.
- **AWS Budgets + Cost Anomaly Detection** - đặt alert khi tiến gần trần hoặc có bất thường. Dựng cái này sớm là một việc nên làm.

## Đánh đổi điển hình bạn sẽ gặp

- **Reliability vs Cost:** Multi-AZ RDS bền hơn nhưng ~gấp đôi tiền. Single-AZ rẻ nhưng rủi ro. Chọn cái nào, vì sao?
- **Scale vs Cost:** node lớn luôn sẵn (đắt) hay autoscale + spot (rẻ, rủi ro gián đoạn)?
- **Observability vs Cost:** giữ log/metric lâu (tốn storage) hay retention ngắn?

Không có đáp án đúng tuyệt đối - có đánh đổi hợp lý và giải thích được. Đó là thứ đang được chấm.

> Con số $300/tuần là baseline. BTC có thể điều chỉnh hoặc nới khi ban hành directive lớn (vd bắt buộc migration) - sẽ thông báo rõ khi đó.
