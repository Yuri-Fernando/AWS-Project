# Perfil `real` — AWS de verdade (opcional, Free Plan, exige aprovação explícita)

**Estado:** preparado, **nunca executado**. Mesmo código Terraform do perfil `free`; muda só o alvo.

## Restrições da conta (Free Plan ativo até 05/05/2027, US$ 100 de créditos)
- Nunca: AWS Organizations, Control Tower, IAM Identity Center em modo organização, **Amazon Managed Grafana**
  (ativa Organizations → plano pago irreversível), Marketplace, Savings Plans/RI.
- Sessões curtas: `plan → apply → evidência → destroy` no mesmo dia; inventário por tag vazio ao final.
- Guardrails antes da 1ª sessão: AWS Budgets zero-spend + mensal **com créditos excluídos**, budget action com deny,
  credenciais com MFA, CI apenas via OIDC. Detalhes e custos estimados: `docs/plans/PLANO_v0.2_Curso_DevOps_x_Repos_AWS_Free.md`.

## Como ativar (quando autorizado)
1. `cp envs/real/backend.hcl.example envs/real/backend.hcl` e ajuste o bucket criado por `00-backend` (`--target real`).
   O `lab.py` usa `platform/terraform/_shared/backend-aws.hcl`: copie o mesmo conteúdo para lá (arquivo gitignored).
2. Credenciais do ambiente (perfil com MFA) — nunca chaves em arquivo versionado.
3. `python platform/lab.py plan --target real` (não cria nada) → revisar custo → `up --target real --yes-real-aws`.
4. Overlay de apps: `gitops/apps/*/overlays/aws` (2 réplicas, imagens no ECR real, sem credenciais — IRSA/Pod Identity).
5. MCP: `mcp/real.mcp.json` (somente leitura: `READ_OPERATIONS_ONLY=true`).

## O que só faz sentido aqui (não existe no emulador)
NAT e roteamento reais, Karpenter, scraper/logging do AMP, OIDC com token real do GitHub, nós EC2 reais.
