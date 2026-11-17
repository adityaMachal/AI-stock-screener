variable "aws_region" {
  default = "us-east-1"
}

variable "instance_type" {
  default = "m7i-flex.large" # Eligible for Free Tier in this account (2 vCPUs, 8GB RAM)
}

variable "key_name" {
  description = "Name of the AWS key pair"
  type        = string
}
