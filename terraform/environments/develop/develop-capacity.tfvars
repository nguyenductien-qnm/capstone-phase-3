# Non-secret capacity policy for the Develop environment.
# Keep two application nodes fixed; the EKS module also creates one fixed Ops node.
eks_node_instance_types = ["t3.large"]

eks_node_scaling = {
  min_size     = 2
  max_size     = 2
  desired_size = 2
}

# The EKS module currently creates one dedicated observability node group.
eks_ops_node_instance_types = ["t3.large"]

# The shared Valkey module enables automatic failover and Multi-AZ, which
# requires at least two cache nodes. Keep this override Develop-only.
valkey_num_cache_clusters = 2
