#!/usr/bin/env bash
# First-time setup: provision AWS infrastructure + deploy initial image.
set -euo pipefail

AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
PROJECT="apex"

echo "→ Applying Terraform..."
cd "$(dirname "$0")/../terraform"
terraform init
terraform apply -auto-approve

echo "→ Building and pushing Docker image..."
cd ..
aws ecr get-login-password --region "$AWS_REGION" | \
  docker login --username AWS --password-stdin \
  "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"

docker build -t "$PROJECT" .
docker tag "$PROJECT:latest" \
  "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$PROJECT:latest"
docker push \
  "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$PROJECT:latest"

echo "→ Updating Lambda functions..."
aws lambda update-function-code \
  --function-name "${PROJECT}_webhook" \
  --image-uri "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$PROJECT:latest" \
  --region "$AWS_REGION"

aws lambda update-function-code \
  --function-name "${PROJECT}_scheduler" \
  --image-uri "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$PROJECT:latest" \
  --region "$AWS_REGION"

WEBHOOK_URL=$(cd terraform && terraform output -raw webhook_url)
echo "→ Registering Telegram webhook: $WEBHOOK_URL"
BOT_TOKEN=$(aws ssm get-parameter \
  --name "/apex/telegram_bot_token" \
  --with-decryption \
  --query "Parameter.Value" \
  --output text \
  --region "$AWS_REGION")
# Optional webhook secret — created by store_secrets.sh. When present, Telegram
# sends it as X-Telegram-Bot-Api-Secret-Token and the Lambda rejects mismatches
# (requires TELEGRAM_WEBHOOK_SECRET in the Lambda environment).
WEBHOOK_SECRET=$(aws ssm get-parameter \
  --name "/apex/telegram_webhook_secret" \
  --with-decryption \
  --query "Parameter.Value" \
  --output text \
  --region "$AWS_REGION" 2>/dev/null || true)

SECRET_PARAM=""
if [[ -n "$WEBHOOK_SECRET" ]]; then
  SECRET_PARAM="&secret_token=$WEBHOOK_SECRET"
fi
curl -s "https://api.telegram.org/bot$BOT_TOKEN/setWebhook?url=$WEBHOOK_URL$SECRET_PARAM" | python3 -m json.tool

echo ""
echo "Apex deployed!"
echo "Open Telegram and send /setup to configure your protocol."
