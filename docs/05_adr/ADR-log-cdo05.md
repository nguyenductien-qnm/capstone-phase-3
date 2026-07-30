# Decision Log (ADR) - TF1 / CDO05

> Append-only. 1 quyết định lớn = 1 ADR. Không xóa ADR cũ.

---

## ADR-001 - Private ops access qua Tailscale L7 Ingress

- **Trạng thái:** Chấp nhận
- **Ngày:** 2026-07-13
- **Người ký:** Auzema
- **Trụ:** Security / Auditability / Reliability / Cost
- **Bối cảnh:** Storefront phải public, nhưng Grafana, Jaeger, ArgoCD và Load Generator không được public qua Envoy. Team tạm thời cần Cloudflare quick tunnel để truy cập storefront; mentor và grader cần ops access không phụ thuộc `kubectl port-forward`.
- **Quyết định:** Cài Tailscale Kubernetes Operator bằng OAuth. Expose Grafana, Jaeger, ArgoCD và Locust bằng bốn Tailscale L7 `Ingress`, mỗi endpoint có MagicDNS, TLS certificate và tag riêng. ACL chỉ cho `group:ops-reviewers` tới `tag:ops-grafana`, `tag:ops-jaeger`, `tag:ops-argocd` và `tag:ops-locust`. Xóa route public `/grafana`, `/jaeger`, `/loadgen`; giữ `/otlp-http/`. Giữ Cloudflare quick tunnel chỉ cho storefront và chỉ bật sau khi image Envoy đã rollout, ba public ops path trả `404`. ArgoCD backend chạy HTTP nội bộ qua `server.insecure`; TLS terminate tại Tailscale proxy.
- **Phương án khác đã cân:** Giữ Envoy public route bị loại vì vi phạm mandate. Tailscale L3 Service annotation bị loại vì không tự cấp TLS và khó tách policy theo web endpoint. Advertise toàn service CIDR bị loại vì blast radius rộng.
- **Cost Δ:** `$0/tuần` khi tailnet Personal không quá 6 users và 50 tagged resources; tổng không đổi so với trần `$300/tuần`. Vượt giới hạn phải review plan trước khi mời thêm user.
- **Ảnh hưởng SLO:** Storefront request path không đổi. Ops availability phụ thuộc Tailscale control plane, operator và proxy pod. Verify storefront `200`, public ops path `404`, Grafana `/grafana/`, Jaeger `/jaeger/ui/`, ArgoCD `/` và Locust `/` trả `200/302` trong tailnet; ngoài tailnet không resolve/reach.
- **Rollback:** Revert commit xóa Envoy route, rebuild/push `frontend-proxy`, rồi sync nếu cần khôi phục ops khẩn cấp. Xóa `tailscale-ingress` Application hoặc uninstall operator để gỡ private path; storefront không bị ảnh hưởng.
- **Hệ quả:** ✅ Ops không public, TLS browser hợp lệ, policy tách theo service, thay đổi GitOps audit được. ⚠️ Quick tunnel có URL public ngẫu nhiên, không auth và không được bật trước khi Envoy mới chặn ops routes. HTTP từ Tailscale proxy tới backend nằm trong cluster; ArgoCD cần rollout một lần sau khi `server.insecure` đổi; access audit mặc định ở mức device/user, không phải per-request.
- **Tham chiếu:** [Tailscale Kubernetes Operator Ingress](https://tailscale.com/docs/kubernetes-operator/ingress) · [Tailscale free plans](https://tailscale.com/kb/1154/free-plans-discounts)

---

> Thêm ADR mới ở dưới. ADR bị thay thế: đổi Trạng thái + link forward, giữ nguyên nội dung cũ.
