# Plan bật IaC scan thành cổng chặn — chờ review

**Trạng thái hiện tại**: cả 2 scan chạy nhưng KHÔNG chặn
- `infra-cd.yaml` Trivy config: `exit-code: "0"`
- `infra-cd.yaml` Checkov: `soft_fail: true`

**Nếu bật chặn ngay hôm nay**: CI đỏ lập tức, không ai merge được PR nào chạm `terraform/`.

## Số thật (chạy checkov 3.3.8 local, 23/07)

| Công cụ | Kết quả |
|---|---|
| Checkov | 637 pass · **119 fail** · 59 loại check |
| Trivy config | **10 CRITICAL · 7 HIGH** |

Finding theo module:
```
29x rds        17x modules      15x cloudfront   12x cost_guard
10x eks         8x cloudtrail    8x msk           6x vpc
 6x develop     4x elasticache   2x ai-guardrails 2x external-dns-irsa
```

---

## Phân loại đề xuất — 4 nhóm

### NHÓM 1 — Bỏ qua, có lý do kiến trúc (không sửa được)

| Check | Số | Lý do |
|---|---|---|
| `CKV_AWS_382` + Trivy `AWS-0104` | 4 + 10 | Egress `0.0.0.0/0`. Pod PHẢI gọi Rekor/Fulcio (Sigstore) để Kyverno verify chữ ký, cộng ECR + Bedrock + Secrets Manager. Chặn egress = Kyverno chết. Thu hẹp được thì phải liệt kê IP range Sigstore — chúng đổi thường xuyên, sẽ thành nguồn sự cố |
| `CKV_AWS_38` `CKV_AWS_39` | 2 | EKS public endpoint. Đang bật có chủ đích để CI/GitHub Actions apply được. Đã giới hạn bằng `eks_public_access_cidrs` |
| `CKV_AWS_130` | 4 | Subnet public gán IP công khai — đúng bản chất subnet public (NAT/ALB nằm đó) |
| `CKV2_AWS_5` | 1 | Security group chưa gắn resource — SG dự phòng |

**Tổng nhóm 1: ~21 finding.** Viết vào file skip kèm lý do.

### NHÓM 2 — Bỏ qua vì chi phí (môi trường học/capstone)

| Check | Số | Chi phí nếu bật |
|---|---|---|
| `CKV_AWS_157` Multi-AZ RDS | 2 | ×2 tiền RDS |
| `CKV_AWS_144` S3 cross-region replication | 2 | ×2 tiền lưu trữ + transfer |
| `CKV_AWS_68` `CKV2_AWS_47` WAF cho CloudFront | 4 | ~$5-10/tháng + phí request |
| `CKV_AWS_118` `CKV_AWS_353` RDS enhanced monitoring + performance insights | 6 | phí CloudWatch |
| `CKV_AWS_338` giữ log 1 năm | 5 | phí lưu CloudWatch |
| `CKV_AWS_117` Lambda trong VPC | 2 | cần NAT, thêm tiền |

**Tổng nhóm 2: ~21 finding.** Ràng buộc directive nói "trong ngân sách" — đây là lý do chính đáng, nhưng phải ghi rõ chứ không im lặng bỏ qua.

### NHÓM 3 — SỬA ĐƯỢC, nên sửa (ưu tiên theo mức độ)

| Check | Số | Việc phải làm | Rủi ro |
|---|---|---|---|
| `CKV_AWS_58` EKS secret encryption | 1 | thêm KMS key cho envelope encryption | **đụng cluster prod đang chạy** — cần cửa sổ bảo trì |
| `CKV_AWS_7` xoay vòng CMK | 1 | thêm `enable_key_rotation = true` | thấp, apply được ngay |
| `CKV_AWS_293` deletion protection RDS | 3 | thêm `deletion_protection = true` | thấp, nhưng destroy sau này phải tắt tay |
| `CKV_AWS_226` minor upgrade tự động | 3 | `auto_minor_version_upgrade = true` | thấp |
| `CKV2_AWS_60` copy tag sang snapshot | 3 | `copy_tags_to_snapshot = true` | không |
| `CKV_AWS_26` mã hoá SNS | 3 | thêm `kms_master_key_id` | thấp |
| `CKV_AWS_158` mã hoá CloudWatch log | 3 | thêm KMS key | thấp, tốn ít tiền KMS |
| `CKV_AWS_149` Secrets Manager dùng CMK | 4 | thay key mặc định bằng CMK | trung bình — secret đang dùng |
| `CKV2_AWS_57` xoay vòng secret tự động | 6 | RDS đã có rotation, còn secret khác | trung bình |
| `CKV_AWS_37` bật đủ log EKS | 1 | thêm log type còn thiếu | thấp, tốn tiền log |
| `CKV2_AWS_11` VPC flow log | 1 | bật flow log | thấp, tốn tiền |
| `CKV2_AWS_12` default SG chặn hết | 1 | thêm rule rỗng | thấp |

