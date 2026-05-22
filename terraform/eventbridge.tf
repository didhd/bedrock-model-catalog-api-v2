# EventBridge rule for daily collection
resource "aws_cloudwatch_event_rule" "daily_collection" {
  name                = "${var.project_name}-daily"
  description         = "Trigger Bedrock model metadata collection daily at 06:00 UTC"
  schedule_expression = var.schedule_expression
}

resource "aws_cloudwatch_event_target" "lambda" {
  rule = aws_cloudwatch_event_rule.daily_collection.name
  arn  = aws_lambda_function.collector.arn
}

resource "aws_lambda_permission" "eventbridge" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.collector.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily_collection.arn
}
