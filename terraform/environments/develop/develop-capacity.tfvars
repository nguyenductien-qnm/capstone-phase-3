# Non-secret capacity policy for the Develop environment.
#
# eks_node_instance_types stays pinned here for Mandate-19 continuity.
#
# MANDATE-13: removed the eks_node_scaling override that used to pin
# min=2/max=3/desired=3 for Mandate-19 Phase 2-3 (per-pod ceiling measurement,
# fixed node count so scale events didn't contaminate before/after numbers).
# That measurement is complete — evidence up through Phase 6-equivalent spike
# tests already exists (docs/mandate-19/loadtest/runs/flashsale-200u-max10,
# yc4-shed-rerun-20260722, both dated 2026-07-22, well past Phase 2-3). Karpenter
# is now the primary autoscaler (see platform/gitops/environments/develop/karpenter/),
# so MNG `primary` reverts to being just the on-demand floor — its actual sizing
# comes from `eks_node_scaling` in terraform/environments/develop/variables.tf,
# unshadowed by this file. Do not reintroduce this override without updating
# variables.tf in the same PR (explicit -var-file wins over the variable default —
# see environment-isolation-execution-guide §3.2 and mandate-13/EXECUTION-GUIDE.md §2.1).
eks_node_instance_types = ["t3.large"]

# The EKS module currently creates one dedicated observability node group.
eks_ops_node_instance_types = ["t3.large"]

# The shared Valkey module enables automatic failover and Multi-AZ, which
# requires at least two cache nodes. Keep this override Develop-only.
valkey_num_cache_clusters = 2

# Enable Multi-AZ deployment for Primary RDS in Develop
rds_multi_az = true

# Match the Product-like RDS topology while retaining smaller Develop instances.
enable_rds_proxy       = true
enable_read_replica    = true
replica_instance_class = "db.t4g.micro"

# Preserve the live Primary setting when Terraform attaches its logical-replication
# parameter group. Both parameters are static and take effect after a DB reboot.
rds_track_activity_query_size = 8192
