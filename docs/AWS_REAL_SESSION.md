# Sessões na AWS real (conta Free Plan, us-east-1)

| Sessão | Data | O que provou | e2e |
|---|---|---|---|
| 1 | 11/11/2026 | plataforma completa na nuvem: rede, EKS, apps, observabilidade, serverless | 13/13 |
| 2 | 12/11/2026 | **GitOps de verdade** (ArgoCD puxando do GitHub) e **ALB público com HTTPS** (TLS 1.3) | **18/18** |

Para saber o que existiu na nuvem sem acesso à conta: [`aws-real/INVENTARIO.md`](aws-real/INVENTARIO.md) (cada recurso,
lido dos states de antes do destroy) e [`aws-real/sessao-2026-11-12/`](aws-real/sessao-2026-11-12/) (retrato
operacional ao vivo: EKS, pods, Ingress, ALB com listeners e alvos, certificado, ArgoCD, Helm, serverless, conta).

---

# Sessão 1 — 11/11/2026

Registro completo da primeira execução do perfil `real`: o mesmo código Terraform/GitOps que roda no emulador (floci)
aplicado numa conta AWS de verdade, testado de ponta a ponta, documentado com evidências e desmontado no mesmo dia.
Todos os números abaixo vêm de saídas reais (`terraform`, `kubectl`, AWS CLI, Cost Explorer, `platform/e2e.py`).

## 1. Regras da sessão

| Regra | Como foi garantida |
|---|---|
| Custo dentro dos créditos, nunca negativo | Budgets US$ 0,01 (zero-spend) e US$ 5/mês com créditos **excluídos**; sessão curta; `destroy` no mesmo dia |
| Conta nunca sai do Free Plan | `free-plan-guard` nega Organizations, Control Tower, `account:CloseAccount` e criações caras via agente; nada de Managed Grafana/Identity Center |
| **Nenhum dado persistido na AWS** | state do Terraform **local** (sem bucket S3); dados copiados para fora (`tools/offload.py`) antes do `destroy` |
| Nada sensível no git | ID da conta só em memória no deploy; evidências com conta, IDs IAM e IPs públicos mascarados; tfvars/state gitignored |

## 2. Linha do tempo

