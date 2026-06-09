variable "aws_region" {
  default = "us-east-1"
}

variable "project" {
  default = "apex"
}

variable "config_bucket_name" {
  description = "S3 bucket for apex.yaml protocol. Must be globally unique across all AWS accounts."
}

variable "morning_checkin_utc" {
  description = "Cron minute/hour for morning check-in in UTC. 12:00 UTC = 7:00 AM EST / 8:00 AM EDT."
  default     = "0 12"
}

variable "schedule_reminders_tick_utc" {
  description = "Cron minute/hour for the hourly reminder tick. Fires every hour on the hour."
  # NOTE: AWS EventBridge uses UTC. This runs every hour — matches reminder times set in apex.yaml.
  # Reminder times in apex.yaml must also be in UTC (e.g. 10am EST = 15:00 UTC).
  default = "0 *"
}

variable "schedule_missed_day_check_utc" {
  description = "Cron minute/hour for the missed-day nudge."
  # NOTE: AWS EventBridge uses UTC. 8pm EST = 01:00 UTC (next day). 8pm EDT = 00:00 UTC.
  default = "0 1"
}

variable "schedule_weekly_summary_utc" {
  description = "Cron minute/hour for the Sunday weekly summary."
  # NOTE: AWS EventBridge uses UTC. Sunday 6pm EST = 23:00 UTC Sunday.
  default = "0 23"
}
