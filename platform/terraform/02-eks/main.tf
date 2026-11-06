# Stack 02 — EKS + ECR (curso: Dia 2 01:00–01:30 e 02:45–03:15).
# Usa terraform/modules/eks (promovido do Argus). No floci o cluster é um k3s real com API server.

terraform {
  required_version = ">= 1.10"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
  backend "s3" {}
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
  backend = "s3"
  config = merge(
    { bucket = local.state_bucket, key = "01-networking.tfstate", region = var.aws_region },
    [for c in [local.emulator_backend] : c if local.is_emulator]...
  )
}

module "eks" {
  source             = "../../../repos/enterprise-automation/terraform/modules/eks"
  name               = "${local.name_prefix}-eks"
  kubernetes_version = var.kubernetes_version
  subnet_ids         = data.terraform_remote_state.network.outputs.private_subnet_ids
  # sem NAT, nós precisam de subnet pública para baixar imagens (só relevante na AWS real)
  node_subnet_ids = length(data.terraform_remote_state.network.outputs.nat_gateway_ids) > 0 ? null : data.terraform_remote_state.network.outputs.public_subnet_ids
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
