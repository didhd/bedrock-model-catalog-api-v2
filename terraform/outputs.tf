output "cloudfront_domain" {
  description = "CloudFront distribution domain name"
  value       = aws_cloudfront_distribution.catalog.domain_name
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID"
  value       = aws_cloudfront_distribution.catalog.id
}

output "api_base_url" {
  description = "Base URL for the API"
  value       = "https://${var.domain_name != "" ? var.domain_name : aws_cloudfront_distribution.catalog.domain_name}/v1"
}

output "s3_bucket_name" {
  description = "S3 bucket name"
  value       = aws_s3_bucket.catalog.id
}

output "lambda_function_name" {
  description = "Lambda function name for manual invocation"
  value       = aws_lambda_function.collector.function_name
}

output "lambda_function_arn" {
  description = "Lambda function ARN"
  value       = aws_lambda_function.collector.arn
}
