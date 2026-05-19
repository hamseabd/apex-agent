#!/usr/bin/env bash
# Store Telegram credentials in SSM Parameter Store.
# Run once before bootstrap.sh
set -euo pipefail

AWS_REGION="${AWS_REGION:-us-east-1}"

echo "Storing Apex secrets in SSM (region: $AWS_REGION)..."

read -p "Telegram bot token: " BOT_TOKEN
read -p "Telegram chat ID: " CHAT_ID

aws ssm put-parameter \
  --name "/apex/telegram_bot_token" \
  --value "$BOT_TOKEN" \
  --type SecureString \
  --overwrite \
  --region "$AWS_REGION"

aws ssm put-parameter \
  --name "/apex/telegram_chat_id" \
  --value "$CHAT_ID" \
  --type String \
  --overwrite \
  --region "$AWS_REGION"

echo "Done. Secrets stored."
