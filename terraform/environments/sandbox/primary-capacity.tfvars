# Non-secret primary worker capacity policy for the sandbox environment.
# infra-cd passes this file after the secret tfvars so the fixed MNG values stay authoritative.
<<<<<<< HEAD
eks_node_instance_types = ["t3.large"]

eks_node_scaling = {
  min_size     = 2
  max_size     = 6
=======
eks_node_instance_types = ["t3.medium"]

eks_node_scaling = {
  min_size     = 2
  max_size     = 3
>>>>>>> 57ab1fa (feat(audit): implement CDO-46 CDO-105 CDO-106 auditability)
  desired_size = 2
}
