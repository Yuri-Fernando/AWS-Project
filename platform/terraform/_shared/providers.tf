# Provider AWS com ALVO DUPLO — copiado (link lógico) em cada stack de platform/terraform/NN-*/.
#   TARGET=floci -> var.aws_endpoint = "http://localhost.floci.io:4566" (emulador local, credencial fictícia "test")
#   TARGET=aws   -> var.aws_endpoint = null (endpoints reais; credenciais do ambiente/OIDC)
# Valor null em um argumento de provider = "não definido" = padrão da AWS real. Nenhum código duplicado.

variable "aws_endpoint" {
  description = "Endpoint do emulador (floci). null = AWS real."
  type        = string
  default     = null
}

variable "aws_region" {
  description = "Região AWS."
  type        = string
  default     = "us-east-1"
}

variable "project" {
  description = "Nome do projeto (prefixo de recursos e tag Project)."
  type        = string
  default     = "argus-platform"
}

variable "environment" {
  description = "Ambiente lógico (lab, dev, prod)."
  type        = string
  default     = "lab"
}

variable "local_state_dir" {
  description = "AWS real: pasta do state LOCAL das stacks (nada salvo na AWS). null = remote state S3 (floci/curso)."
  type        = string
  default     = null
}

locals {
  is_emulator  = var.aws_endpoint != null
  name_prefix  = "${var.project}-${var.environment}"
  state_bucket = "${var.project}-${var.environment}-tfstate"

  # Extras do backend S3 quando o alvo é o emulador. Uso em terraform_remote_state:
  #   config = merge({ bucket = local.state_bucket, key = "01-networking.tfstate", region = var.aws_region },
  #                  [for c in [local.emulator_backend] : c if local.is_emulator]...)
  # (o "for ... if" evita o erro de tipos inconsistentes de um condicional objeto/{}).
  emulator_backend = {
    access_key                  = "test"
    secret_key                  = "test"
    skip_credentials_validation = true
    skip_requesting_account_id  = true
    skip_region_validation      = true
    use_path_style              = true
    endpoints                   = { s3 = coalesce(var.aws_endpoint, "http://localhost.floci.io:4566"), sts = coalesce(var.aws_endpoint, "http://localhost.floci.io:4566") }
  }
  common_tags = {
    Project     = var.project
    Environment = var.environment
    ManagedBy   = "terraform"
    Owner       = "yuri-fernando"
    CostCenter  = "portfolio"
    Target      = local.is_emulator ? "floci" : "aws"
  }
}

provider "aws" {
  region = var.aws_region

  # Emulador: credenciais fictícias aceitas pelo floci. AWS real: null -> cadeia padrão (env, perfil, OIDC).
  access_key                  = local.is_emulator ? "test" : null
  secret_key                  = local.is_emulator ? "test" : null
  skip_credentials_validation = local.is_emulator
  skip_metadata_api_check     = local.is_emulator
  s3_use_path_style           = local.is_emulator

  endpoints {
    acm            = var.aws_endpoint
    budgets        = var.aws_endpoint
    amp            = var.aws_endpoint
    cloudwatch     = var.aws_endpoint
    dynamodb       = var.aws_endpoint
    ec2            = var.aws_endpoint
    ecr            = var.aws_endpoint
    eks            = var.aws_endpoint
    elbv2          = var.aws_endpoint
    iam            = var.aws_endpoint
    kms            = var.aws_endpoint
    logs           = var.aws_endpoint
    route53        = var.aws_endpoint
    s3             = var.aws_endpoint
    s3control      = var.aws_endpoint
    secretsmanager = var.aws_endpoint
    sqs            = var.aws_endpoint
    ssm            = var.aws_endpoint
    sts            = var.aws_endpoint
    wafv2          = var.aws_endpoint
  }

  default_tags {
    tags = local.common_tags
  }
}
