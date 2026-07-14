# Non-secret primary worker capacity policy for the sandbox environment.
# infra-cd passes this file after the secret tfvars so the fixed MNG values stay authoritative.
eks_node_instance_types = ["t3.medium"]

eks_node_scaling = {
  min_size     = 3
  max_size     = 4
  desired_size = 3
}
