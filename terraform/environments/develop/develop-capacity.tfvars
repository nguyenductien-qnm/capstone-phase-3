# Non-secret capacity policy for the Develop environment.
# Three application nodes fixed to mirror Production primary MNG for load-test
# parity (Mandate-19): at 1 replica/service the 2-node baseline already ran CPU
# requests at 56-95% allocatable and left ml-guard Pending. Enabling prod-like
# HPA (min=2 on the core flow services) needs the third node to schedule without
# Pending. Kept min=max=desired so no node is added mid-run (Mandate-19: fixed
# infrastructure). The EKS module also creates one fixed Ops node.
eks_node_instance_types = ["t3.large"]

eks_node_scaling = {
  min_size     = 3
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
