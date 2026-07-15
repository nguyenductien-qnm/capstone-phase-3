# Non-secret primary worker capacity policy for the sandbox environment.
# infra-cd passes this file after the secret tfvars so the fixed MNG values stay authoritative.
eks_node_instance_types = ["t3.large"]

eks_node_scaling = {
  min_size     = 2
  max_size     = 6
  desired_size = 2
}
