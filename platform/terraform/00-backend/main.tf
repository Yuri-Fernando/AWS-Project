# Stack 00 — bucket do remote state das demais stacks (padrão do workshop, Dia 1 05:00–05:38).
# State desta stack é LOCAL (ovo e galinha). Lock nativo do S3 (use_lockfile) nas outras stacks: sem DynamoDB.

terraform {
  required_version = ">= 1.10"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
  backend "local" {}
}

variable "noncurrent_version_expiration_days" {
  description = "Dias até expirar versões antigas do state."
  type        = number
  default     = 30
}

resource "aws_s3_bucket" "state" {
  bucket        = "${local.name_prefix}-tfstate"
  force_destroy = local.is_emulator # no lab local pode apagar com conteúdo; na AWS real, protegido
}

resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id
  rule {
    bucket_key_enabled = true
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "state" {
  bucket                  = aws_s3_bucket.state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "state" {
  depends_on = [aws_s3_bucket_versioning.state]
  bucket     = aws_s3_bucket.state.id
  rule {
    id     = "expire-noncurrent-versions"
    status = "Enabled"
    filter {}
    noncurrent_version_expiration {
      noncurrent_days = var.noncurrent_version_expiration_days
    }
  }
}

output "state_bucket" {
  value = aws_s3_bucket.state.id
}

output "state_bucket_arn" {
  value = aws_s3_bucket.state.arn
}
