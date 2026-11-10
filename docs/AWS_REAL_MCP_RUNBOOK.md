# Runbook — terminar o projeto na AWS real (conta Free Plan) via MCP, sem cobrança

## 1. O que acontece quando os créditos acabam (fontes oficiais, consultadas em 07/11/2026)
| Pergunta | Resposta | Fonte |
|---|---|---|
| Quando o Free Plan termina? | 6 meses após abrir a conta **ou** quando os créditos acabam, o que vier primeiro (sua conta: 05/05/2027) | [Free Tier FAQ](https://aws.amazon.com/free/free-tier-faqs/), [Choosing a plan](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html) |
| Vou ser cobrado automaticamente? | **Não.** A conta é **suspensa**; para continuar é preciso fazer upgrade manual para o plano pago | idem |
| E os meus dados? | Perde o acesso na suspensão; a AWS guarda 90 dias e depois **apaga a conta e todo o conteúdo** | Free Tier FAQ |
| O que converte em pago sem eu clicar em upgrade? | Entrar no AWS Organizations, landing zone do Control Tower, APN, contratos enterprise, conta HIPAA/SEC — e o Managed Grafana com Identity Center ativa Organizations | Choosing a plan; docs do Managed Grafana |
| Se um dia fizer upgrade? | Créditos restantes passam para as faturas; "Always Free" continua grátis (ex.: Lambda 1 mi req/mês, DynamoDB 25 GB, SQS/SNS 1 mi, CloudWatch 10 métricas/alarmes) — **acima disso, cobra** | FAQ + [Serverless free tier](https://aws.amazon.com/free/serverless) |

**Conclusão:** ficando no Free Plan e sem acionar os gatilhos acima, o pior caso é a conta ser suspensa — sem fatura.
Por isso: (1) a policy `free-plan-guard` nega os gatilhos; (2) tudo que importa é copiado para fora com
`tools/offload.py --target real` antes do fim do plano e ao fim de cada sessão; (3) o código vive no GitHub e o lab
`free` continua funcionando sem conta.

## 2. Pré-requisitos (uma vez, ~30 min, custo zero)
1. Conferir no console: Billing → Free Tier (saldo, data), e se **EKS** e **Amazon Managed Service for Prometheus**
   abrem sem aviso de plano (não há lista oficial pública).
2. Usuário IAM pessoal com MFA (não usar root). Perfis em `~/.aws/config`:
   `argus-lab` (usuário com MFA) → `argus-lab-deployer` (role `…-deployer`) e `argus-lab-readonly` (role `…-mcp-readonly`).
3. Atividades de crédito (+ até US$ 100): Budgets, EC2 t3.micro (terminar), Lambda web app (apagar), 1 prompt no Bedrock
   playground, RDS db.t4g.micro sem snapshot final (apagar).
4. Ativar MCP somente leitura: `python tools/mcp_profile.py real` (aprovação `@devops`).

## 3. Sessões (cada uma: plan → apply → evidência → offload → destroy no mesmo dia)
| # | Sessão | Comando | Custo estimado* |
|---|---|---|---|
| R0 | Identidade + budgets (bootstrap com credencial do usuário) | `TF_VAR_enable_workload_identity=false lab.py up --target real --stacks 00-backend,06-identity --yes-real-aws` (guardrails antes de qualquer recurso pago; roles de workload entram depois da R2) | ~US$ 0 |
| R1 | Rede (1 NAT ou nenhum) | `lab.py up --target real --stacks 01-networking --yes-real-aws` → evidências → `down` | < US$ 0,10/h |
| R2 | EKS + ECR + OIDC + deploy dos apps | `--stacks 02-eks,03-ci-cd` → `images/build.py` (ECR real) → `lab.py deploy --target real` → `e2e.py --target real` | ~US$ 0,25–0,30/h |
| R3 | Observabilidade | `05-monitoring` (AMP liga sozinho na AWS) + Prometheus remote_write; Grafana OSS no cluster | centavos |
| R4 | Serverless Credit Score | Terraform do repo `meu-projeto-aws` no perfil real | ~US$ 0 (free tier Lambda/DynamoDB) |

*Estimativas us-east-1 sob demanda; conferir no Pricing Calculator antes do apply. Ao fim de cada sessão:
`python tools/offload.py --target real` e `python platform/lab.py down --target real --yes-real-aws`, depois conferir
inventário por tag vazio.

## 4. Papel do MCP em cada sessão
- **Antes:** `aws-mcp-readonly` (AWS MCP Server gerenciado: documentação, skills e chamadas de leitura) + `terraform`
  (registry) para revisar recursos, conferir saldo, quotas e recursos órfãos.
- **Durante:** `eks-readonly` para listar nodes/pods e diagnosticar (como no Dia 2 do curso).
- **Depois:** `aws-mcp-readonly` lista tudo com a tag `Project=argus-platform` para provar que o teardown zerou.
- Escrita via MCP na AWS real: **não** nesta fase (só Terraform com o deployer + MFA). Dupla barreira: o proxy roda com
  `--read-only` e a policy `free-plan-guard` nega criações caras quando `aws:ViaAWSMCPService = true`.
