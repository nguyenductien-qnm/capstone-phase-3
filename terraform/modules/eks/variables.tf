variable "project_name" {
  description = "Project name used for resource names"
  type        = string
}

variable "environment" {
  description = "Deployment environment"
  type        = string
}

variable "cluster_version" {
  description = "Explicit EKS Kubernetes version. Keep this reviewed instead of silently following latest."
  type        = string
}

variable "private_subnet_ids" {
  description = "Private application subnet IDs used by the EKS control plane ENIs and managed nodes"
  type        = list(string)

  validation {
    condition     = length(distinct(var.private_subnet_ids)) >= 2
    error_message = "EKS requires at least two distinct private subnets across the intended AZs."
  }
}

variable "endpoint_public_access" {
  description = "Enable the public Kubernetes API endpoint for operators outside the VPC"
  type        = bool
  default     = true
}

variable "public_access_cidrs" {
  description = "Trusted CIDRs allowed to reach the public Kubernetes API endpoint"
  type        = list(string)
  default     = []

  validation {
    condition = alltrue([
      for cidr in var.public_access_cidrs :
      can(cidrhost(cidr, 0))
    ])
    error_message = "public_access_cidrs must contain valid CIDRs."
  }
}

variable "enabled_cluster_log_types" {
  description = "EKS control-plane logs sent to CloudWatch"
  type        = list(string)
  default     = ["api", "audit", "authenticator"]

  validation {
    condition = alltrue([
      for log_type in var.enabled_cluster_log_types :
      contains(["api", "audit", "authenticator", "controllerManager", "scheduler"], log_type)
    ])
    error_message = "Unsupported EKS control-plane log type."
  }
}

variable "control_plane_log_retention_days" {
  description = "CloudWatch retention for EKS control-plane logs"
  type        = number
  default     = 30
}

variable "node_instance_types" {
  description = "Allowed EC2 instance types for the primary managed node group"
  type        = list(string)
}

variable "node_capacity_type" {
  description = "Managed node group capacity type"
  type        = string
  default     = "ON_DEMAND"

  validation {
    condition     = contains(["ON_DEMAND", "SPOT"], var.node_capacity_type)
    error_message = "node_capacity_type must be ON_DEMAND or SPOT."
  }
}

variable "node_disk_size_gib" {
  description = "Encrypted gp3 root volume size per node"
  type        = number
  default     = 50
}

variable "node_scaling" {
  description = "Managed node group scaling bounds"
  type = object({
    min_size     = number
    max_size     = number
    desired_size = number
  })

  validation {
    condition = (
      var.node_scaling.min_size >= 1 &&
      var.node_scaling.min_size <= var.node_scaling.desired_size &&
      var.node_scaling.desired_size <= var.node_scaling.max_size
    )
    error_message = "Node scaling must satisfy 1 <= min_size <= desired_size <= max_size."
  }
}

variable "node_labels" {
  description = "Labels applied to the primary managed node group"
  type        = map(string)
  default     = {}
}

variable "node_taints" {
  description = "Optional taints applied to the primary managed node group"
  type = list(object({
    key    = string
    value  = optional(string, "")
    effect = string
  }))
  default = []

  validation {
    condition = alltrue([
      for taint in var.node_taints :
      contains(["NO_SCHEDULE", "NO_EXECUTE", "PREFER_NO_SCHEDULE"], taint.effect)
    ])
    error_message = "Taint effect must be NO_SCHEDULE, NO_EXECUTE or PREFER_NO_SCHEDULE."
  }
}

variable "enable_core_addons" {
  description = "Manage CoreDNS, kube-proxy, VPC CNI and Pod Identity Agent as EKS add-ons"
  type        = bool
  default     = true
}

variable "enable_cluster_autoscaler" {
  description = "Create the IRSA role/policy for the Cluster Autoscaler (MANDATE-02 node autoscaling)"
  type        = bool
  default     = true
}

variable "access_entries" {
  description = <<-EOT
    EKS API access entries. For AWS IAM Identity Center, use the IAM role ARN:
    arn:aws:iam::<account>:role/aws-reserved/sso.amazonaws.com/<region>/AWSReservedSSO_<PermissionSet>_<suffix>
    Do not use arn:aws:sts::...:assumed-role/... session ARNs.
  EOT
  type = map(object({
    principal_arn      = string
    access_policy_name = string
    access_scope_type  = optional(string, "cluster")
    namespaces         = optional(list(string), [])
    kubernetes_groups  = optional(list(string), [])
  }))

  validation {
    condition = length(var.access_entries) > 0 && alltrue([
      for entry in values(var.access_entries) :
      can(regex("^arn:[^:]+:iam::[0-9]{12}:role/.+", entry.principal_arn)) &&
      !can(regex(":assumed-role/", entry.principal_arn))
    ])
    error_message = "At least one access entry is required, and every principal must be an IAM role ARN (not an STS assumed-role ARN)."
  }

  validation {
    condition = alltrue([
      for entry in values(var.access_entries) :
      contains([
        "AmazonEKSClusterAdminPolicy",
        "AmazonEKSAdminPolicy",
        "AmazonEKSEditPolicy",
        "AmazonEKSViewPolicy",
      ], entry.access_policy_name)
    ])
    error_message = "Use one of the supported AWS-managed EKS access policy names."
  }

  validation {
    condition = alltrue([
      for entry in values(var.access_entries) :
      contains(["cluster", "namespace"], entry.access_scope_type) &&
      (entry.access_scope_type == "cluster" || length(entry.namespaces) > 0)
    ])
    error_message = "Namespace-scoped entries require at least one namespace; scope must be cluster or namespace."
  }
}
