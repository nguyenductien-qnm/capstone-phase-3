variable "aws_region" {
  description = "Region hosting the guardrail. Must match where Nova/Titan are invoked."
  type        = string
  default     = "us-east-2"
}

variable "guardrail_name" {
  type    = string
  default = "aio-mandate06"
}

variable "grounding_threshold" {
  description = "Faithfulness threshold (0-1). Response below this vs source reviews = hallucination → block/fallback."
  type        = number
  default     = 0.7
}

variable "relevance_threshold" {
  description = "Relevance-to-query threshold (0-1)."
  type        = number
  default     = 0.7
}

variable "pii_entities" {
  description = "Bedrock built-in PII entity types to ANONYMIZE."
  type        = list(string)
  default = [
    "EMAIL",
    "PHONE",
    "CREDIT_DEBIT_CARD_NUMBER",
    "CREDIT_DEBIT_CARD_CVV",
    "US_SOCIAL_SECURITY_NUMBER",
    "NAME",
    "ADDRESS",
    "PASSWORD",
  ]
}
