data "archive_file" "alert_handler" {
  type        = "zip"
  source_file = "${path.module}/lambda_src/alert_handler.py"
  output_path = "${path.module}/.build/alert_handler.zip"
}

resource "aws_iam_role" "lambda_exec" {
  name = "${var.project_name}-lambda-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "lambda_perms" {
  name = "${var.project_name}-lambda-policy"
  role = aws_iam_role.lambda_exec.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["dynamodb:PutItem"]
        Resource = aws_dynamodb_table.events.arn
      },
      {
        Effect   = "Allow"
        Action   = ["sns:Publish"]
        Resource = aws_sns_topic.alerts.arn
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

resource "aws_lambda_function" "alert_handler" {
  function_name    = "${var.project_name}-alert-handler"
  filename         = data.archive_file.alert_handler.output_path
  source_code_hash = data.archive_file.alert_handler.output_base64sha256
  role             = aws_iam_role.lambda_exec.arn
  handler          = "alert_handler.handler"
  runtime          = "python3.12"
  timeout          = 10

  environment {
    variables = {
      DYNAMODB_TABLE = aws_dynamodb_table.events.name
      SNS_TOPIC_ARN  = aws_sns_topic.alerts.arn
    }
  }
}

resource "aws_lambda_permission" "allow_iot" {
  statement_id  = "AllowIoTInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.alert_handler.function_name
  principal     = "iot.amazonaws.com"
  source_arn    = aws_iot_topic_rule.alerts_to_lambda.arn
}

resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${aws_lambda_function.alert_handler.function_name}"
  retention_in_days = 14
}

resource "aws_cloudwatch_metric_alarm" "critical_alert_rate" {
  alarm_name          = "${var.project_name}-critical-alert-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Invocations"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 5
  alarm_description   = "Más de 5 alertas críticas en 5 minutos — posible intrusión"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    FunctionName = aws_lambda_function.alert_handler.function_name
  }
}
