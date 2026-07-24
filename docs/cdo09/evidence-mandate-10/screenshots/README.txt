Đặt ảnh chụp vào thư mục này, đúng tên file dưới đây.
Lệnh chụp: HUONG-DAN-CHUP.md  ·  Tình trạng repo: ../AUDIT-DIRECTIVE-10.md

Chụp theo thứ tự A -> B -> C -> D. Mỗi nhóm là một lần ngồi.

=== A · TĨNH (lúc nào cũng chụp được) ===
  A1-ruleset.png              4 required status checks trên develop
  A2-trivy-gate.png           severity CRITICAL,HIGH + exit-code 1
  A3-ecr-immutable.png        imageTagMutability = IMMUTABLE
  A4-cosign-verify.png        cosign verify + verify-attestation chạy thật
  A5-build-scoped.png         CI run chỉ build service đổi

=== B · KYVERNO TRƯỚC ENFORCE (chụp TRƯỚC khi merge!) ===
  B1-pods-kyverno.png                4 pod Running + PDB ALLOWED DISRUPTIONS=1
  B2-policyreport-sach.png           report PASS, FAIL=0
  B3-truoc-unsigned-duoc-nhan.png    pod KHÔNG chữ ký vẫn được nhận    <- vế "trước"
  B4-policy-audit.png                "Audit / Ignore"
  B5-argocd-apps.png                 ArgoCD kyverno + kyverno-policies

=== C · KYVERNO SAU ENFORCE (sau merge + sync techx-corp-root) ===
  C1-sau-unsigned-bi-chan.png        pod KHÔNG chữ ký BỊ CHẶN    <- ẢNH GIÁ TRỊ NHẤT
  C2-signed-van-tao-duoc.png         pod đã ký OK + image mutate @sha256
  C3-policyreport-day-du.png         report phủ hết pod, kể cả aiops
  C4-rollout-khong-ket.png           rollout restart frontend hoàn tất
  C5-techx-corp-van-synced.png       autogen:none chặn vòng lặp drift
  C6-do-tre-sau-enforce.png          so với baseline lúc Audit
  C7-policy-enforce.png              "Enforce / Fail"

=== D · BA BÀI KIỂM MENTOR BẤM NÚT ===
  D1-ci-do-chan-merge.png     PR có CI đỏ -> nút Merge bị khoá
  D2-admission-tu-choi.png    = C1, chụp 1 lần dùng 2 chỗ
  D3-provenance-chain.png     chỉ vào pod -> truy ngược 6 mắt   <- CẦN provenance.sh

CẶP QUAN TRỌNG NHẤT: B3 <-> C1
Cùng một lệnh, hai kết quả trái ngược. Để cạnh nhau trong PR và video.

KHÔNG chụp được (repo chưa đạt — xem AUDIT):
  YC2b IaC scan chưa chặn · YC2d không có SAST · YC4a action chưa pin SHA
  YC4b base image chưa pin digest · YC5 chưa có provenance.sh (chặn D3)
