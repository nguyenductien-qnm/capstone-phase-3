# Non-secret worker capacity policy for the Develop environment.
# The primary application node group starts at one replica and can scale to three.
eks_node_instance_types = ["t3.large"]

eks_node_scaling = {
  min_size     = 1
  max_size     = 3
  desired_size = 1
}

# The EKS module currently creates one dedicated observability node group.
eks_ops_node_instance_types = ["t3.large"]
