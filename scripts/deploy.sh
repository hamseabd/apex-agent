#!/usr/bin/env bash
# Deploy code changes (no Terraform, just image rebuild + Lambda update).
set -euo pipefail

AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
PROJECT="apex"
GIT_SHA=$(git rev-parse --short HEAD)
ECR_REPO="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$PROJECT"
IMAGE_TAG="v$GIT_SHA"

echo "→ Building Docker image ($IMAGE_TAG)..."
docker build -t "$PROJECT" .
docker tag "$PROJECT:latest" "$ECR_REPO:$IMAGE_TAG"

aws ecr get-login-password --region "$AWS_REGION" | \
  docker login --username AWS --password-stdin \
  "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"

docker push "$ECR_REPO:$IMAGE_TAG"

echo "→ Updating Lambda functions..."
for fn in "${PROJECT}_webhook" "${PROJECT}_scheduler"; do
  aws lambda update-function-code \
    --function-name "$fn" \
    --image-uri "$ECR_REPO:$IMAGE_TAG" \
    --region "$AWS_REGION" \
    --output text \
    --query 'FunctionName'
done

echo "Deployed."
