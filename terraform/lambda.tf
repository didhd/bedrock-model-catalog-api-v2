# Lambda layer for dependencies
resource "null_resource" "lambda_deps" {
  triggers = {
    requirements = filemd5("${path.module}/../lambda/requirements.txt")
  }

  provisioner "local-exec" {
    command = <<-EOT
      rm -rf ${path.module}/../lambda/package
      pip install -r ${path.module}/../lambda/requirements.txt \
        -t ${path.module}/../lambda/package/python \
        --quiet --no-cache-dir
    EOT
  }
}

data "archive_file" "lambda_layer" {
  type        = "zip"
  source_dir  = "${path.module}/../lambda/package"
  output_path = "${path.module}/../lambda/layer.zip"
  depends_on  = [null_resource.lambda_deps]
}

resource "aws_lambda_layer_version" "deps" {
  filename            = data.archive_file.lambda_layer.output_path
  source_code_hash    = data.archive_file.lambda_layer.output_base64sha256
  layer_name          = "${var.project_name}-deps"
  compatible_runtimes = ["python3.12"]
}

# Lambda function
data "archive_file" "lambda" {
  type        = "zip"
  source_dir  = "${path.module}/../lambda"
  output_path = "${path.module}/../lambda/lambda.zip"

  excludes = [
    "package",
    "layer.zip",
    "lambda.zip",
    "requirements.txt",
  ]
}

resource "aws_lambda_function" "collector" {
  function_name    = "${var.project_name}-collector"
  filename         = data.archive_file.lambda.output_path
  source_code_hash = data.archive_file.lambda.output_base64sha256
  handler          = "handler.handler"
  runtime          = "python3.12"
  memory_size      = var.lambda_memory_size
  timeout          = var.lambda_timeout
  role             = aws_iam_role.lambda.arn

  layers = [aws_lambda_layer_version.deps.arn]

  environment {
    variables = {
      S3_BUCKET      = aws_s3_bucket.catalog.id
      PRIMARY_REGION = var.primary_region
    }
  }

  reserved_concurrent_executions = 1

  tracing_config {
    mode = "Active"
  }
}

# CloudWatch Log Group with retention
resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${var.project_name}-collector"
  retention_in_days = 30
}

# X-Ray tracing policy
resource "aws_iam_role_policy" "lambda_xray" {
  name = "${var.project_name}-lambda-xray"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "xray:PutTraceSegments",
          "xray:PutTelemetryRecords"
        ]
        Resource = "*"
      }
    ]
  })
}
