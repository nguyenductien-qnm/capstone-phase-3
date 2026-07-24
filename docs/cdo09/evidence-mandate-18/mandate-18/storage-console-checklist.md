# Mandate 18 — AWS/Grafana storage screenshot checklist

Use `us-east-1`, show the selected time window and redact account/user identifiers. Do not hide resource name, type, size, state, unit or utilization.

## EBS type, size and attachment

1. AWS Console → EC2 → Elastic Block Store → Volumes.
2. Filter the instance/PVC resources belonging to `ecommerce-dev-eks`.
3. Show columns: Volume ID, Type, Size, State, Availability Zone, Attached resources and Created time.
4. Confirm all nine rows show `gp3` and `in-use`.
5. Capture `05a-ebs-gp3-scope.png`.

## PVC utilization

1. Grafana → Explore → Prometheus → Table.
2. Run:
   - `kubelet_volume_stats_capacity_bytes{namespace="techx-tf1"}`
   - `kubelet_volume_stats_used_bytes{namespace="techx-tf1"}`
   - `kubelet_volume_stats_available_bytes{namespace="techx-tf1"}`
3. Keep timestamp and `persistentvolumeclaim` labels visible.
4. Capture `05b-pvc-utilization.png`.

## Node root utilization

1. Capture the terminal/kubelet `stats/summary` table that maps node/provider ID to capacity, used and available bytes.
2. Keep the corresponding EC2 volume size visible in a second pane if possible.
3. Capture `05c-node-root-headroom.png`.

## Snapshot and DLM

1. EC2 → Snapshots → Owned by me; show the empty result and region.
2. Capture `06a-snapshots-owned-empty.png`.
3. EC2 → Lifecycle Manager → EBS snapshot policies; show the empty result.
4. Capture `06b-dlm-empty.png`.

An empty list proves the baseline only; do not label it “lifecycle enabled”.

## CloudTrail S3 lifecycle

1. S3 → `ecommerce-dev-cloudtrail-logs` → Management → Lifecycle rules.
2. Open `archive-and-retain-audit-logs`.
3. Show Enabled, transition after 90 days to Glacier Instant Retrieval and expiration after 2555 days.
4. Capture `06c-cloudtrail-lifecycle.png`.

## Terraform state bucket gap

1. S3 → `terraform-state-phase-3` → Properties; show Versioning status.
2. S3 → Management → Lifecycle rules; show no lifecycle configuration.
3. Capture `06d-terraform-state-controls-gap.png`.

Do not enable versioning/lifecycle from the console. This bucket is a shared backend and requires owner review plus Terraform management.

## Terraform tests

1. Capture terminal output for `terraform fmt -check -recursive` and `terraform validate -no-color` showing exit 0/success.
2. Capture the plan blocker listing only missing variable names, never their values.
3. Capture `06e-terraform-storage-tests.png`.

Do not claim a clean plan or zero destroy/replace until protected inputs produce a complete plan.
