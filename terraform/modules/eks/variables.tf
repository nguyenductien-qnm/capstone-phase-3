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

  validation {
    condition = contains([
      1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545,
      731, 1096, 1827, 2192, 2557, 2922, 3288, 3653,
    ], var.control_plane_log_retention_days)
    error_message = "control_plane_log_retention_days must be a CloudWatch Logs supported retention value."
  }
}

variable "enable_control_plane_log_kms" {
  description = "Encrypt the EKS control-plane CloudWatch log group with a customer-managed KMS key"
  type        = bool
  default     = true
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

variable "ops_node_subnet_id" {
  description = "Single private subnet used by the dedicated observability managed node group"
  type        = string

  validation {
    condition     = can(regex("^subnet-[0-9a-f]+$", var.ops_node_subnet_id))
    error_message = "ops_node_subnet_id must be a valid subnet ID."
  }
}

variable "ops_node_instance_types" {
  description = "Allowed EC2 instance types for the dedicated observability managed node group"
  type        = list(string)
  default     = ["m6a.large"]

  validation {
    condition     = length(var.ops_node_instance_types) > 0
    error_message = "ops_node_instance_types must contain at least one instance type."
  }
}

variable "ops_node_disk_size_gib" {
  description = "Encrypted gp3 root volume size for the observability node"
  type        = number
  default     = 30

  validation {
    condition     = var.ops_node_disk_size_gib >= 20
    error_message = "ops_node_disk_size_gib must be at least 20 GiB."
  }
}

variable "enable_core_addons" {
  description = "Manage CoreDNS, kube-proxy, VPC CNI and Pod Identity Agent as EKS add-ons"
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

# CDO-219 (Mandate 17 — R3): bật enforce NetworkPolicy ở VPC CNI (aws-eks-nodeagent).
# Mặc định false để KHÔNG ảnh hưởng các environment khác dùng chung module này (vd develop).
# Chỉ set true ở environment sở hữu cluster cần khoanh mạng (sandbox = ecommerce-dev-eks).
variable "enable_network_policy" {
  description = "Enable AWS VPC CNI NetworkPolicy enforcement (aws-node ENABLE_NETWORK_POLICY)."
  type        = bool
  default     = false
}

# MANDATE-13: dự định rào (gate) SQS interruption queue + EventBridge rule của
# Karpenter bằng biến này để chỉ bật ở develop, tránh tạo resource mới bên
# sandbox dùng chung module (environment-isolation-execution-guide §Case T3).
# THỰC TẾ (đã xác minh khi audit mở rộng Mandate-13 sang sandbox, 27-07-2026):
# biến này KHÔNG được tham chiếu ở bất kỳ đâu trong karpenter.tf — không có
# `count`/`dynamic` nào dùng nó. `aws_sqs_queue.karpenter_interruption`, các
# `aws_cloudwatch_event_rule`/`_target`, và statement `AllowInterruptionQueueActions`
# đều tạo VÔ ĐIỀU KIỆN cho mọi environment gọi module này. Trên thực tế sandbox
# đã có các resource này từ trước (PR #415/#386, sáng kiến Karpenter riêng của
# sandbox, commit 6df27a6/b68b16f — không liên quan Mandate-13), và ArgoCD
# `platform/gitops/applications/karpenter.yaml` của sandbox đã trỏ
# `interruptionQueue: ecommerce-dev-eks-karpenter` từ trước. Nghĩa là claim "sandbox
# plan sẽ ra No changes nhờ biến này" trong ADR Mandate-13 đúng ngẫu nhiên (vì
# resource vốn đã tồn tại ở sandbox từ nguồn khác), KHÔNG phải nhờ cơ chế gate.
# KHÔNG thêm `count = var.enable_karpenter_interruption_queue ? 1 : 0` vào các
# resource trên mà không kiểm tra state trước — sandbox default của biến này là
# `false`, thêm gate ngay bây giờ sẽ khiến apply tiếp theo DESTROY queue/rule/policy
# đang chạy thật của sandbox.
variable "enable_karpenter_interruption_queue" {
  description = "Không dùng ở đâu trong module hiện tại (dead variable) — xem comment phía trên trước khi wire lại hoặc xoá."
  type        = bool
  default     = false
}
variable "enable_vpc_cni_prefix_delegation" {
  description = "Enable AWS VPC CNI prefix delegation to increase pod density on worker nodes."
  type        = bool
  default     = false
}

variable "vpc_cni_warm_prefix_target" {
  description = "WARM_PREFIX_TARGET value for AWS VPC CNI when prefix delegation is enabled."
  type        = number
  default     = 1

  validation {
    condition     = var.vpc_cni_warm_prefix_target >= 1
    error_message = "vpc_cni_warm_prefix_target must be at least 1."
  }
}
