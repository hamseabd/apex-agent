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
