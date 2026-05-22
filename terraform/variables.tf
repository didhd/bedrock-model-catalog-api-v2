variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "bedrock-model-catalog-v2"
}

variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
  default     = "us-east-1"
}

variable "collection_regions" {
  description = "Regions to collect Bedrock model metadata from"
  type        = list(string)
  default     = []  # empty = use ALL_BEDROCK_REGIONS in handler
}

variable "primary_region" {
  description = "Primary region for inference profile collection"
  type        = string
  default     = "us-east-1"
}

variable "schedule_expression" {
  description = "EventBridge schedule expression for data collection"
  type        = string
  default     = "cron(0 6 * * ? *)"
}

variable "lambda_memory_size" {
  description = "Lambda function memory in MB"
  type        = number
  default     = 512
}

variable "lambda_timeout" {
  description = "Lambda function timeout in seconds"
  type        = number
  default     = 900
}

variable "domain_name" {
  description = "Custom domain name for CloudFront (optional)"
  type        = string
  default     = ""
}

variable "route53_zone_id" {
  description = "Route53 hosted zone ID for custom domain"
  type        = string
  default     = ""
}

variable "waf_rate_limit" {
  description = "WAF rate limit (requests per 5 minutes per IP)"
  type        = number
  default     = 1000
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default = {
    Project     = "bedrock-model-catalog"
    ManagedBy   = "terraform"
    Environment = "production"
  }
}
