# Roles e permissões do projeto (curso DevOps na Nuvem + plano do GPT)

Todas criadas por Terraform, aplicadas e verificadas no perfil `free` (floci) em 07/11/2026. Prefixo: `argus-platform-lab-`.

| Role / política | Quem usa | Permissões | Origem | Stack |
|---|---|---|---|---|
| `…-eks-cluster` | control plane EKS | `AmazonEKSClusterPolicy` | curso (eks-cluster) | 02-eks (`repos/enterprise-automation/terraform/modules/eks`) |
| `…-eks-node` | nós do node group | `AmazonEKSWorkerNodePolicy`, `AmazonEKS_CNI_Policy`, `AmazonEC2ContainerRegistryReadOnly` | curso | 02-eks |
| OIDC provider do cluster (IRSA) | service accounts | federação OIDC do cluster | curso (eks-express) | 02-eks |
| `…-vpc-flow-logs` | VPC Flow Logs | escrever no log group do flow log | curso (dvn-workshop 01) | 01-networking |
| `…-github-actions-role` | pipeline GitHub Actions (OIDC, repo/branch restritos) | state no S3, ECR push nos 7 repositórios, `eks:DescribeCluster` | curso (Dia 2, 04:00–05:17) | 03-ci-cd (`modules/iam`) |
| `…-deployer` | humano/CI que aplica a plataforma | `PowerUserAccess` + IAM só em `argus-platform-*` + `free-plan-guard`; **MFA obrigatório na AWS real**; sessão de 4 h | plano GPT ("papel de deploy separado") | 06-identity |
| `…-mcp-readonly` | servidores MCP no perfil `real` | `ReadOnlyAccess` + `free-plan-guard`; MFA; sessão de 1 h | plano GPT ("MCP só leitura primeiro") | 06-identity |
| `…-free-plan-guard` (policy) | anexada a deployer e mcp-readonly | **Deny** em Organizations, Control Tower, Managed Grafana, criação de instância do Identity Center, Marketplace, Savings Plans/RI, endpoints SageMaker | lição do curso (aulas 05/06) + regra R$ 0 | 06-identity |
| `…-wl-riskcredit-train` | Job de treino (EKS Pod Identity) | S3 leitura/escrita só no bucket `…-ml-artifacts` | plano GPT (least privilege por workload) | 06-identity |
| `…-wl-creditscore-app` | app Credit Score | S3 só leitura em `…-ml-artifacts` | idem | 06-identity |
| `…-wl-argus-api` | Argus | S3 leitura/escrita em `…-lakehouse` | idem | 06-identity |
| Budgets `…-zero-spend` e `…-monthly` | alerta por e-mail | gasto real com **créditos excluídos**; mensal 50/80/100% | plano v0.2 (guardrails) | 06-identity |

Fora de escopo de propósito: role com `AdministratorAccess` (os READMEs do curso sugerem; não usamos), roles do
Karpenter/ALB Controller/external-dns (dependem de AWS real e domínio).

**Pendência:** os Deployments ainda usam credencial estática do emulador via ConfigMap; para as roles de workload
valerem, cada app precisa do ServiceAccount homônimo e de remover `AWS_ACCESS_KEY_ID/SECRET` do ConfigMap
(as associações de Pod Identity já existem no floci).
