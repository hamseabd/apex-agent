#!/usr/bin/env bash
# Deploy code changes (no Terraform, just image rebuild + Lambda update).
set -euo pipefail

AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
PROJECT="apex"

echo "→ Building Docker image..."
docker build -t "$PROJECT" .
docker tag "$PROJECT:latest" \
  "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$PROJECT:latest"

aws ecr get-login-password --region "$AWS_REGION" | \
  docker login --username AWS --password-stdin \
  "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"

docker push \
  "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$PROJECT:latest"

echo "→ Updating Lambda functions..."
for fn in "${PROJECT}_webhook" "${PROJECT}_scheduler"; do
  aws lambda update-function-code \
    --function-name "$fn" \
    --image-uri "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$PROJECT:latest" \
    --region "$AWS_REGION" \
    --output text \
    --query 'FunctionName'
done

echo "Deployed."
