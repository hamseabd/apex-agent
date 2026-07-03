#!/usr/bin/env bash
# One-time: create GitHub OIDC provider + scoped deploy role for CI/CD.
# Run once by the operator. Idempotent where possible.
set -euo pipefail

AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
GH_REPO="hamseabd/apex-agent"
PROJECT="apex"
ROLE_NAME="${PROJECT}_github_deploy"
OIDC_URL="token.actions.githubusercontent.com"
OIDC_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:oidc-provider/${OIDC_URL}"

echo "→ Ensuring GitHub OIDC provider exists..."
if ! aws iam get-open-id-connect-provider --open-id-connect-provider-arn "$OIDC_ARN" >/dev/null 2>&1; then
  aws iam create-open-id-connect-provider \
    --url "https://${OIDC_URL}" \
    --client-id-list "sts.amazonaws.com" \
    --thumbprint-list "ffffffffffffffffffffffffffffffffffffffff"
  echo "  created."
else
  echo "  already exists, skipping."
fi

echo "→ Creating deploy role trust policy..."
TRUST=$(cat <<JSON
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": { "Federated": "${OIDC_ARN}" },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": { "${OIDC_URL}:aud": "sts.amazonaws.com" },
      "StringLike": {
        "${OIDC_URL}:sub": [
          "repo:${GH_REPO}:ref:refs/heads/main",
          "repo:${GH_REPO}:environment:production"
        ]
      }
    }
  }]
}
JSON
)

if aws iam get-role --role-name "$ROLE_NAME" >/dev/null 2>&1; then
  echo "  role exists, updating trust policy..."
  aws iam update-assume-role-policy --role-name "$ROLE_NAME" --policy-document "$TRUST"
else
  aws iam create-role --role-name "$ROLE_NAME" --assume-role-policy-document "$TRUST" >/dev/null
  echo "  role created."
fi

echo "→ Attaching scoped inline permissions policy..."
PERMS=$(cat <<JSON
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "ecr:GetAuthorizationToken",
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ecr:BatchCheckLayerAvailability",
        "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload",
        "ecr:PutImage",
        "ecr:BatchGetImage"
      ],
      "Resource": "arn:aws:ecr:${AWS_REGION}:${AWS_ACCOUNT_ID}:repository/${PROJECT}"
    },
    {
      "Effect": "Allow",
      "Action": "lambda:UpdateFunctionCode",
      "Resource": [
        "arn:aws:lambda:${AWS_REGION}:${AWS_ACCOUNT_ID}:function:${PROJECT}_webhook",
        "arn:aws:lambda:${AWS_REGION}:${AWS_ACCOUNT_ID}:function:${PROJECT}_scheduler"
      ]
    }
  ]
}
JSON
)
aws iam put-role-policy --role-name "$ROLE_NAME" \
  --policy-name "${PROJECT}_deploy" --policy-document "$PERMS"

ROLE_ARN=$(aws iam get-role --role-name "$ROLE_NAME" --query 'Role.Arn' --output text)
echo ""
echo "✅ Done. Deploy role ARN:"
echo "   $ROLE_ARN"
echo ""
echo "Next steps (one time):"
echo "  1. Add repo variable:  gh variable set AWS_DEPLOY_ROLE_ARN --body \"$ROLE_ARN\""
echo "  2. Create the 'production' GitHub Environment with yourself as a required reviewer:"
echo "     GitHub → Settings → Environments → New environment → 'production' → Required reviewers."
