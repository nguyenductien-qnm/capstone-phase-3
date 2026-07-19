# [DIRECTIVE #19] Biết trần của mình - và nâng trần bằng hiệu suất

**Từ:** Ban Vận hành (SRE) - TechX Corp
**Hiệu lực:** khi nhận · hoàn tất & nộp trước **hết ngày 22/07/2026**
**Áp dụng:** toàn bộ Task Force (phần CDO)

---

## Bối cảnh
Directive #2 hỏi "chịu được 200 user không", #13 hỏi "chạy có gọn tiền không", #16 hỏi "có nhanh không". Directive này hỏi thứ chưa ai chạm: **trần thông lượng của hệ là bao nhiêu, và nâng nó lên được không mà không thêm node**. Hầu hết đội không biết cluster của mình chịu được bao nhiêu request/giây trước khi gãy - nên khi tải thật vượt qua, sập mà không hiểu vì sao.

## Điều kiện chung
- Đo trên **cùng hạ tầng hiện tại** (không thêm node giữa bài) - vì đây là bài về **hiệu suất trên tài nguyên có sẵn**, không phải mua thêm.
- Thước đo: **RPS (hoặc user đồng thời) đỉnh mà vẫn giữ SLO**, và **số request phục vụ được trên mỗi node** (density).

## Yêu cầu
1. **Tìm trần THẬT (breakpoint).** Tăng tải dần tới khi SLO gãy (p99 vượt / error tăng) → xác định **chính xác** hệ hiện tại chịu được bao nhiêu RPS/đồng thời. Biết trần là điều kiện để quản trị nó.
2. **Nâng trần bằng hiệu suất, không bằng node.** Tăng số request phục vụ được **trên cùng số node** - qua tuning (concurrency, thread/worker pool, HPA target, resource request sát usage, keep-alive/connection reuse). Chứng minh trần mới cao hơn mà **số node không đổi**.
3. **Xử nút thắt thông lượng.** Tìm service **bão hoà sớm nhất** (không phải chậm - mà cạn: CPU/mem/connection/queue depth) và nới nó - đây là thứ quyết định trần.
4. **Xuống mềm khi vượt trần.** Khi tải vượt trần, hệ **shed load / rate-limit** để bảo vệ phần còn phục vụ được (ưu tiên checkout, hy sinh bớt browse) - **không sập toàn bộ**. Vượt trần là chuyện sẽ xảy ra; cách xử mới là điểm.

## Ràng buộc
- **Không nâng trần bằng cách bơm thêm node** - phải là hiệu suất trên hạ tầng có sẵn.
- Giữ đúng/độ tin cậy - thông lượng cao mà sai kết quả là fail.
- Storefront public, cổng vận hành private (Directive #1); không đụng flagd.

## Phải nộp
- Cho mentor xem **RPS đỉnh giữ SLO trước - sau** (đã nâng trần), **requests-per-node** tăng mà node không đổi, **một nút thắt thông lượng** đã tìm và nới, và **demo xuống mềm**: đẩy tải vượt trần → checkout vẫn được bảo vệ (shed/rate-limit), hệ không sập.
- ADR ký tên: trần cũ/mới, nút thắt ở đâu, nâng bằng gì, cơ chế load-shedding.

## Được nhìn ở trụ nào
Chính là **Performance Efficiency** - trần thông lượng, density, khử saturation. Chạm **Cost Optimization** (nhiều request hơn trên mỗi node = rẻ hơn mỗi request) và **Reliability** (xuống mềm, bảo vệ luồng lõi khi quá tải).

> Directive bắt buộc toàn TF. Khác #2 (chịu một mức cố định) - directive này hỏi **trần thật của các bạn ở đâu, có nâng được không mà không tốn thêm, và khi vượt trần thì gục hay xuống mềm**.
