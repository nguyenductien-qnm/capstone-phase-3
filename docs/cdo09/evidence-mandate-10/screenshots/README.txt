ĐÃ CHỤP XONG PHẦN LỚN — cập nhật 26/07/2026.

Chú thích từng ảnh: mỗi ảnh NN-*.png có file NN-*.md đi kèm ngay cạnh.
Bảng tra nhanh toàn bộ 20 ảnh: INDEX.md
Danh sách lệnh chụp (giữ lại để chụp bổ sung): HUONG-DAN-CHUP.md

=== ĐỐI CHIẾU KẾ HOẠCH CHỤP CŨ -> ẢNH THỰC TẾ ===

A · TĨNH
  A1-ruleset              -> 15,16,17  ĐÃ CHỤP (3 required check, không phải 4:
                                       "Unit tests" gộp 2 check cũ, xem PR #340)
  A2-trivy-gate           -> CHƯA      bằng chứng dạng lệnh: app-build.yaml:485
  A3-ecr-immutable        -> CHƯA
  A4-cosign-verify        -> 20        gộp trong bảng trace provenance
  A5-build-scoped         -> CHƯA      bằng chứng: app-build.yaml confirm_full+reason

B · KYVERNO TRƯỚC ENFORCE
  B1-pods-kyverno         -> 01        ĐÃ CHỤP
  B2-policyreport-sach    -> 02        ĐÃ CHỤP
  B3-truoc-unsigned       -> 03        ĐÃ CHỤP  <- vế "trước"
  B4-policy-audit         -> 04        ĐÃ CHỤP
  B5-argocd-apps          -> 05,07     ĐÃ CHỤP

C · KYVERNO SAU ENFORCE
  C1-sau-unsigned-bi-chan -> 09        ĐÃ CHỤP  <- ẢNH GIÁ TRỊ NHẤT
  C2-signed-van-tao-duoc  -> 10        ĐÃ CHỤP
  C3-policyreport-day-du  -> 11        ĐÃ CHỤP
  C4-rollout-khong-ket    -> 12        ĐÃ CHỤP
  C5-techx-corp-synced    -> 13        ĐÃ CHỤP
  C6-do-tre-sau-enforce   -> 14        ĐÃ CHỤP
  C7-policy-enforce       -> 08        ĐÃ CHỤP

D · BA BÀI KIỂM MENTOR
  D1-ci-do-chan-merge     -> CHƯA      18 là PR XANH bị chặn vì out-of-date.
                                       Vẫn cần ảnh PR CỐ TÌNH ĐỎ -> merge xám.
  D2-admission-tu-choi    -> 09        ĐÃ CHỤP (dùng chung với C1)
  D3-provenance-chain     -> 19,20     ĐÃ CHỤP — 8 mắt xích, hơn 6 mắt dự kiến.
                                       provenance.sh đã thay bằng workflow
                                       trace-image-provenance.yaml

CẶP QUAN TRỌNG NHẤT: 03 <-> 09
Cùng một manifest, cùng một cụm, chỉ khác chế độ policy.
Kết quả lật từ "created" sang "blocked". Để cạnh nhau trong PR và video.

=== CÒN THIẾU (tính năng chưa làm, không phải quên chụp) ===
  YC2d  SAST      — grep 10 công cụ trên 13 workflow = 0 kết quả
  YC2b  IaC gate  — infra-cd.yaml exit-code:"0" + soft_fail:true, chưa chặn

=== ĐÃ XONG so với bản cũ (bản cũ ghi "chưa đạt") ===
  YC4a  action pin SHA      — grep uses:@vX = 0 (PR #346)
  YC4b  base image digest   — 57/57 dòng FROM có @sha256: (PR #377)
  YC5   provenance          — workflow trace-image-provenance.yaml (PR #385)
