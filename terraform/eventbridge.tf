# 12:00 UTC = 7:00 AM EST / 8:00 AM EDT. Adjust var.morning_checkin_utc for DST if needed.
resource "aws_cloudwatch_event_rule" "morning_checkin" {
  name                = "${var.project}_morning_checkin"
  schedule_expression = "cron(${var.morning_checkin_utc} * * ? *)"
  description         = "Daily morning check-in reminder"
}

resource "aws_cloudwatch_event_target" "morning_checkin" {
  rule      = aws_cloudwatch_event_rule.morning_checkin.name
  target_id = "apex_scheduler"
  arn       = aws_lambda_function.scheduler.arn
  input     = jsonencode({ job = "morning_checkin" })
}

resource "aws_lambda_permission" "morning_checkin" {
  statement_id  = "AllowEventBridgeMorningCheckin"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.scheduler.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.morning_checkin.arn
}
