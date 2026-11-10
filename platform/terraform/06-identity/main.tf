# Stack 06 — Identidade, guardrails de custo e roles de workload.
# Junta o que o plano do GPT pedia ("separar papel de deploy de consulta, permissões mínimas, OIDC, budgets") com o
# que o curso usa (roles por componente). Roles já existentes em outras stacks: cluster/nós EKS (02), GitHub OIDC (03),
# flow logs (01). Esta stack adiciona:
#   - argus-platform-deployer   : humano/CI aplica a plataforma (exige MFA na AWS real)
#   - argus-platform-mcp-readonly: perfil do MCP no modo real (somente leitura)
#   - free-plan-guard (policy)   : NEGA o que converte o Free Plan em pago ou estoura crédito
#   - budgets                    : zero-spend + mensal, créditos EXCLUÍDOS
#   - roles de workload (EKS Pod Identity) por app, com acesso mínimo ao S3

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

variable "budget_email" {
  description = "E-mail que recebe os alertas de orçamento (não versionar; passe via -var ou TF_VAR_budget_email)."
  type        = string
  default     = "alertas@example.invalid"
}

variable "monthly_budget_usd" {
  description = "Limite mensal de gasto real (créditos excluídos)."
  type        = number
  default     = 5
}

variable "trusted_principal_arns" {
  description = "Quem pode assumir deployer/mcp-readonly. Vazio = a conta inteira (root), sujeito a MFA na AWS real."
  type        = list(string)
  default     = []
}

variable "enable_workload_identity" {
  description = "Cria roles/associações de Pod Identity (exige o cluster da stack 02). false = só guardrails e roles humanas (sessão R0)."
  type        = bool
  default     = true
}

data "aws_caller_identity" "current" {}

data "terraform_remote_state" "eks" {
  count   = var.enable_workload_identity ? 1 : 0
  backend = "s3"
  config = merge(
    { bucket = local.state_bucket, key = "02-eks.tfstate", region = var.aws_region },
    [for c in [local.emulator_backend] : c if local.is_emulator]...
  )
}

locals {
  account    = data.aws_caller_identity.current.account_id
  principals = length(var.trusted_principal_arns) > 0 ? var.trusted_principal_arns : ["arn:aws:iam::${local.account}:root"]
  # MFA só é exigido na AWS real (o emulador não tem fluxo de MFA)
  mfa_condition = local.is_emulator ? {} : { Bool = { "aws:MultiFactorAuthPresent" = "true" } }
  cluster       = try(data.terraform_remote_state.eks[0].outputs.cluster_name, null)
  ml_bucket     = "${var.project}-${var.environment}-ml-artifacts"
}

# ---------------------------------------------------------------------------
# Guardrail do Free Plan: negações explícitas valem acima de qualquer Allow
# ---------------------------------------------------------------------------
resource "aws_iam_policy" "free_plan_guard" {
  name        = "${local.name_prefix}-free-plan-guard"
  description = "Nega ações que convertem o Free Plan em pago (Organizations, Control Tower, Managed Grafana/Identity Center) ou compram capacidade."
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "NoPaidPlanTriggers"
        Effect = "Deny"
        Action = [
          "organizations:*", "controltower:*", "account:CloseAccount",
          "grafana:CreateWorkspace", "sso:CreateInstance", "sso:CreateInstanceAccessControlAttributeConfiguration",
          "aws-marketplace:Subscribe", "savingsplans:CreateSavingsPlan",
          "ec2:PurchaseReservedInstancesOffering", "rds:PurchaseReservedDBInstancesOffering",
          "sagemaker:CreateEndpoint", "sagemaker:CreateEndpointConfig"
        ]
        Resource = "*"
      },
      {
        # O AWS MCP Server marca toda chamada do agente com aws:ViaAWSMCPService; aqui o agente não cria nada caro,
        # mesmo que alguém o configure sem --read-only. Criação desses recursos só via Terraform (deployer + MFA).
        Sid    = "NoCostlyCreatesViaAgent"
        Effect = "Deny"
        Action = [
          "ec2:RunInstances", "ec2:CreateNatGateway", "ec2:AllocateAddress", "eks:CreateCluster", "eks:CreateNodegroup",
          "elasticloadbalancing:CreateLoadBalancer", "rds:CreateDBInstance", "rds:CreateDBCluster",
          "elasticache:CreateCacheCluster", "es:CreateDomain", "redshift:CreateCluster", "kafka:CreateCluster"
        ]
        Resource  = "*"
        Condition = { Bool = { "aws:ViaAWSMCPService" = "true" } }
      }
    ]
  })
}

# ---------------------------------------------------------------------------
# Humanos / CI
# ---------------------------------------------------------------------------
resource "aws_iam_role" "deployer" {
  name                 = "${local.name_prefix}-deployer"
  max_session_duration = 14400 # 4 h: uma sessão de laboratório
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [merge({
      Effect    = "Allow"
      Principal = { AWS = local.principals }
      Action    = "sts:AssumeRole"
    }, length(local.mfa_condition) > 0 ? { Condition = local.mfa_condition } : {})]
  })
}

