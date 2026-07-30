# [DIRECTIVE #10] Từ commit tới cluster - không tin image mù

**Từ:** Ban Bảo mật Nền tảng & Tuân thủ - TechX Corp
**Hiệu lực:** khi nhận · hoàn tất & nộp trước **hết ngày 20/07/2026**
**Áp dụng:** toàn bộ Task Force

---

## Bối cảnh
Hệ đang chạy production, nhưng đường từ code → image → cluster của các TF phần lớn **chạy cho có**: CI đỏ vẫn merge được, image ra cluster mà **không ai chứng minh được nó sạch, từ đâu, ai duyệt**. Một pipeline bị chiếm, một image độc, hay một thay đổi nhỏ cuốn cả hệ rebuild-redeploy - đều đủ để hạ cả service. Directive này siết chuỗi giao hàng phần mềm tới mức **chứng minh được, không tin mù**.

## Yêu cầu
Chấm **kết quả**, không chấm có-làm-hay-không.

1. **Cổng chặn thật.** CI đỏ = **không merge, không deploy**. Bật branch protection + required status checks trên nhánh deploy. Hết cảnh "pipeline chạy cho vui" - test/scan/render phải xanh mới qua.
2. **Quét trước khi ra cluster, chặn trên HIGH/CRITICAL.** Image CVE scan + IaC misconfig scan + secret/SAST là **cổng chặn**, không phải hậu kiểm (ECR scan-on-push **không tính**). Dính HIGH/CRITICAL thì dừng, không đẩy tiếp.
3. **Bất biến + xác thực nguồn gốc.** Registry để **immutable**; mỗi image được **ký (cosign) + kèm SBOM + provenance**; cluster **chỉ chạy image đã ký, tham chiếu theo digest** - admission **enforce** (không phải audit/cảnh báo suông).
4. **Không phụ thuộc thứ trôi.** GitHub Action pin theo **commit SHA**; base image pin theo **digest**. Không `@latest`, không `@master`, không tag trôi ở bước dựng.
5. **Truy ngược được.** Với **một pod bất kỳ đang chạy**, dựng lại được chuỗi: image digest → commit → **PR ai duyệt** → scan nào đã pass → **ai/khóa nào ký** → SBOM.
6. **Chỉ đụng cái gì đổi.** Một thay đổi nhỏ **không được** kéo rebuild + redeploy cả hệ. Build/deploy có phạm vi theo service thay đổi; nếu có đường "full rebuild" thì phải hẹp và có lý do, không phải mặc định mỗi lần merge - để giữ blast-radius nhỏ và không đốt chi phí vô ích.

## Ràng buộc
- Trong ngân sách; giữ SLO trong suốt.
- Storefront vẫn công khai, cổng vận hành vẫn riêng tư (Directive #1); không đụng / vô hiệu hóa flagd.
- Không phá kiến trúc để lấy điểm ngắn hạn.

## Phải nộp
Cho mentor **tự bấm nút kiểm**, không nghe khai:
- Mở PR với **CI cố tình đỏ** → phải **bị chặn merge**.
- Thử deploy một image **chưa ký / chưa scan** → admission phải **từ chối**.
- Chỉ vào **một pod đang chạy** → team **truy ngược full provenance** (commit → PR duyệt → scan pass → chữ ký → SBOM) ngay trước mặt.

## Được nhìn ở trụ nào
Chính là **Security** (chuỗi cung ứng, quét, ký, bất biến) và **Auditability** (truy nguồn gốc, ai duyệt/ký). Xuyên suốt là **Operational Excellence** (kỷ luật giao hàng). Chạm **Reliability** (deploy an toàn, blast-radius nhỏ) và **Cost Optimization** (không rebuild thừa).

> Directive bắt buộc toàn TF, thi head-to-head. Điểm nằm ở chỗ: một image bất kỳ trên cluster **chứng minh được là sạch, bất biến, ký bởi pipeline có cổng chặn, và truy được về commit + người duyệt** - chứ không phải "tin là nó ổn".
