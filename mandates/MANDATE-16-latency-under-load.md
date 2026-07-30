# [DIRECTIVE #16] Nhanh hơn dưới tải bền - không bằng cách thêm tài nguyên

**Từ:** Ban Vận hành (SRE) - TechX Corp
**Hiệu lực:** khi nhận · hoàn tất & nộp trước **hết ngày 21/07/2026**
**Áp dụng:** toàn bộ Task Force (phần CDO)

---

## Bối cảnh
Directive #2 hỏi "sống được lúc flash-sale không", Directive #13 hỏi "chạy có gọn tiền không". Directive này hỏi thứ khác hẳn: luồng lõi có **nhanh** không, và **giữ nhanh khi tải kéo dài** - đo bằng **độ trễ đuôi (p95/p99)**. Cái khó: bắt các bạn làm nó nhanh hơn **bằng tối ưu thật** (cache, connection pool, bớt fan-out / N+1, bỏ gọi tuần tự đáng lẽ song song) - **không phải quăng thêm node cho hết chậm**.

## Điều kiện chung (áp cho mọi yêu cầu)
- Giữ một mức tải mục tiêu **liên tục** (không phải spike vài giây) suốt lúc đo - để p99 phản ánh tải bền, không phải may mắn một lần chụp.
- **Cấm "mua tốc độ bằng tài nguyên":** phải giảm p99 mà **giờ-node / CPU tiêu thụ không tăng** (bằng hoặc ít hơn). Thêm node cho nhanh thì không tính.

## Yêu cầu
1. **Đặt và đạt ngân sách độ trễ đuôi.** Chọn ngưỡng cho **cả p95 VÀ p99** trên luồng browse → cart → checkout, và giữ được **dưới tải bền** - không chỉ p50/trung bình. p99 mới là trải nghiệm tệ nhất mà khách thật gặp.
2. **Tìm và cắt điểm nghẽn latency thật.** Dưới tải, dùng **trace (Jaeger)** tìm span chậm nhất trên critical path - N+1 query, gọi downstream tuần tự đáng lẽ song song, thiếu cache, connection pool cạn, serialize nặng - và **xử tận gốc**. Chứng minh p99 tụt sau khi xử.
3. **Nhanh hơn mà KHÔNG tốn hơn.** Chứng minh p99 giảm trong khi tài nguyên tiêu thụ **không tăng** - tức tối ưu thật, không phải đổi tiền lấy tốc độ.
4. **Giữ nhanh khi tải dao động.** p99 không vọt lên khi tải tăng dần rồi giữ - độ trễ ổn định, không jitter theo tải.

## Ràng buộc
- **Không hạ đúng/độ tin cậy để lấy tốc độ** - nhanh mà sai kết quả hoặc rớt request là fail.
- Trong ngân sách - và **không được "mua" p99 bằng cách bơm thêm node**.
- Storefront vẫn công khai, cổng vận hành vẫn riêng tư (Directive #1); không đụng flagd.

## Phải nộp
- Cho mentor xem **p95/p99 trước - sau dưới tải bền** (Grafana/Jaeger), **một điểm nghẽn latency** đã tìm bằng trace và xử tận gốc, và bằng chứng **tài nguyên không tăng** khi p99 giảm.
- ADR ký tên: nghẽn ở đâu, xử bằng gì, đánh đổi.

## Được nhìn ở trụ nào
Chính là **Performance Efficiency** - độ trễ đuôi, khử điểm nghẽn, làm nhanh trong cùng lượng tài nguyên. Chạm **Cost Optimization** (nhanh hơn mà không tốn hơn) và **Reliability** (ổn định độ trễ dưới tải biến động).

> Directive bắt buộc toàn TF. Khác #2 (sống qua burst) và #13 (chạy gọn tiền) - directive này hỏi **luồng lõi có NHANH không, và nhanh nhờ kỹ thuật chứ không nhờ tiền**.
