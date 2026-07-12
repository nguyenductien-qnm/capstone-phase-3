# Non-secret EKS access configuration. Identity Center group IDs cannot be used
# directly; EKS Access Entries require the persistent permission-set IAM roles.

# Sandbox tradeoff: expose the Kubernetes API publicly for distributed TF1
# members. Authentication and authorization still require SSO + Access Entry.
# The EKS module rejects world-open CIDRs outside environment=dev.
eks_endpoint_public_access = true
eks_public_access_cidrs    = ["0.0.0.0/0"]

eks_access_entries = {
  mentor = {
    principal_arn      = "arn:aws:iam::804372444787:role/aws-reserved/sso.amazonaws.com/AWSReservedSSO_Phase3-Mentor-PermissionSet_05d2f6060a74cb33"
    access_policy_name = "AmazonEKSClusterAdminPolicy"
    access_scope_type  = "cluster"
  }

  cdo5_and_cdo9 = {
    principal_arn      = "arn:aws:iam::804372444787:role/aws-reserved/sso.amazonaws.com/AWSReservedSSO_Phase3-CDO-PermissionSet_29ab4c042f467568"
    access_policy_name = "AmazonEKSClusterAdminPolicy"
    access_scope_type  = "cluster"
  }

  aio = {
    principal_arn      = "arn:aws:iam::804372444787:role/aws-reserved/sso.amazonaws.com/AWSReservedSSO_Phase3-AIO-PermissionSet_7897382fd3255fbb"
    access_policy_name = "AmazonEKSAdminPolicy"
    access_scope_type  = "namespace"
    namespaces         = ["techx-tf1"]
  }
}
