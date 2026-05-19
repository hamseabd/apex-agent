output "webhook_url" {
  value       = "${aws_apigatewayv2_stage.default.invoke_url}/webhook"
  description = "Telegram webhook URL — register this with BotFather"
}

output "ecr_repository_url" {
  value       = aws_ecr_repository.apex.repository_url
  description = "ECR repository URL for Docker image pushes"
}
