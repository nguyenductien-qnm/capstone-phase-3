# Non-secret capacity policy for the Develop environment.
#
# Node sizing for the Mandate-19 throughput-ceiling load test. Production primary
# MNG runs min=2/desired=2/max=6 (elastic via Karpenter overflow), NOT a fixed
# size -- so develop deliberately diverges during the measurement phases:
#
#   Phase 2-3 (per-pod ceiling): pin desired=3, max=3 so no node is added mid-run
#   -- node count jumping bac would otherwise contaminate before/after ceiling
#   numbers (master plan section 4, "Nhieu 3"). Three app nodes are required
#   because at 1 replica/service the 2-node baseline already ran CPU requests at
#   56-95% allocatable, so prod-like HPA (min=2 core flow) left pods Pending on
#   two nodes. The EKS module also creates one fixed Ops node.
#
#   Phase 6 (spike/recovery): raise max_size = 6 to match prod and observe
#   HPA/Karpenter scale-out. Separate apply, only when entering Phase 6.
eks_node_instance_types = ["t3.large"]

# min_size stays at the live value 2 (safety floor). EKS UpdateNodegroupConfig
# validates minSize against the *current* desiredSize, so pushing min=3 here
# fails "Minimum capacity 3 can't be greater than desired size 2" while desired
# is still 2. desired=3/max=3 is valid in a single apply and already guarantees
# three fixed nodes for Phase 2-3, so min stays 2.
eks_node_scaling = {
  min_size     = 2
  max_size     = 3
  desired_size = 3
}

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
