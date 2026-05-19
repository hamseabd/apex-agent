# Morning check-in — 7:00 AM ET (12:00 UTC, adjust for DST)
resource "aws_cloudwatch_event_rule" "morning_checkin" {
  name                = "${var.project}_morning_checkin"
  schedule_expression = "cron(0 12 * * ? *)"
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
