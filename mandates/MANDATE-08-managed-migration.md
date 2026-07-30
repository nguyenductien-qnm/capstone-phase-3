# [DIRECTIVE #8] Đưa toàn bộ tầng dữ liệu lên managed service

**Từ:** Ban Hạ tầng & Tuân thủ - TechX Corp
**Hiệu lực:** khi nhận · hoàn tất & nộp trước **hết ngày 20/07/2026**
**Áp dụng:** TF chưa đưa tầng dữ liệu lên managed (TF đã managed từ trước làm Directive #9 thay cho directive này - mỗi đội chỉ làm một trong hai)

---

## Bối cảnh
Ba store trạng thái của hệ thống - **PostgreSQL, Redis/Valkey, Kafka** - đang tự host bằng pod trong cluster: không backup tự động, không Multi-AZ, không mã hóa chuẩn, và tốn công tự vận hành. TechX Corp yêu cầu chuyển cả ba sang **managed service** (RDS, ElastiCache, MSK) để có độ tin cậy, backup và tuân thủ mà không phải tự lo tầng hạ tầng đó.

## Yêu cầu
1. **Cả 3 store lên managed:** PostgreSQL → **RDS**, Redis/Valkey → **ElastiCache**, Kafka → **MSK**. Sau khi xong, **không còn pod DB / cache / queue tự host** trong cluster.
2. **Cutover an toàn:** không mất dữ liệu, không downtime khách - checkout giữ SLO ≥ 99% trong suốt quá trình chuyển.
3. **Bảo mật đúng chuẩn:** TLS in-transit, encryption at rest, credential để trong Secrets Manager (không plaintext trong env/manifest), endpoint **riêng tư** (DB/cache/queue không phơi ra public).
4. **Di trú dữ liệu đầy đủ:** schema + dữ liệu seed hiện có nạp sang managed, app đọc/ghi đúng như trước.
5. **Cost-aware:** right-size, giải thích chọn Multi-AZ hay single, nằm trong ngân sách.

## Ràng buộc
- Trong ngân sách hiện tại (~$300/tuần/TF).
- Storefront vẫn công khai, cổng vận hành vẫn riêng tư (Directive #1); không đụng / vô hiệu hóa flagd (Luật chơi).

## Phải nộp
- Cho mentor xem: 3 store đang chạy trên **RDS / ElastiCache / MSK**, app trỏ vào đó, **không còn pod data tự host**, kèm **bằng chứng data parity** (đếm/checksum trước - sau) và **rollback plan**. Mentor tự xác nhận.

## Được nhìn ở trụ nào
Chính là **Reliability** (managed HA + backup). Chạm **Cost Optimization** (right-size, Multi-AZ vs single), **Security** (TLS/encryption/secret/private endpoint) và **Auditability** (dấu vết cutover).

> Directive bắt buộc toàn TF. Điểm nằm ở chỗ **chuyển được cả ba store lên managed mà khách không hề hay biết** và dữ liệu toàn vẹn.