| Etapa | O que aconteceu | Resultado |
|---|---|---|
| Preparação | usuário IAM com MFA, perfil `argus-lab` no AWS CLI, checagem do plano (FREE, US$ 100, expira 05/05/2027) | conta limpa, nenhum recurso prévio |
| **R0** identidade e custo | `lab.py up --target real --stacks 06-identity` | 10 recursos: `free-plan-guard`, roles `deployer` e `mcp-readonly` (MFA), 2 budgets |
| **R1** rede | `--stacks 01-networking` | 23 recursos: VPC 10.20.0.0/16 em 3 AZs, 6 subnets, rotas, **sem NAT**, flow logs (7 dias) |
| **R4** serverless | Terraform do repo [Credit-Score-Predictor](https://github.com/Yuri-Fernando/Credit-Score-Predictor---AWS-Streamlit) | 30 recursos: API Gateway HTTP + JWT/Cognito, Lambda v3, DynamoDB, KMS, S3, alarmes; Lambda HTTP 200 |
| **R2** EKS e apps | `--stacks 02-eks` → push de 7 imagens no ECR → Pod Identity (`06-identity`, +9) → `lab.py deploy --target real` | EKS 1.33, 2 nós `c7i-flex.large` SPOT, 6 serviços × 2 réplicas + 1 job |
| **R3** observabilidade | Helm: ArgoCD 10.13.1 e kube-prometheus-stack 92.21.1 (`platform/k8s/*-values.yaml`) | Grafana OSS e Prometheus coletando os nós EC2 e o namespace `ecosystem` |
| Validação | `platform/e2e.py --target aws` | **13/13** verificações |
| Evidências | `platform/evidence.py --target aws` | 8 capturas em `docs/evidence/aws/` |
| Offload | `tools/offload.py --target real` | 10 arquivos do S3 e 2 itens do DynamoDB copiados para disco local |
| Desmonte | Pod Identity desligado, bucket do job removido, `down` de 02 e 01, `destroy` da R4 | inventário zerado (seção 6) |

## 3. O que cada camada provou

| Verificação (e2e) | O que prova na AWS real |
|---|---|
| `k8s/<6 serviços>/health` → HTTP 200 | imagens do ECR real puxadas pelos nós EC2; probes, Services e rede de pods (VPC CNI) funcionando |
| `k8s/churn-api/predict` + contrato `scoring_result.v1` | API de churn servindo modelo real no cluster; contrato entre repositórios válido |
| `s3/riskcredit-champion` + contrato `model_manifest.v1` | o Job treinou o modelo no EKS (49,6 s) e publicou 8 artefatos com sha256 no S3 **via EKS Pod Identity, sem chave de acesso** |
| `lambda/credit-score-predict` + contrato | Lambda v3 (`v3-20260929`) respondeu HTTP 200, PD 0,235, faixa D |
| `dynamodb/inference-log` | a inferência foi gravada (1 → 2 registros) |

## 4. Achados que só apareceram na conta real

O emulador não valida estas regras; cada uma foi diagnosticada pela causa e corrigida no código.

| Sintoma | Investigação | Causa real | Correção |
|---|---|---|---|
| Node group 22 min em `CREATING`, ASG com 0 instâncias | `aws autoscaling describe-scaling-activities` | o Free Plan só lança tipos `free-tier-eligible`; `t3.medium` é recusado ("instance type is not eligible for Free Tier") | `aws ec2 describe-instance-types --filters Name=free-tier-eligible,Values=true` → `c7i-flex.large` (2 vCPU, 4 GiB, 29 pods/nó) |
| `CreateLogGroup` → `AccessDeniedException` (KMS) | erro do `terraform apply` da R4 | a chave KMS não tinha key policy liberando o CloudWatch Logs | policy com `logs.<região>.amazonaws.com` e condição no ARN do log group |
| Lambda não criaria (concorrência) | `aws lambda get-account-settings` antes do apply | conta nova tem limite 10 e a AWS exige 10 não reservadas; o código reservava 20 | variável `lambda_reserved_concurrency` (`-1` no lab) |
| `TF_VAR_enable_workload_identity=false` ignorado | `plan` tentou ler state remoto inexistente | no Windows o `os.environ` do Python devolve chaves em maiúsculas; o Terraform casa o nome exato | `lab.py` normaliza `TF_VAR_*` |
| Budget com e-mail de exemplo | conferência pós-apply do state | placeholder colado no comando | e-mail lido de `envs/real/real.auto.tfvars` (gitignored) |
| Perfil MCP "somente leitura" não lia a conta | `tools/mcp_smoke.py real` | `--read-only` no proxy esconde `aws___run_script` (6 ferramentas em vez de 8) | barreira no IAM (role `ReadOnlyAccess` + guard), sem a flag |

## 5. Custo real (Cost Explorer)

| Serviço | Custo bruto |
|---|---|
| EKS (control plane) | US$ 0,809 |
| EC2 — 2 nós SPOT | US$ 0,038 |
| VPC — IPv4 públicos | US$ 0,006 |
| EC2 — outros (EBS) | US$ 0,003 |
| KMS | US$ 0,001 |
| **Total** | **US$ 0,86** — descontado dos créditos; fatura líquida **US$ 0,00** |

Créditos: US$ 100 iniciais + US$ 60 de três atividades "Explore AWS" cumpridas pela própria sessão (budget, EC2,
Lambda) = US$ 160 → **US$ 159,14** após a sessão.

## 6. Desmonte verificado

Conferido em 12/11/2026 em **todas as 17 regiões**: 0 instâncias EC2, volumes EBS, IPs elásticos, NAT Gateways,
snapshots, VPCs não padrão, clusters EKS, RDS, Lambdas, load balancers e tabelas DynamoDB; 0 buckets S3.
Permanecem só itens **sem custo**: as roles `deployer` e `mcp-readonly`, a policy `free-plan-guard` e os 2 budgets de
alerta. A chave KMS ficou em exclusão agendada (não é cobrada). Ao fim dos créditos ou do prazo, o Free Plan suspende
a conta em vez de cobrar — só um upgrade manual para o plano pago mudaria isso.

## 7. MCP contra a conta real

`python tools/mcp_smoke.py real` (12/11/2026), chamadas só de leitura:

| Servidor | Ferramentas | Resultado |
|---|---|---|
| AWS MCP Server gerenciado (`mcp-proxy-for-aws-cli` 1.7.0) | 8 | `aws___run_script` na conta: STS, EKS e S3 ok (0 clusters, 0 buckets — conta limpa) |
| `awslabs.eks-mcp-server` 0.2.1 | 16 | autenticou na AWS; "cluster não encontrado" (esperado, cluster já destruído) |
| `hashicorp/terraform-mcp-server` 1.4.1 | 9 | ok |

Uso no dia a dia: `python tools/mcp_session.py` (digita o código MFA) gera credenciais de 1 h da role somente leitura
no perfil `argus-lab-mcp`; depois `python tools/mcp_profile.py real` e abrir o Claude Code.

## 8. Como reproduzir

```bash
# pré-requisitos: AWS CLI com perfil argus-lab (usuário IAM + MFA), Terraform >= 1.10, Docker, kubectl, Helm
cp envs/real/aws-config.example ~/.aws/config        # ajustar ID da conta e MFA
# envs/real/real.auto.tfvars (gitignored): budget_email, enable_workload_identity, node_group
python platform/lab.py up --target real --stacks 06-identity --yes-real-aws      # R0
python platform/lab.py up --target real --stacks 01-networking --yes-real-aws    # R1
python platform/lab.py up --target real --stacks 02-eks --yes-real-aws           # R2
python platform/images/build.py --target aws                                     # 7 imagens -> ECR
# enable_workload_identity = true e reaplicar 06-identity (Pod Identity)
python platform/lab.py kubeconfig --target real
helm upgrade --install argocd argo/argo-cd --version 10.13.1 -n argocd --create-namespace -f - < platform/k8s/argocd-values.yaml
helm upgrade --install monitoring prometheus-community/kube-prometheus-stack --version 92.21.1 -n monitoring --create-namespace -f - < platform/k8s/monitoring-values.yaml
python platform/lab.py deploy --target real
python platform/e2e.py --target aws && python platform/evidence.py --target aws
python tools/offload.py --target real
python platform/lab.py down --target real --stacks 01-networking,02-eks --yes-real-aws
```

---

# Sessão 2 — 12/11/2026: ArgoCD puxando do GitHub e ALB com HTTPS

Objetivo: fechar as duas lacunas da sessão 1 — o deploy era feito por script (não era GitOps de verdade) e não havia
entrada pública (só `port-forward`).

## O que mudou no código (antes de subir)

| Peça | Mudança | Por quê |
|---|---|---|
| `01-networking` | `aws_ec2_tag`: `kubernetes.io/role/elb=1` nas subnets públicas e `internal-elb=1` nas privadas | o AWS Load Balancer Controller descobre onde criar o ALB por essas tags; o módulo do submódulo não foi alterado |
| `02-eks` | provider `tls`: chave RSA 2048 + certificado **autoassinado** `*.argus.lab` (7 dias) importado no ACM; output `vpc_id` | sem domínio próprio não há certificado público válido; a chave vive só no state local (gitignored) |
| `06-identity` | role do controller com a **policy oficial v3.6.2** (`policies/aws-load-balancer-controller-v3.6.2.json`) via EKS Pod Identity | sem chave estática; versão da policy casada com a versão do chart |
| `gitops` | Ingress no overlay `aws` para `creditscore-app` e `churn-api`: ALB compartilhado (`group.name: argus`), HTTP 80 → 301 → HTTPS 443, política `ELBSecurityPolicy-TLS13-1-2-2021-06`, `target-type: ip`, health check por app | um único ALB (custo) com roteamento por host; o certificado é achado pelo host do `tls` (nenhum ARN no git) |
| `lab.py addons` | instala com Helm, em versões fixas, ArgoCD 10.13.1, kube-prometheus-stack 92.21.1 e AWS Load Balancer Controller 3.6.2 (`clusterName`, `vpcId`, SA com Pod Identity) | antes eram comandos manuais do README |
| `lab.py argocd` | cria o Application `platform-env-aws` e o ApplicationSet `ecosystem-aws` (7 apps) apontando para `github.com/Yuri-Fernando/AWS-Project`, `main`, `gitops/apps/<app>/overlays/aws`, sync automático com prune e self-heal; o ID da conta entra **só em memória** como `kustomize.images` | o cluster passa a **puxar** do repositório; o git continua com `ACCOUNT_ID` |
| `lab.py down` | antes de destruir o EKS: apaga Applications e Ingress e espera o controller remover o ALB (até 10 min, senão aborta) | o ALB é criado fora do Terraform; se o cluster morrer antes, o ALB fica órfão cobrando e a VPC não apaga |
| `e2e.py` | +5 verificações na AWS: ArgoCD Synced/Healthy, HTTPS 200 via ALB nos 2 hosts, redirect 301 nos 2 hosts | provar entrada pública e GitOps, não só o cluster |
| `evidence.py` | captura do app servido pelo ALB em HTTPS (`--host-resolver-rules` mapeia `*.argus.lab` para o IP do ALB) | evidência visual da entrada pública |
| `tools/real_snapshot.py` | grava o estado vivo da sessão em `docs/aws-real/sessao-AAAA-MM-DD/` | consulta futura sem acesso à nuvem |

## Execução (comandos na ordem real)

```bash
python platform/lab.py up --target real --stacks 01-networking --yes-real-aws   # 29 recursos (23 + 6 tags)
python platform/lab.py up --target real --stacks 02-eks --yes-real-aws          # 30 recursos (27 + chave, cert, ACM)
terraform -chdir=../meu-projeto-aws/infra/terraform apply ...                   # R4: 30 recursos
# enable_workload_identity = true
python platform/lab.py up --target real --stacks 06-identity --yes-real-aws     # +13 (9 apps + 4 do controller)
python platform/lab.py kubeconfig --target real
python platform/lab.py addons --target real                                     # 3 releases Helm "deployed"
python platform/images/build.py --target aws                                    # 7 imagens no ECR
python platform/lab.py argocd --target real                                     # 8 Applications
python platform/e2e.py --target aws                                             # 18/18
python platform/evidence.py --target aws                                        # 9 capturas
python tools/real_snapshot.py                                                   # retrato operacional
python tools/offload.py --target real                                           # 10 arquivos S3 + 1 item DynamoDB
python platform/lab.py down --target real --stacks 01-networking,02-eks --yes-real-aws
```

## Resultados

| Verificação | Resultado |
|---|---|
| ArgoCD | 8/8 Applications **Synced + Healthy**, fonte `github.com/Yuri-Fernando/AWS-Project` @ `main` |
| ALB | 1 ALB compartilhado `k8s-argus-*`, internet-facing, 3 AZs; listeners HTTP 80 (redirect) e HTTPS 443 com 1 certificado |
| HTTPS | `churn.argus.lab/health` e `creditscore.argus.lab/_stcore/health` → **HTTP 200 via TLS 1.3** |
| Redirect | HTTP → **301** → `https://<host>:443/...` nos dois hosts |
| Alvos | 4 alvos **healthy** (2 pods por app, IPs de pod — `target-type: ip`) |
| Certificado | `*.argus.lab`, tipo `IMPORTED`, status `ISSUED`, em uso pelo listener |
| e2e completo | **18/18** (13 da sessão 1 + 5 novos) |

## Achados desta sessão

| Sintoma | Causa real | Correção |
|---|---|---|
| `helm` → "invalid leading UTF-8 octet" ao ler os values | no Windows o `subprocess` do Python envia stdin em cp1252; os comentários em português viram bytes inválidos | `encoding="utf-8"` explícito nas chamadas com stdin (`addons`, `deploy`, `argocd`) |
| Valor do Secret de laboratório apareceu no log do terminal | a função que imprime comandos mostrava `--from-literal=CHAVE=valor` | `shown()` mascara `--from-literal` e `password=` em toda saída do `lab.py` |
| VPC presa ~8 min no `destroy` da rede | o controller cria o security group `k8s-traffic-<cluster>` (ALB → pods) e morreu com o cluster antes de apagá-lo | removido o SG; o `lab.py` agora apaga, depois que o ALB some, os SGs com a tag `elbv2.k8s.aws/cluster` |
| **Ingress travado e ALB não apagava** no desmonte | desliguei o Pod Identity (stack 06) **antes** de apagar o Ingress: o controller perdeu a credencial AWS e não conseguia remover o ALB; a trava do `lab.py` recusou destruir o EKS (evitou ALB órfão) | religado o Pod Identity → controller apagou o ALB em 30 s; o `lab.py` agora **libera o ALB automaticamente** antes de desligar o Pod Identity ou destruir a stack 06 |

## Desmonte

Offload (10 arquivos S3 + 1 item DynamoDB) → Pod Identity desligado (com a liberação automática do ALB) → `down` do
EKS (30 destruídos) e da rede (29 destruídos) → `destroy` da R4 (30 destruídos) → bucket do job removido.

**Verificação final (12/11/2026), todas as 17 regiões:** 0 instâncias EC2, volumes EBS, IPs elásticos, NAT, VPCs não
padrão, clusters EKS, RDS, Lambdas, load balancers, tabelas DynamoDB, certificados ACM e repositórios ECR; 0 buckets
S3. Permanece só a R0 (roles, policy e budgets — sem custo).

**Custo:** estimado em ~US$ 0,40 (EKS ~US$ 0,10/h + ALB ~US$ 0,02/h + nós SPOT e IPs por ~2,5 h), coberto pelos
créditos. O Cost Explorer lança o valor com atraso de algumas horas; no fechamento desta sessão os créditos ainda
marcavam US$ 159,14 (antes do lançamento).
