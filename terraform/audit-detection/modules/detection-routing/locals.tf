locals {
  action_rules = {
    cloudtrail_tampering = {
      category    = "audit_collection_tampering"
      description = "Detect changes that can disable or weaken CloudTrail audit collection"
      event_pattern = jsonencode({
        "detail-type" = ["AWS API Call via CloudTrail"]
        detail = {
          eventSource = ["cloudtrail.amazonaws.com"]
          eventName   = ["StopLogging", "DeleteTrail", "UpdateTrail", "PutEventSelectors", "PutInsightSelectors"]
        }
      })
    }
    cloudwatch_log_tampering = {
      category    = "cloudwatch_audit_log_tampering"
      description = "Detect deletion, retention, or KMS changes to CloudWatch Logs"
      event_pattern = jsonencode({
        "detail-type" = ["AWS API Call via CloudTrail"]
        detail = {
          eventSource = ["logs.amazonaws.com"]
          eventName   = ["DeleteLogGroup", "DeleteLogStream", "PutRetentionPolicy", "DeleteRetentionPolicy", "AssociateKmsKey", "DisassociateKmsKey"]
        }
      })
    }
    s3_audit_tampering = {
      category    = "audit_s3_bucket_tampering"
      description = "Detect destructive or control-plane changes to S3 audit evidence buckets"
      event_pattern = jsonencode({
        "detail-type" = ["AWS API Call via CloudTrail"]
        detail = {
          eventSource = ["s3.amazonaws.com"]
          eventName   = ["DeleteBucket", "DeleteBucketPolicy", "PutBucketPolicy", "PutBucketVersioning", "DeleteBucketEncryption", "PutBucketEncryption", "DeleteBucketLifecycle", "PutBucketLifecycleConfiguration", "PutObjectLockConfiguration"]
        }
      })
    }
    kms_audit_tampering = {
      category    = "audit_kms_key_tampering"
      description = "Detect destructive or security-control changes to KMS keys"
      event_pattern = jsonencode({
        "detail-type" = ["AWS API Call via CloudTrail"]
        detail = {
          eventSource = ["kms.amazonaws.com"]
          eventName   = ["DisableKey", "ScheduleKeyDeletion", "PutKeyPolicy", "DisableKeyRotation", "RevokeGrant"]
        }
      })
    }
    iam_credential_persistence = {
      category    = "iam_credential_persistence"
      description = "Detect IAM operations that create persistent identities or credentials"
      event_pattern = jsonencode({
        "detail-type" = ["AWS API Call via CloudTrail"]
        detail = {
          eventSource = ["iam.amazonaws.com"]
          eventName   = ["CreateAccessKey", "UpdateAccessKey", "CreateLoginProfile", "UpdateLoginProfile", "CreateUser", "CreateRole", "UpdateAssumeRolePolicy"]
        }
      })
    }
    iam_privilege_escalation = {
      category    = "iam_privilege_escalation"
      description = "Detect IAM policy and membership changes that can increase privileges"
      event_pattern = jsonencode({
        "detail-type" = ["AWS API Call via CloudTrail"]
        detail = {
          eventSource = ["iam.amazonaws.com"]
          eventName   = ["AttachRolePolicy", "AttachUserPolicy", "AttachGroupPolicy", "PutRolePolicy", "PutUserPolicy", "PutGroupPolicy", "CreatePolicy", "CreatePolicyVersion", "SetDefaultPolicyVersion", "AddUserToGroup"]
        }
      })
    }
    iam_guardrail_removal = {
      category    = "iam_guardrail_removal"
      description = "Detect removal or replacement of IAM policies and permissions boundaries"
      event_pattern = jsonencode({
        "detail-type" = ["AWS API Call via CloudTrail"]
        detail = {
          eventSource = ["iam.amazonaws.com"]
          eventName   = ["DetachRolePolicy", "DetachUserPolicy", "DetachGroupPolicy", "DeleteRolePolicy", "DeleteUserPolicy", "DeleteGroupPolicy", "DeletePolicy", "DeletePolicyVersion", "DeleteRolePermissionsBoundary", "DeleteUserPermissionsBoundary", "PutRolePermissionsBoundary", "PutUserPermissionsBoundary"]
        }
      })
    }
    eks_access_changes = {
      category    = "eks_access_changes"
      description = "Detect EKS access-entry, access-policy, and cluster configuration changes"
      event_pattern = jsonencode({
        "detail-type" = ["AWS API Call via CloudTrail"]
        detail = {
          eventSource = ["eks.amazonaws.com"]
          eventName   = ["CreateAccessEntry", "UpdateAccessEntry", "DeleteAccessEntry", "AssociateAccessPolicy", "DisassociateAccessPolicy", "UpdateClusterConfig"]
        }
      })
    }
    secrets_manager_changes = {
      category    = "protected_secret_changes"
      description = "Detect destructive or policy and value changes in Secrets Manager"
      event_pattern = jsonencode({
        "detail-type" = ["AWS API Call via CloudTrail"]
        detail = {
          eventSource = ["secretsmanager.amazonaws.com"]
          eventName   = ["DeleteSecret", "PutResourcePolicy", "DeleteResourcePolicy", "CancelRotateSecret", "UpdateSecret", "PutSecretValue", "UpdateSecretVersionStage"]
        }
      })
    }
    network_exposure = {
      category    = "private_network_exposure"
      description = "Detect security-group, network ACL, and VPC endpoint changes"
      event_pattern = jsonencode({
        "detail-type" = ["AWS API Call via CloudTrail"]
        detail = {
          eventSource = ["ec2.amazonaws.com"]
          eventName   = ["AuthorizeSecurityGroupIngress", "ModifySecurityGroupRules", "CreateNetworkAclEntry", "ReplaceNetworkAclEntry", "DeleteVpcEndpoints"]
        }
      })
    }
    destructive_eks = {
      category    = "destructive_crown_jewel"
      description = "Detect EKS cluster deletion"
      event_pattern = jsonencode({
        "detail-type" = ["AWS API Call via CloudTrail"]
        detail = {
          eventSource = ["eks.amazonaws.com"]
          eventName   = ["DeleteCluster"]
        }
      })
    }
    destructive_rds = {
      category    = "destructive_crown_jewel"
      description = "Detect RDS instance or cluster deletion"
      event_pattern = jsonencode({
        "detail-type" = ["AWS API Call via CloudTrail"]
        detail = {
          eventSource = ["rds.amazonaws.com"]
          eventName   = ["DeleteDBInstance", "DeleteDBCluster"]
        }
      })
    }
    destructive_elasticache = {
      category    = "destructive_crown_jewel"
      description = "Detect ElastiCache replication-group deletion"
      event_pattern = jsonencode({
        "detail-type" = ["AWS API Call via CloudTrail"]
        detail = {
          eventSource = ["elasticache.amazonaws.com"]
          eventName   = ["DeleteReplicationGroup"]
        }
      })
    }
    destructive_msk = {
      category    = "destructive_crown_jewel"
      description = "Detect Amazon MSK cluster deletion"
      event_pattern = jsonencode({
        "detail-type" = ["AWS API Call via CloudTrail"]
        detail = {
          eventSource = ["kafka.amazonaws.com"]
          eventName   = ["DeleteCluster"]
        }
      })
    }
    destructive_elb = {
      category    = "destructive_crown_jewel"
      description = "Detect Elastic Load Balancing load-balancer deletion"
      event_pattern = jsonencode({
        "detail-type" = ["AWS API Call via CloudTrail"]
        detail = {
          eventSource = ["elasticloadbalancing.amazonaws.com"]
          eventName   = ["DeleteLoadBalancer"]
        }
      })
    }
    destructive_vpc = {
      category    = "destructive_crown_jewel"
      description = "Detect VPC deletion"
      event_pattern = jsonencode({
        "detail-type" = ["AWS API Call via CloudTrail"]
        detail = {
          eventSource = ["ec2.amazonaws.com"]
          eventName   = ["DeleteVpc"]
        }
      })
    }
  }

  identity_rules = merge(
    {
      root_activity = {
        category    = "root_activity"
        description = "Detect any AWS activity performed with root credentials"
        event_pattern = jsonencode({
          detail = {
            userIdentity = {
              type = ["Root"]
            }
          }
        })
      }
    },
    length(var.break_glass_role_arns) > 0 ? {
      break_glass_assume_role = {
        category    = "break_glass_access"
        description = "Detect use of named break-glass or audit-administrator roles"
        event_pattern = jsonencode({
          "detail-type" = ["AWS API Call via CloudTrail"]
          detail = {
            eventSource = ["sts.amazonaws.com"]
            eventName   = ["AssumeRole"]
            requestParameters = {
              roleArn = sort(tolist(var.break_glass_role_arns))
            }
          }
        })
      }
    } : {}
  )

  audit_rules = merge(local.action_rules, local.identity_rules)
}
