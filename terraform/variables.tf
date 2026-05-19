variable "aws_region" {
  default = "us-east-1"
}

variable "project" {
  default = "apex"
}

variable "config_bucket_name" {
  description = "S3 bucket for apex.yaml protocol. Must be globally unique across all AWS accounts."
}
