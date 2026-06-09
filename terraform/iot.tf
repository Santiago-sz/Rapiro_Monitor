resource "aws_iot_thing" "rapiro" {
  name = "${var.project_name}-thing"
}

resource "aws_iot_certificate" "rapiro" {
  active = true
}

resource "aws_iot_policy" "rapiro_publish" {
  name = "${var.project_name}-publish-policy"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["iot:Connect"]
        Resource = "arn:aws:iot:${var.aws_region}:*:client/${aws_iot_thing.rapiro.name}"
      },
      {
        Effect   = "Allow"
        Action   = ["iot:Publish"]
        Resource = "arn:aws:iot:${var.aws_region}:*:topic/rapiro/events/*"
      }
    ]
  })
}

resource "aws_iot_thing_principal_attachment" "rapiro" {
  thing     = aws_iot_thing.rapiro.name
  principal = aws_iot_certificate.rapiro.arn
}

resource "aws_iot_policy_attachment" "rapiro" {
  policy = aws_iot_policy.rapiro_publish.name
  target = aws_iot_certificate.rapiro.arn
}

resource "aws_iot_topic_rule" "events_to_lambda" {
  name        = "${replace(var.project_name, "-", "_")}_events_rule"
  enabled     = true
  sql         = "SELECT * FROM 'rapiro/events/+'"
  sql_version = "2016-03-23"

  lambda {
    function_arn = aws_lambda_function.alert_handler.arn
  }
}
