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

# --- reminders_tick: fires every hour, dispatches run_reminders ---

resource "aws_cloudwatch_event_rule" "reminders_tick" {
  name                = "${var.project}_reminders_tick"
  schedule_expression = "cron(${var.schedule_reminders_tick_utc} * * ? *)"
  description         = "Hourly tick — dispatches reminders matching current UTC hour from protocol"
}

resource "aws_cloudwatch_event_target" "reminders_tick" {
  rule      = aws_cloudwatch_event_rule.reminders_tick.name
  target_id = "apex_scheduler"
  arn       = aws_lambda_function.scheduler.arn
  input     = jsonencode({ job = "run_reminders" })
}

resource "aws_lambda_permission" "reminders_tick" {
  statement_id  = "AllowEventBridgeRemindersTick"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.scheduler.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.reminders_tick.arn
}

# --- missed_day_check: fires at 8pm EST (01:00 UTC) ---

resource "aws_cloudwatch_event_rule" "missed_day_check" {
  name                = "${var.project}_missed_day_check"
  schedule_expression = "cron(${var.schedule_missed_day_check_utc} * * ? *)"
  description         = "Evening nudge if no logs recorded today"
}

resource "aws_cloudwatch_event_target" "missed_day_check" {
  rule      = aws_cloudwatch_event_rule.missed_day_check.name
  target_id = "apex_scheduler"
  arn       = aws_lambda_function.scheduler.arn
  input     = jsonencode({ job = "missed_day_check" })
}

resource "aws_lambda_permission" "missed_day_check" {
  statement_id  = "AllowEventBridgeMissedDayCheck"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.scheduler.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.missed_day_check.arn
}

# --- weekly_summary: fires Sunday 6pm EST (23:00 UTC Sunday) ---

resource "aws_cloudwatch_event_rule" "weekly_summary" {
  name                = "${var.project}_weekly_summary"
  schedule_expression = "cron(${var.schedule_weekly_summary_utc} ? * SUN *)"
  description         = "Sunday evening weekly summary across all tracked metrics"
}

resource "aws_cloudwatch_event_target" "weekly_summary" {
  rule      = aws_cloudwatch_event_rule.weekly_summary.name
  target_id = "apex_scheduler"
  arn       = aws_lambda_function.scheduler.arn
  input     = jsonencode({ job = "weekly_summary" })
}

resource "aws_lambda_permission" "weekly_summary" {
  statement_id  = "AllowEventBridgeWeeklySummary"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.scheduler.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.weekly_summary.arn
}