**Tổng nhóm 3: ~30 finding.** Đây là phần việc thật, ước tính 2-4 giờ.

### NHÓM 4 — Cần xem từng cái mới quyết được

| Check | Số | Vì sao phải xem |
|---|---|---|
| `CKV_AWS_356` `CKV_AWS_355` IAM `*` resource | 7 | Một số bắt buộc (`ecr:GetAuthorizationToken` chỉ nhận `*`), số khác thu hẹp được |
| `CKV_AWS_111` `CKV_AWS_109` `CKV_AWS_290` IAM ghi không ràng buộc | 7 | Xem từng policy |
| `CKV_AWS_108` data exfiltration | 1 | Xem policy nào |
| `CKV_AWS_274` AdministratorAccess | 1 | **Đáng lo nhất** — role nào đang có quyền admin? |
| `CKV_AWS_61` assume role mọi service | 1 | Xem trust policy |
| Nhóm Lambda (`115` `116` `173` `50` `272`) | 10 | cost_guard_automation — cân nhắc từng cái |
| Nhóm CloudFront (`86` `310` `305` `374` `174` `CKV2_AWS_32`) | 11 | Phần lớn là tính năng thêm, không phải lỗ hổng |
| Nhóm S3 (`18` `300` `145` `CKV2_AWS_61` `CKV2_AWS_62`) | 7 | Bucket CloudTrail — vài cái nên sửa |
| Nhóm RDS còn lại (`129` `161` `CKV2_AWS_30`) | 5 | Query logging tốn tiền, IAM auth đụng app |

**Tổng nhóm 4: ~50 finding.** Cần đọc từng cái, không quyết được từ tên check.

---

## Thứ tự thực hiện đề xuất

```
1. Sửa nhóm 3 phần dễ (rotation, deletion protection, copy tags, SNS)  ~1h
   -> giảm ~15 finding, không rủi ro

2. Đọc nhóm 4, quyết từng cái                                          ~2h
   -> ưu tiên xem CKV_AWS_274 (AdministratorAccess) trước

3. Viết file skip cho nhóm 1 + 2, mỗi dòng có lý do + ngày review      ~30'
   -> theo đúng kiểu .trivyignore hiện tại đang làm với CVE

4. Sửa CKV_AWS_58 (EKS secret encryption) — cần cửa sổ bảo trì         riêng

5. RỒI MỚI bật exit-code: 1 và soft_fail: false
```

**Không bật gate trước khi làm xong bước 1-3.** Bật trước thì cả team không merge
được gì trong lúc mình xử.

## File cần tạo

`.checkov.yaml` ở gốc repo:
```yaml
# Mỗi skip PHẢI có lý do + ngày review, theo đúng kỷ luật .trivyignore đang dùng cho CVE
skip-check:
  - CKV_AWS_382  # egress 0.0.0.0/0 — pod cần Rekor/Fulcio/ECR/Bedrock. Review: 2026-10-23
  - CKV_AWS_157  # Multi-AZ RDS — ngoài ngân sách capstone. Review: 2026-10-23
  # ...
```

Thêm mục IaC vào `.trivyignore` (file đã có sẵn cho CVE):
```
AVD-AWS-0104  # egress 0.0.0.0/0 — như trên
```

## Câu hỏi cần chốt trước khi làm

1. **Có sửa `CKV_AWS_58` (EKS secret encryption) không?** Đụng cluster prod đang
   chạy, cần cửa sổ bảo trì. Bỏ qua thì mất một điểm bảo mật thật.
2. **Nhóm 2 (chi phí) bỏ qua hết hay sửa vài cái?** WAF cho CloudFront ~$5-10/tháng,
   có thể chấp nhận được.
3. **Làm việc này trước hay sau `provenance.sh`?** provenance.sh chặn bài kiểm mentor
   bấm nút trực tiếp; IaC gate chỉ là điểm trừ trên giấy.

## Danh sách 119 finding đầy đủ

Chạy lại để xem chi tiết:
```bash
python3 -m venv /tmp/cvenv && /tmp/cvenv/bin/pip install checkov
/tmp/cvenv/bin/checkov -d terraform --framework terraform --compact
```
