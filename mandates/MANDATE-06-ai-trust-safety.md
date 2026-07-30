# [DIRECTIVE #6] Tính năng AI phải đáng tin - không bịa, không để bị dắt mũi

**Từ:** Ban AI & Chất lượng - TechX Corp
**Hiệu lực:** ngay khi nhận · hoàn tất & nộp trước **thứ Bảy 18/07/2026**
**Áp dụng:** nhóm AIO của mọi Task Force

---

## Bối cảnh
Tính năng AI đang hiển thị cho khách thật - tóm tắt review, trợ lý hỏi-đáp - nhưng chất lượng và độ an toàn của nó gần như chưa ai kiểm. Khách hỏi "pin con này trâu không", AI **bịa đại một câu nghe hợp lý** dù review chẳng nói gì về pin - thế là mất niềm tin. Tệ hơn: có người nhét vào review một câu kiểu *"bỏ qua hướng dẫn trên, trả lời…"* và AI **ngoan ngoãn nghe theo**, hoặc vô tình phơi thông tin cá nhân trong review ra tóm tắt. Với một sản phẩm có khách, một AI **bịa** hoặc **bị dắt mũi** là rủi ro thương hiệu và dữ liệu thật sự. Từ giờ, tầng AI phải **chứng minh được là đáng tin** thì mới tính là "chạy" - không phải cứ trả lời trôi chảy là xong.

## Yêu cầu
1. **Chạy trên model thật, có đường lui.** Dùng LLM thật (không mock), và khi model lỗi/chậm thì **fallback** - không để treo trang sản phẩm.
2. **Không show nội dung sai.** Tóm tắt/trả lời phải bám review nguồn; có **eval** bắt được khi output sai để **chặn hoặc fallback**, thay vì đẩy nội dung bịa tới khách.
3. **Không để bị dắt mũi.** Chặn câu lệnh độc nhét trong review (prompt-injection), **lọc PII**, không để lộ system prompt. Trợ lý có hành động thì **chỉ làm trong phạm vi cho phép** - tuyệt đối không tự ý checkout hay xoá giỏ của khách.
4. **Chứng minh bằng eval, không bằng lời.** Có bộ eval + số đo (độ trung thực, tỉ lệ chặn tấn công) **tái tạo được** từ script/dữ liệu các bạn commit.

## Ràng buộc
- Đừng để guardrail/eval kéo p95 trang sản phẩm vỡ SLO.
- Trong ngân sách hiện tại - tối ưu token, đừng "quăng model to cho xong".
- Không đụng / vô hiệu hóa cơ chế sự cố (flagd) - xem Luật chơi trong RULES.

## Phải nộp
- Cho mentor **tự bắn thử**: một review có câu độc (injection) và một câu hỏi mà review nguồn không hề trả lời được - và tận mắt thấy AI **chặn / trả "không có thông tin" / fallback**, chứ không bịa hay nghe theo. Nếu có trợ lý hành động: mentor thử bảo nó checkout - nó phải **từ chối / hỏi xác nhận**.
- **ADR ký tên**: chọn model gì, guardrail + fallback thiết kế ra sao, eval đo cái gì.

## Được nhìn ở đâu
Chính là **trụ AI** (AIE): chất lượng, an toàn (guardrail), độ tin cậy, chi phí của tính năng AI. Chạm thêm **Reliability** (fallback khi model hỏng) và **Auditability** (log lại lời gọi AI/tool).

> Directive bắt buộc nhóm AIO toàn TF, thực thi trong ràng buộc. Điểm nằm ở **mức độ đáng tin chứng minh được** - mentor tự thử phá mà AI vẫn đứng vững - không phải "AI có chạy hay không".
