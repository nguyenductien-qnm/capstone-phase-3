# IRSA role for AI workloads that call Amazon Bedrock runtime.
# The trust policy is scoped to one Kubernetes ServiceAccount.

locals {
  # oidc_issuer_url has the form https://oidc.eks.<region>.amazonaws.com/id/XXXX.
  # IAM condition keys use the issuer URL without the https:// prefix.
  oidc_provider_url = replace(var.oidc_issuer_url, "https://", "")

  foundation_model_arns = [
    for model_id in var.foundation_model_ids :
    "arn:aws:bedrock:${var.aws_region}::foundation-model/${model_id}"
  ]

  # Include both account-scoped and AWS-managed inference profile ARN forms.
  # Bedrock system inference profiles vary by profile type, so keeping both
  # avoids blocking Converse when the runtime routes through a profile.
  inference_profile_arns = [
    "arn:aws:bedrock:${var.aws_region}:${data.aws_caller_identity.current.account_id}:inference-profile/*",
    "arn:aws:bedrock:${var.aws_region}::inference-profile/*",
  ]
}

data "aws_caller_identity" "current" {}

data "aws_iam_policy_document" "trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [var.oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_provider_url}:sub"
      values   = ["system:serviceaccount:${var.service_account_namespace}:${var.service_account_name}"]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_provider_url}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "this" {
  name               = "${var.project_name}-${var.environment}-ai-bedrock"
  assume_role_policy = data.aws_iam_policy_document.trust.json

  tags = {
    Name        = "${var.project_name}-${var.environment}-ai-bedrock"
    Environment = var.environment
    Project     = var.project_name
  }
}

data "aws_iam_policy_document" "bedrock_runtime" {
  statement {
    sid    = "InvokeNovaModels"
    effect = "Allow"
    actions = [
      "bedrock:InvokeModel",
      "bedrock:InvokeModelWithResponseStream",
    ]
    resources = concat(local.foundation_model_arns, local.inference_profile_arns)
  }

  statement {
    sid    = "ReadBedrockInferenceMetadata"
    effect = "Allow"
    actions = [
      "bedrock:GetInferenceProfile",
      "bedrock:ListFoundationModels",
      "bedrock:ListInferenceProfiles",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "bedrock_runtime" {
  name   = "bedrock-runtime-nova"
  role   = aws_iam_role.this.id
  policy = data.aws_iam_policy_document.bedrock_runtime.json
}
