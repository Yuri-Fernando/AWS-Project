# Stack 03 — GitHub Actions -> AWS via OIDC (curso: Dia 2 04:00–05:17).
# Reaproveita terraform/modules/iam (provider OIDC + role com trust restrito a repo/branch + permissões de state)
# e adiciona o que a pipeline do workshop precisa: push no ECR e DescribeCluster no EKS.
# No floci: os recursos IAM existem, mas o token real do GitHub não é validado — no CI usamos o floci
# como service container com credencial de teste (ver .github/workflows/platform-floci.yml).

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

variable "github_org" {
  type    = string
  default = "Yuri-Fernando"
}

variable "github_repo" {
  type    = string
  default = "Enterprise-Automation"
}

variable "github_allowed_branches" {
  type    = list(string)
  default = ["ref:refs/heads/main"]
}

data "terraform_remote_state" "eks" {
  backend = "s3"
  config = merge(
    { bucket = local.state_bucket, key = "02-eks.tfstate", region = var.aws_region },
    [for c in [local.emulator_backend] : c if local.is_emulator]...
  )
}

module "iam" {
  source                      = "../../../repos/enterprise-automation/terraform/modules/iam"
  name_prefix                 = local.name_prefix
  create_ec2_role             = false
  create_github_oidc_provider = true
  github_org                  = var.github_org
  github_repo                 = var.github_repo
  github_allowed_branches     = var.github_allowed_branches
  state_bucket_arn            = "arn:aws:s3:::${local.state_bucket}"
}

resource "aws_iam_role_policy" "ecr_push_eks_describe" {
  name = "${local.name_prefix}-ecr-push-eks-describe"
  role = split("/", module.iam.github_actions_role_arn)[1]
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "EcrLogin"
        Effect   = "Allow"
        Action   = ["ecr:GetAuthorizationToken"]
        Resource = "*"
      },
      {
        Sid    = "EcrPush"
        Effect = "Allow"
        Action = ["ecr:BatchCheckLayerAvailability", "ecr:InitiateLayerUpload", "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload", "ecr:PutImage", "ecr:BatchGetImage", "ecr:DescribeImages"]
        Resource = data.terraform_remote_state.eks.outputs.ecr_repository_arns
      },
      {
        Sid      = "EksDescribe"
        Effect   = "Allow"
        Action   = ["eks:DescribeCluster"]
        Resource = "*"
      }
    ]
  })
}

output "github_actions_role_arn" {
  description = "Use como AWS_ROLE_ARN (variável do repositório) no aws-actions/configure-aws-credentials."
  value       = module.iam.github_actions_role_arn
}

output "github_oidc_provider_arn" {
  value = module.iam.github_oidc_provider_arn
}
