# Mandates - directive từ BTC

Trong quá trình vận hành (Tuần 2-3), BTC có thể ban hành các **directive bắt buộc** cho toàn bộ TF - ví dụ một quyết định kiến trúc từ trên xuống như migrate database sang managed service (RDS), siết bảo mật, hay cắt chi phí.

Mỗi directive xuất hiện ở đây dưới dạng một file memo **khi có hiệu lực**. Khi thấy một memo mới:

- Đọc kỹ yêu cầu, thời hạn, và ràng buộc.
- Thực thi **trong ngân sách + giữ SLO** - không thương lượng phạm vi.
- Nộp kèm **ADR ký tên** (đánh đổi đã cân), bằng chứng hoàn thành, và **rollback plan**.

Directive được chấm ở **cách bạn làm** (zero-downtime, an toàn dữ liệu, cost, bảo mật, rollback), không phải chỉ "có làm xong hay không".

> Thư mục này trống lúc bắt đầu - directive được thả vào đúng thời điểm trong lúc vận hành. Theo dõi nó cùng với kênh thông báo của chương trình.
