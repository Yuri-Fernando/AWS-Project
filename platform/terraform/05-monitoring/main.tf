# Stack 05 — Amazon Managed Prometheus (aulas de Observabilidade 01–04, reescritas).
# DESVIO CONSCIENTE DO CURSO: sem Amazon Managed Grafana. Na conta Free Plan, AMG + IAM Identity Center ativa
# AWS Organizations, o que converte a conta em paga (irreversível). Grafana OSS roda no cluster (platform/k8s).
# Scraper gerenciado (aws_prometheus_scraper) é opcional e não existe no floci; no lab o Prometheus do
# kube-prometheus-stack faz remote_write para cá quando TARGET=aws.

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

variable "log_retention_days" {
  type    = number
  default = 7
}

variable "enable_amp" {
  description = <<-EOT
    Cria o workspace AMP. null = automático: liga na AWS real e desliga no floci.
    Motivo (verificado em 06/11/2026): o provider hashicorp/aws 6.x chama DescribeLoggingConfiguration após criar o
    workspace e o floci 2.4.0 não implementa /workspaces/{id}/logging (404 UnknownOperation). No lab, o Prometheus
    real roda no cluster (platform/k8s/monitoring-values.yaml).
  EOT
  type        = bool
  default     = null
}

locals {
  amp = coalesce(var.enable_amp, !local.is_emulator)
}

resource "aws_cloudwatch_log_group" "amp" {
  name              = "/aws/prometheus/${local.name_prefix}"
  retention_in_days = var.log_retention_days
}

resource "aws_prometheus_workspace" "this" {
  count = local.amp ? 1 : 0
  alias = "${local.name_prefix}-amp"

  logging_configuration {
    log_group_arn = "${aws_cloudwatch_log_group.amp.arn}:*"
  }
}

resource "aws_prometheus_rule_group_namespace" "platform" {
  count        = local.amp ? 1 : 0
  name         = "platform-alerts"
  workspace_id = aws_prometheus_workspace.this[0].id
  data         = <<-YAML
    groups:
      - name: node
        rules:
          - alert: NodeHighCPU
            expr: 100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 85
            for: 10m
            labels: { severity: warning }
            annotations: { summary: "CPU do nó acima de 85% por 10 min" }
          - alert: NodeLowMemory
            expr: node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes < 0.10
            for: 10m
            labels: { severity: warning }
            annotations: { summary: "Menos de 10% de memória livre" }
  YAML
}

output "amp_workspace_id" {
  value = try(aws_prometheus_workspace.this[0].id, null)
}

output "amp_remote_write_url" {
  value = try("${aws_prometheus_workspace.this[0].prometheus_endpoint}api/v1/remote_write", null)
}
