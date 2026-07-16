# Lambda execution role
resource "aws_iam_role" "lambda" {
  name = "${var.project_name}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

# CloudWatch Logs
resource "aws_iam_role_policy" "lambda_logs" {
  name = "${var.project_name}-lambda-logs"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "${aws_cloudwatch_log_group.lambda.arn}:*"
      }
    ]
  })
}

# Bedrock read-only (list models & profiles)
resource "aws_iam_role_policy" "lambda_bedrock" {
  name = "${var.project_name}-lambda-bedrock"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock:ListFoundationModels",
          "bedrock:GetFoundationModel",
          "bedrock:ListInferenceProfiles",
          # bedrock-mantle (OpenAI-compatible endpoint) uses a separate IAM
          # namespace. Needed to list Mantle models via GET /v1/models.
          "bedrock-mantle:ListModels",
          "bedrock-mantle:GetModel",
          "bedrock-mantle:ListProjects",
          "bedrock-mantle:GetProject"
        ]
        Resource = "*"
      }
    ]
  })
}

# Pricing API (read-only)
resource "aws_iam_role_policy" "lambda_pricing" {
  name = "${var.project_name}-lambda-pricing"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = "pricing:GetProducts"
        Resource = "*"
      }
    ]
  })
}

# S3 write to catalog bucket only
resource "aws_iam_role_policy" "lambda_s3" {
  name = "${var.project_name}-lambda-s3"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = "s3:PutObject"
        Resource = [
          "${aws_s3_bucket.catalog.arn}/v1/*",
          "${aws_s3_bucket.catalog.arn}/v2/*"
        ]
      }
    ]
  })
}
