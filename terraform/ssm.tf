# Secrets are stored via scripts/store_secrets.sh — Terraform reads them here.
data "aws_ssm_parameter" "telegram_bot_token" {
  name            = "/${var.project}/telegram_bot_token"
  with_decryption = true
}

data "aws_ssm_parameter" "telegram_chat_id" {
  name = "/${var.project}/telegram_chat_id"
}

resource "aws_ssm_parameter" "config_bucket" {
  name  = "/${var.project}/config_bucket_name"
  type  = "String"
  value = var.config_bucket_name
}
