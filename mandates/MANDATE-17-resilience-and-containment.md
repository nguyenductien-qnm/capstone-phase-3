# [DIRECTIVE #17] Chịu được sự cố, khoanh được kẻ xâm nhập

**Từ:** Ban SRE & Bảo mật Nền tảng - TechX Corp
**Hiệu lực:** khi nhận · hoàn tất & nộp trước **hết ngày 21/07/2026**
**Áp dụng:** toàn bộ Task Force (phần CDO)

---

## Bối cảnh
Hệ thật đối mặt hai loại biến cùng lúc: một thành phần **chết bất ngờ** (dependency lỗi, một AZ trục trặc), và nguy cơ **một pod bị chiếm**. Directive này bắt hệ vững ở cả hai: (a) một mảnh chết mà luồng ra tiền không sập, (b) nếu một pod bị chiếm thì thiệt hại bị **khoanh nhỏ**, không lan ra cả cluster.

## Yêu cầu
**Reliability - chịu lỗi:**
1. **Sống qua một dependency chết.** Một service downstream (ad / recommendation / payment-provider ...) lỗi hoặc chậm → luồng browse → cart → checkout **vẫn giữ SLO** nhờ timeout + fallback + degrade graceful; lỗi không lan ngược. (Khác Directive #3 - đó là bảo trì **có kế hoạch**; đây là **chết bất ngờ**.)
2. **Chịu được mất cả một AZ.** Không chỉ mất 1 node (Directive #3 đã lo qua drain có kế hoạch) - mà một **vùng khả dụng (AZ) sập bất ngờ**: workload trải đủ nhiều AZ để luồng ra tiền vẫn giữ SLO khi mất trọn một AZ.

**Security - khoanh blast-radius:**
3. **Khoanh mạng (NetworkPolicy).** Mỗi pod chỉ nói được với đúng thứ nó cần; một pod bị chiếm **không quét / kết nối được khắp cluster** (chặn lateral movement); egress bị khóa - không cho gọi ra ngoài tùy tiện.
4. **Least-privilege ở tầng Kubernetes (RBAC / service account / token).** Mỗi service dùng service account riêng, quyền RBAC tối thiểu, không mount token quá rộng - pod bị chiếm **không gọi được K8s API ngoài quyền tối thiểu**, không leo ra quyền cluster. (Phần hardening Linux runtime - root / caps / privilege-escalation - đã có Directive #5.)

## Ràng buộc
- Trong ngân sách; giữ SLO; không đụng flagd; storefront public, ops private.
- Tập trung vào **chịu lỗi + khoanh vùng runtime** - không phải khôi phục dữ liệu.

## Phải nộp
- Mentor tự **giết một dependency** (service downstream) **hoặc chặn một AZ** và thấy **luồng ra tiền vẫn giữ SLO**.
- Cho mentor xem **NetworkPolicy khoanh** đang bật, và thử một **pod "kẻ tấn công"**: nó **không quét / kết nối được** sang service khác và **không gọi ra ngoài** được - chứng minh containment, không phải mô tả trên slide.

## Được nhìn ở trụ nào
**Reliability** (chịu lỗi bất ngờ, fallback, chịu mất AZ) và **Security** (khoanh blast-radius: NetworkPolicy + least-privilege K8s RBAC, chặn lateral movement + egress). Chạm **Operational Excellence** (vận hành có kỷ luật khi sự cố).

> Directive bắt buộc toàn TF. Điểm nằm ở chỗ: một mảnh chết **khách không hề hay biết**, và một pod bị chiếm **không kéo theo cả hệ** - hệ vừa dẻo vừa kín.
