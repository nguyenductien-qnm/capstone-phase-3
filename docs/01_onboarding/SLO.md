# SLO - mục tiêu mức dịch vụ

Đây là cam kết dịch vụ của TechX Corp với khách hàng. Bạn tiếp quản hệ thống thì bạn giữ các mục tiêu này. Mọi thay đổi bạn làm không được kéo các số này xuống dưới ngưỡng.

## SLO theo luồng chính

| Luồng | SLI (đo cái gì) | SLO (ngưỡng) |
|---|---|---|
| Duyệt / tìm sản phẩm | Tỉ lệ request không lỗi (non-5xx) | **≥ 99.5%** |
| Duyệt sản phẩm - độ trễ | p95 latency ở storefront | **< 1s** |
| Giỏ hàng | Tỉ lệ thao tác giỏ thành công | **≥ 99.5%** |
| **Đặt hàng (checkout)** | Tỉ lệ đặt hàng thành công | **≥ 99.0%** |
| Tóm tắt review AI | Best-effort | Không SLA cứng, nhưng **không được hiển thị tóm tắt sai lệch** cho khách |

Checkout là luồng quan trọng nhất (ra tiền) - ưu tiên bảo vệ nó trước.

## Error budget

SLO không phải 100%, phần thiếu là **error budget** để bạn tiêu:
- Checkout ≥ 99.0% → error budget = **1%** số request trong cửa sổ đo.
- Còn budget → được phép làm thay đổi rủi ro (deploy, migration, thí nghiệm).
- **Cháy budget** (đã lỗi vượt mức) → đóng băng thay đổi rủi ro, tập trung ổn định lại trước.

Đây là công cụ đánh đổi thật: giữa "ship nhanh" và "giữ ổn định", error budget là thứ quyết định bạn được phép liều tới đâu.

## Đo ở đâu

- Cửa sổ đo mặc định: **rolling 24h** cho vận hành hằng ngày; tổng kết theo **tuần** ở Ops Review.
- Nguồn số liệu: **Prometheus / Grafana** (đã có sẵn trong hệ thống). Dựng dashboard SLO là một trong những việc nên làm sớm - không đo được thì không quản được.

## Lưu ý

Mấy con số này là **baseline BTC đặt ra**. Khi có sự cố do BTC bơm vào, mục tiêu không phải là "SLO không bao giờ vỡ" mà là **giữ ảnh hưởng tới khách nhỏ nhất và phục hồi nhanh** - fallback, retry, containment. Cách bạn xử lý khi SLO bị đe dọa mới là thứ được đánh giá.
