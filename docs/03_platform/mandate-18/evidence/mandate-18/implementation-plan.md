# MANDATE-18 implementation plan

## Guardrails

- Read-only baseline trước mọi mutation.
- Không apply Terraform hoặc delete resource nếu chưa có plan/manifest được duyệt.
- Không touch/disable `flagd`.
- Không public Grafana, Jaeger hoặc ArgoCD.
- Không giảm audit/security retention chỉ để tạo delta cost.
- Before/after dùng cùng workload, filter, window và đơn vị.

## Sequence

1. Capture scope, Git SHA và operator identity đã redact.
2. Capture non-compute Usage Quantity và chọn top driver theo từng usage type.
3. Inventory orphan resources; phân loại `KEEP`, `DELETE_CANDIDATE`, `UNKNOWN`.
4. Verify gp3, volume/PVC usage và lifecycle.
5. Measure NAT/cross-AZ; evaluate S3 gateway and conditional interface endpoints.
6. Measure telemetry ingestion/cardinality/retention.
7. Propose minimal changes with Terraform/Helm plan and rollback.
8. Re-run equivalent workload; verify SLO and investigation.
9. Capture delayed Cost Explorer after data when available.

## Current execution state

| Phase | State | Exit needed |
|---|---|---|
| Scope and baseline | COMPLETE | Raw logs 01, 02, 03, 05, 06, 07, 08, 09 and 11 exist |
| Orphan decision | BLOCKED | Confirm owner/project for three target groups; no deletion without full ARN approval |
| Storage implementation | PARTIAL | gp3 verified; collect full-window usage and protected plan before any migration |
| Data-transfer implementation | PARTIAL | Module test passes; obtain remote-state access and full plan; then reviewed rollout |
| Telemetry implementation | PARTIAL | Debug code rendered; ISM remains gated pending owner and backup |
| Runtime verification | FAIL/PARTIAL | Storefront p95 must be <1s; exemplar hop lacks data |
| Usage after/delta | BLOCKED | Rollout plus same scope/window/Usage Type data required |
| PR/CI/review | PENDING | Exact diff, plan, screenshots and approvals required |

## Sprint-to-PR closure plan

1. **Permissions:** request read access to the S3 backend object only; rerun
   `terraform plan` with protected variables through the approved CI
   environment. Reject the plan if any unexpected delete/replace appears.
2. **Ownership:** ask platform/network owner to classify the three target
   groups. Keep `testt` on HOLD because it is in another VPC unless its owner
   explicitly approves cleanup.
3. **Latency:** query Jaeger for frontend-proxy traces over 1 second in the exact
   SLO window, fix the confirmed downstream/route bottleneck, then rerun the
   same load-generator mix until p95 is below 1 second.
4. **Telemetry:** deploy debug removal first. After stability, obtain backup
   and retention-owner approval before enabling ISM in a separate change.
5. **Network:** after a one-add/zero-destroy protected plan, deploy the S3
   Gateway Endpoint; keep NAT and verify image pull/AWS API/public storefront.
6. **After window:** repeat Cost Explorer and CloudWatch using the exact usage
   types/windows in `mandate-18.md`; wait for CE data finalization where needed.
7. **Evidence:** capture every mandatory screenshot and run the trace drill;
   redact account/customer data before commit.
8. **PR:** attach plan summary, rollback, raw evidence, screenshots, CI URL and
   reviewer approval. Do not call the PR complete while after usage is absent.

## Exit criteria

Xem `../EVIDENCE-INDEX.md`. Không có runtime evidence thì trạng thái tối đa là
`PARTIAL`. Completion additionally requires:

- all five directive requirements PASS or an explicit mentor-approved
  exception;
- complete Terraform plan with zero unexpected destroy/replace;
- same-Usage-Type before/after delta;
- SLO thresholds and investigation drill PASS;
- actual screenshots, PR/CI and reviewer evidence.
