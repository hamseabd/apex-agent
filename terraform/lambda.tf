locals {
  lambda_env = {
    TELEGRAM_BOT_TOKEN = data.aws_ssm_parameter.telegram_bot_token.value
    TELEGRAM_CHAT_ID   = data.aws_ssm_parameter.telegram_chat_id.value
    CONFIG_BUCKET      = var.config_bucket_name
    TABLE_NAME         = aws_dynamodb_table.apex.name
    AWS_REGION         = var.aws_region
    POWERTOOLS_SERVICE_NAME = "apex"
    LOG_LEVEL          = "INFO"
  }
}

resource "aws_lambda_function" "webhook" {
  function_name = "${var.project}_webhook"
  role          = aws_iam_role.lambda.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.apex.repository_url}:latest"
  timeout       = 30
  memory_size   = 512

  image_config {
    command = ["lambda_webhook.handler"]
  }

  environment {
    variables = local.lambda_env
  }

  tracing_config {
    mode = "Active"
  }
}

resource "aws_lambda_function" "scheduler" {
  function_name = "${var.project}_scheduler"
  role          = aws_iam_role.lambda.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.apex.repository_url}:latest"
  timeout       = 60
  memory_size   = 256

  image_config {
    command = ["lambda_scheduler.handler"]
  }

  environment {
    variables = local.lambda_env
  }

  tracing_config {
    mode = "Active"
  }
}