resource "aws_iam_role_policy_attachment" "deployer" {
  for_each = {
    power = "arn:aws:iam::aws:policy/PowerUserAccess"
    guard = aws_iam_policy.free_plan_guard.arn
  }
  role       = aws_iam_role.deployer.name
  policy_arn = each.value
}

resource "aws_iam_role_policy" "deployer_iam_scoped" {
  name = "iam-scoped-to-project"
  role = aws_iam_role.deployer.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid    = "ManageOnlyProjectRolesAndPolicies"
      Effect = "Allow"
      Action = ["iam:CreateRole", "iam:DeleteRole", "iam:GetRole", "iam:TagRole", "iam:UpdateAssumeRolePolicy",
        "iam:AttachRolePolicy", "iam:DetachRolePolicy", "iam:PutRolePolicy", "iam:DeleteRolePolicy", "iam:PassRole",
        "iam:CreatePolicy", "iam:DeletePolicy", "iam:CreatePolicyVersion", "iam:DeletePolicyVersion",
      "iam:CreateOpenIDConnectProvider", "iam:DeleteOpenIDConnectProvider", "iam:TagOpenIDConnectProvider"]
      Resource = [
        "arn:aws:iam::${local.account}:role/${var.project}-*",
        "arn:aws:iam::${local.account}:policy/${var.project}-*",
        "arn:aws:iam::${local.account}:oidc-provider/*"
      ]
    }]
  })
}

resource "aws_iam_role" "mcp_readonly" {
  name                 = "${local.name_prefix}-mcp-readonly"
  max_session_duration = 3600
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [merge({
      Effect    = "Allow"
      Principal = { AWS = local.principals }
      Action    = "sts:AssumeRole"
    }, length(local.mfa_condition) > 0 ? { Condition = local.mfa_condition } : {})]
  })
}

resource "aws_iam_role_policy_attachment" "mcp_readonly" {
  for_each = {
    read  = "arn:aws:iam::aws:policy/ReadOnlyAccess"
    guard = aws_iam_policy.free_plan_guard.arn
  }
  role       = aws_iam_role.mcp_readonly.name
  policy_arn = each.value
}

# ---------------------------------------------------------------------------
# Orçamentos (créditos EXCLUÍDOS para o gasto real aparecer)
# ---------------------------------------------------------------------------
resource "aws_budgets_budget" "zero_spend" {
  name         = "${local.name_prefix}-zero-spend"
  budget_type  = "COST"
  limit_amount = "0.01"
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  cost_types {
    include_credit = false
    include_refund = false
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.budget_email]
  }
}

resource "aws_budgets_budget" "monthly" {
  name         = "${local.name_prefix}-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  cost_types {
    include_credit = false
  }

  dynamic "notification" {
    for_each = [50, 80, 100]
    content {
      comparison_operator        = "GREATER_THAN"
      threshold                  = notification.value
      threshold_type             = "PERCENTAGE"
      notification_type          = notification.value == 100 ? "ACTUAL" : "FORECASTED"
      subscriber_email_addresses = [var.budget_email]
    }
  }
}

# ---------------------------------------------------------------------------
# Workloads — EKS Pod Identity (o floci injeta credenciais temporárias no pod; na AWS real idem)
# ---------------------------------------------------------------------------
locals {
  workloads = !var.enable_workload_identity ? {} : {
    riskcredit-train = { actions = ["s3:PutObject", "s3:GetObject", "s3:ListBucket", "s3:CreateBucket", "s3:HeadBucket"], bucket = local.ml_bucket }
    creditscore-app  = { actions = ["s3:GetObject", "s3:ListBucket"], bucket = local.ml_bucket }
    argus-api        = { actions = ["s3:GetObject", "s3:PutObject", "s3:ListBucket"], bucket = "${var.project}-${var.environment}-lakehouse" }
  }
}

resource "aws_iam_role" "workload" {
  for_each = local.workloads
  name     = "${local.name_prefix}-wl-${each.key}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "pods.eks.amazonaws.com" }
      Action    = ["sts:AssumeRole", "sts:TagSession"]
    }]
  })
}

resource "aws_iam_role_policy" "workload" {
  for_each = local.workloads
  name     = "s3-minimo"
  role     = aws_iam_role.workload[each.key].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = each.value.actions
      Resource = ["arn:aws:s3:::${each.value.bucket}", "arn:aws:s3:::${each.value.bucket}/*"]
    }]
  })
}

resource "aws_eks_pod_identity_association" "workload" {
  for_each        = local.workloads
  cluster_name    = local.cluster
  namespace       = "ecosystem"
  service_account = each.key
  role_arn        = aws_iam_role.workload[each.key].arn
}

output "deployer_role_arn" {
  value = aws_iam_role.deployer.arn
}

output "mcp_readonly_role_arn" {
  description = "Use no perfil AWS 'argus-lab-readonly' (role_arn + source_profile + mfa_serial) do mcp/real.mcp.json."
  value       = aws_iam_role.mcp_readonly.arn
}

output "free_plan_guard_arn" {
  value = aws_iam_policy.free_plan_guard.arn
}

output "workload_roles" {
  value = { for k, r in aws_iam_role.workload : k => r.arn }
}
