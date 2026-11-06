# Matriz de compatibilidade — floci (emulador AWS local)

**Ambiente verificado em 06/11/2026:** floci `2.4.0` · Terraform `1.15.8` · provider `hashicorp/aws ~> 6.0` · Docker Desktop (WSL2, 4 CPU / 12,5 GB) · Windows 11.
Ferramenta: `platform/floci/spike.py` (aplica stacks **sem editá-las**, via `*_override.tf`) e `platform/lab.py` (stacks próprias).
Legenda: ✅ funcionou · ⚠️ funcionou com ajuste · ❌ não suportado pelo floci · 🔧 pré-requisito do ambiente (falharia igual numa conta AWS nova).

## 1. IaC do curso (materiais do instrutor, sem modificação)
### dvn-workshop-maio (Workshop Dia 1–2)
| Stack | Resultado | Recursos | Observação |
|---|---|---|---|
| 00-remote-backend-stack-ai | ✅ | S3 + versioning + SSE + lifecycle + public access block | falha inicial foi bucket pré-criado pelo próprio spike |
| 01-networking-stack-ai | ✅ | 24 (VPC, 6 subnets, IGW, **3 NAT + 3 EIP**, route tables, flow logs + IAM) | |
| 02-eks-stack-ai | ✅ | 14 (EKS → **k3s real**, node group, add-ons, ECR, IAM, SG) | ~3 min |
| 03-ci-cd-stack-ai | ✅ | 4 (OIDC GitHub + role + policy) | `destroy` bloqueado por `prevent_destroy = true` do próprio curso |

### eks-express-iac (Observabilidade / eks-express)
| Stack | Resultado | Detalhe |
|---|---|---|
| 00-backend | ✅ | S3 + DynamoDB lock |
| 01-networking | ✅ | 23 recursos |
| 02-eks-cluster | ⚠️ 22/27 | 🔧 hosted zone `eks.devopsnanuvem.com` (domínio do instrutor) criada no floci · 🔧 access entries apontam para usuário IAM / role SSO **da conta do instrutor** · ❌ add-on `metrics-server` (floci aceita só `vpc-cni`, `coredns`, `kube-proxy`, `eks-pod-identity-agent`) · ❌ `AssociateAccessPolicy` não implementado |
| 03-karpenter-auto-scaling | ❌ | `ecr-public:GetAuthorizationToken` não implementado (chart do Karpenter vem do ECR Public) — e Karpenter precisa de frota EC2 real |
| 04-security | ✅ | WAFv2 Web ACL |
| 05-monitoring | ❌ parcial | ❌ Amazon Managed Grafana (`grafana:CreateWorkspace`) · ❌ add-on `prometheus-node-exporter` · ❌ logging do AMP (ver §3) |

## 2. Stacks próprias (`platform/terraform`, alvo duplo floci/AWS)
| Stack | Resultado | Recursos |
|---|---|---|
| 00-backend | ✅ | 5 (S3 do state, lock nativo `use_lockfile`) |
| 01-networking | ✅ | 23 (reusa `terraform/modules/networking`; flow logs) |
| 02-eks | ✅ | 27 (módulo `terraform/modules/eks`: cluster, node group SPOT, 4 add-ons, IRSA, 7 ECR + lifecycle) |
| 03-ci-cd | ✅ | 4 (reusa `terraform/modules/iam`: OIDC GitHub + role + ECR push/EKS describe) |
| 04-security | ✅ | 1 (WAFv2, regras gerenciadas em COUNT) |
| 05-monitoring | ⚠️ | AMP desligado automaticamente no floci (§3); log group criado |

## 3. Limitações e contornos descobertos
| Problema | Causa | Contorno aplicado |
|---|---|---|
| `aws_prometheus_workspace` falha | provider 6.x chama `DescribeLoggingConfiguration` após criar; floci 2.4.0 não implementa `/workspaces/{id}/logging` (404) | `enable_amp = null` → automático (off no floci, on na AWS). Prometheus real roda no cluster. Candidato a issue/PR no floci |
| `kubectl` → "server has asked for credentials" | webhook do EKS emulado só aceita token assinado por access key **existente no IAM do floci** (a genérica `test` é rejeitada) | `lab.py kubeconfig` cria usuário IAM `lab-kube-admin` + access key e injeta no `exec` do kubeconfig |
| `lookup 000000000000.localhost: no such host` | S3 Control (tags de bucket via `default_tags`) prefixa o ID da conta no host; Windows não resolve `*.localhost` | endpoint `http://localhost.floci.io:4566` (DNS público curinga → 127.0.0.1) + endpoint `s3control` no provider |
| `count` do provider OIDC (IRSA) inválido | issuer só existe após criar o cluster | `count = var.enable_irsa ? 1 : 0` |
| Helm `-f` quebra caminho | `-f` aceita lista separada por vírgula e o caminho contém "Projetos, Robos" | valores via stdin (`-f - < arquivo`) |
| Nó EKS com ~3,5 GB alocáveis | floci reserva memória para emular a capacidade de uma t3.medium | requests baixos (ArgoCD, Prometheus, apps) |

## 4. O que fica para a AWS real (opcional, `TARGET=aws`)
Karpenter, NAT/roteamento reais, scraper e logging do AMP, OIDC com token real do GitHub, Managed Grafana (**não usar no Free Plan**: ativa AWS Organizations → plano pago).
