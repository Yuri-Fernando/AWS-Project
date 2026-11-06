# Stack 04 — WAFv2 regional para o ALB do ingress (eks-express-iac/04-security, reescrito).
# Regras gerenciadas em COUNT por padrão: observar antes de bloquear (o curso deixava COUNT sem explicar).
# Na AWS real o Web ACL custa por mês + por regra; no floci é só API (sem filtragem de tráfego).

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

variable "managed_rule_groups" {
  description = "Grupos gerenciados AWS (nome => prioridade)."
  type        = map(number)
  default = {
    AWSManagedRulesCommonRuleSet          = 10
    AWSManagedRulesKnownBadInputsRuleSet  = 20
    AWSManagedRulesAmazonIpReputationList = 30
  }
}

variable "enforce" {
  description = "false = COUNT (só registra); true = aplica a ação das regras (bloqueia)."
  type        = bool
  default     = false
}

variable "rate_limit_per_5min" {
  type    = number
  default = 2000
}

resource "aws_wafv2_web_acl" "alb" {
  name  = "${local.name_prefix}-alb-acl"
  scope = "REGIONAL"

  default_action {
    allow {}
  }

  dynamic "rule" {
    for_each = var.managed_rule_groups
    content {
      name     = rule.key
      priority = rule.value

      override_action {
        dynamic "count" {
          for_each = var.enforce ? [] : [1]
          content {}
        }
        dynamic "none" {
          for_each = var.enforce ? [1] : []
          content {}
        }
      }

      statement {
        managed_rule_group_statement {
          vendor_name = "AWS"
          name        = rule.key
        }
      }

      visibility_config {
        cloudwatch_metrics_enabled = true
        metric_name                = rule.key
        sampled_requests_enabled   = true
      }
    }
  }

  rule {
    name     = "rate-limit-per-ip"
    priority = 100

    action {
      dynamic "count" {
        for_each = var.enforce ? [] : [1]
        content {}
      }
      dynamic "block" {
        for_each = var.enforce ? [1] : []
        content {}
      }
    }

    statement {
      rate_based_statement {
        limit              = var.rate_limit_per_5min
        aggregate_key_type = "IP"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "rate-limit-per-ip"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "${local.name_prefix}-alb-acl"
    sampled_requests_enabled   = true
  }
}

output "web_acl_arn" {
  description = "Associe ao ALB via anotação alb.ingress.kubernetes.io/wafv2-acl-arn."
  value       = aws_wafv2_web_acl.alb.arn
}
