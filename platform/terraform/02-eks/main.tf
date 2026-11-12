# Stack 02 — EKS + ECR (curso: Dia 2 01:00–01:30 e 02:45–03:15).
# Usa terraform/modules/eks (promovido do Argus). No floci o cluster é um k3s real com API server.

terraform {
  required_version = ">= 1.10"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.1"
    }
  }
  backend "s3" {}
}

variable "enable_alb_tls" {
  description = "Cria um certificado AUTOASSINADO *.argus.lab e importa no ACM para o HTTPS do ALB (sem domínio próprio). O navegador avisa que o certificado não é confiável; a criptografia é real."
  type        = bool
  default     = false
}

variable "alb_domain" {
  description = "Domínio interno do laboratório usado nos hosts do Ingress (<app>.<domínio>)."
  type        = string
  default     = "argus.lab"
}

# Chave e certificado ficam SÓ no state local (platform/.state, gitignored); destruídos junto com a stack.
resource "tls_private_key" "alb" {
  count     = var.enable_alb_tls ? 1 : 0
  algorithm = "RSA"
  rsa_bits  = 2048
}

resource "tls_self_signed_cert" "alb" {
  count                 = var.enable_alb_tls ? 1 : 0
  private_key_pem       = tls_private_key.alb[0].private_key_pem
  validity_period_hours = 168
  allowed_uses          = ["key_encipherment", "digital_signature", "server_auth"]
  dns_names             = ["*.${var.alb_domain}", var.alb_domain]
  subject {
    common_name  = "*.${var.alb_domain}"
    organization = "Argus Platform Lab"
  }
}

# O AWS Load Balancer Controller descobre este certificado pelos hosts do `tls` do Ingress (sem ARN no git).
resource "aws_acm_certificate" "alb" {
  count            = var.enable_alb_tls ? 1 : 0
  private_key      = tls_private_key.alb[0].private_key_pem
  certificate_body = tls_self_signed_cert.alb[0].cert_pem
}

variable "kubernetes_version" {
  type    = string
  default = "1.33"
}

variable "node_group" {
  description = "Ver terraform/modules/eks. SPOT por padrão (só importa na AWS real)."
  type = object({
    name           = string
    instance_types = list(string)
    capacity_type  = string
    disk_size      = number
    desired_size   = number
    min_size       = number
    max_size       = number
  })
  default = {
    name           = "default"
    instance_types = ["t3.medium"]
    capacity_type  = "SPOT"
    disk_size      = 20
    desired_size   = 2
    min_size       = 1
    max_size       = 3
  }
}

variable "admin_principal_arns" {
  description = "Principais IAM com AmazonEKSClusterAdminPolicy (além do criador do cluster)."
  type        = list(string)
  default     = []
}

variable "ecr_repositories" {
  description = "Repositórios ECR dos workloads do ecossistema."
  type        = list(string)
  default     = ["argus-api", "retentiq-api", "themis-api", "omnimind-api", "churn-api", "riskcredit-train", "creditscore-app"]
}

data "terraform_remote_state" "network" {
  count   = var.local_state_dir == null ? 1 : 0
  backend = "s3"
  config = merge(
    { bucket = local.state_bucket, key = "01-networking.tfstate", region = var.aws_region },
    [for c in [local.emulator_backend] : c if local.is_emulator]...
  )
}

# AWS real: state local (regra do dono: nada salvo na AWS)
data "terraform_remote_state" "network_local" {
  count   = var.local_state_dir == null ? 0 : 1
  backend = "local"
  config  = { path = "${var.local_state_dir}/01-networking-aws.tfstate" }
}

locals {
  network = var.local_state_dir == null ? data.terraform_remote_state.network[0].outputs : data.terraform_remote_state.network_local[0].outputs
}

module "eks" {
  source             = "../../../repos/enterprise-automation/terraform/modules/eks"
  name               = "${local.name_prefix}-eks"
  kubernetes_version = var.kubernetes_version
  subnet_ids         = local.network.private_subnet_ids
  # sem NAT, nós precisam de subnet pública para baixar imagens (só relevante na AWS real)
  node_subnet_ids = length(local.network.nat_gateway_ids) > 0 ? null : local.network.public_subnet_ids
  node_group      = var.node_group
  access_entries = {
    for i, arn in var.admin_principal_arns : "admin-${i}" => { principal_arn = arn, policy = "AmazonEKSClusterAdminPolicy" }
  }
}

resource "aws_ecr_repository" "this" {
  for_each             = toset(var.ecr_repositories)
  name                 = "${var.project}/${each.value}"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "this" {
  for_each   = aws_ecr_repository.this
  repository = each.value.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Mantém só as 10 imagens mais recentes (custo de storage na AWS real)."
      selection    = { tagStatus = "any", countType = "imageCountMoreThan", countNumber = 10 }
      action       = { type = "expire" }
    }]
  })
}

output "cluster_name" {
  value = module.eks.cluster_name
}

output "cluster_endpoint" {
  value = module.eks.cluster_endpoint
}

output "oidc_provider_arn" {
  value = module.eks.oidc_provider_arn
}

output "ecr_repository_urls" {
  value = { for k, r in aws_ecr_repository.this : k => r.repository_url }
}

output "ecr_repository_arns" {
  value = [for r in aws_ecr_repository.this : r.arn]
}

output "vpc_id" {
  description = "Usado pelo AWS Load Balancer Controller (--set vpcId)."
  value       = local.network.vpc_id
}

output "alb_certificate_domain" {
  value = var.enable_alb_tls ? "*.${var.alb_domain}" : null
}
