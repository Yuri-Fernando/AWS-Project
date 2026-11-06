# PLANO v0.2 — Curso DevOps na Nuvem × Repositórios × Argus Master, com AWS a custo zero
> **Atualização (05/11/2026):** a execução passa a ter o **floci** (emulador AWS local) como alvo padrão. Ver
> `PLANO_DE_ACAO_v1_floci_MCP.md`. Este documento continua valendo para a avaliação de custos, os guardrails e o passo
> opcional na AWS real.
**Data:** 05/11/2026 · **Substitui parcialmente:** `Plano_Master_Argus_AWS_Data_AI_2026.md` (v0.1, mantido) e o HANDOFF de 05/11.
**Base factual:** transcrição + OCR das 9 aulas (11h57) gerados por `tools/course_kb`, Terraform dos materiais do curso,
Terraform/infra dos seus repositórios e documentação AWS consultada em 05/11/2026.

---

## 0. Decisões em uma página
1. **AWS = computação efêmera; tudo que precisa durar fica fora da AWS.** O Free Plan fecha a conta em **05/05/2027**
   (ou quando os créditos acabarem) e apaga tudo 90 dias depois. Código → GitHub; imagens → GHCR; dados/artefatos →
   Cloudflare R2 ou disco local/Drive; bancos → Supabase/Neon/Atlas (já usados por você); evidências → repositório.
2. **Local primeiro, AWS em "sessões burst".** Tudo do Dia 2 (Kubernetes, ArgoCD, Kustomize, probes/PDB, Prometheus/Grafana)
   roda de graça em `kind`. A AWS entra só para o que não existe localmente (EKS, IAM/OIDC real, ECR, AMP, VPC real), sempre
   no ciclo `plan → apply → evidência → destroy` no mesmo dia — exatamente o que o instrutor recomenda.
3. **Custo-alvo:** o próprio instrutor relata que os alunos gastam **US$ 10–15/mês** estudando todo dia com apply/destroy.
   Com US$ 100 (+ até US$ 100 em atividades) isso cobre o curso inteiro **sem desembolso**, desde que nada fique ligado.
4. **Três desvios obrigatórios do curso** (senão quebra o R$ 0):
   - **Não fazer as aulas 05/06 como gravadas**: o Amazon Managed Grafana com IAM Identity Center **ativa o AWS
     Organizations** numa conta standalone — e entrar no Organizations **converte o Free Plan em pago (irreversível)**.
     O instrutor fez dentro da organização dele. Alternativa: Grafana via Helm (local ou no cluster) lendo o AMP por SigV4.
   - **1 NAT Gateway (ou nenhum) em vez de 3.** A arquitetura gerada no Dia 1 estimava ~US$ 65/mês só de VPC.
   - **Sem Route 53/ACM/external-dns** a menos que você já tenha um domínio (zona hospedada e domínio custam dinheiro).
5. **Não criar repositório novo.** O conhecimento do curso entra no `Enterprise Cloud Automation Platform` (infra) e nos
   workloads `RetentIQ`/`ArgusAI` (apps), como já previa o v0.1. Os repos do Kenerry ficam como *submodules* de referência
   no hub `Projetos_Pessoais` (HANDOFF, seção H) — não executar o IaC deles sem a auditoria da seção G do HANDOFF.

---

## 1. O que foi extraído (e onde está)
| Item | Local | Observação |
|---|---|---|
| Script | `tools/course_kb/course_kb.py` + `README.md` | reutilizável para qualquer curso em vídeo |
| Base de conhecimento | `Q:\Cursos Pagos\DevOps na Nuvem ( )\_kb\` | **privada** (derivada de curso pago) |
| Índice do curso | `_kb\KNOWLEDGE.md` | serviços, ferramentas, recursos TF, comandos, menções a custo |
| Por aula | `_kb\<aula>\lesson.md` | linha do tempo de 5 em 5 min com fala + telas de código/terminal |
| Cobertura | `_kb\COVERAGE.md` | termo × curso × plano × repositório |

Números: 9/9 aulas íntegras (clipes de 6 s em `_invalid_clips` descartados); ~84 mil palavras transcritas; 1.054 telas
distintas lidas por OCR. Os vídeos válidos estão em `DevOps na Nuvem\<módulo>\<aula>\` (não nos caminhos do `TRANSCREVER.md`).

---

## 2. Mapa do conhecimento do curso
### Dia 1 — Agentes de IA, Terraform e Redes (5h38)
| Tempo | Conteúdo |
|---|---|
| 00:00–00:30 | Agenda; setup do Terraform com a conta AWS; remote backend e state locking |
| 00:30–01:00 | Usuário IAM + `~/.aws/credentials`; primeira VPC com `terraform apply` |
| 01:00–02:30 | **Harness de agentes no Claude Code**: system prompt, subagentes, *skills*, *rules*, MCP; Terraform MCP + AWS MCP via Docker; skill que roda `apply`, verifica e corrige erro |
| 02:30–03:30 | Agente gera ADR de VPC multi-AZ (3 NATs, ~US$ 65/mês — "tá uma bosta isso ainda"); convenções de nomenclatura (`vpc.public-subnets.tf` …); variáveis objeto |
| 03:30–04:45 | Redes: CIDR, subnets públicas/privadas, IGW (1 por VPC) × NAT (1 por AZ), route tables, IPs para pods |
| 04:00–04:30 | Skill **terraform-deploy multi-stack** criada com o skill-creator |
| 05:00–05:38 | Terraform state, risco de corrupção, **backend S3 + locking**, migração do state local para o bucket |

### Dia 2 — Agentes de IA, Kubernetes e Pipelines (5h25)
| Tempo | Conteúdo |
|---|---|
| 00:15–01:00 | Kubernetes: pod × container, Deployment, ReplicaSet, probes, PDB, HPA, Service, Ingress/ALB |
| 01:00–01:30 | **EKS MCP Server**; EKS com managed node group (2 nós) sobre a VPC do Dia 1 via `terraform_remote_state`; Fargate × EC2 (Fargate é caro para 24×7) |
| 02:00–02:45 | Operar o cluster com o agente (listar nodes/pods, 403 de access entry, criar pod) |
| 02:45–03:15 | Skills **dockerfile-generator** e **docker build/push para ECR** |
| 03:15–03:45 | Manifestos com probes/PDB, **Kustomize**; secrets (External Secrets × Sealed Secrets) |
| 04:00–05:17 | **GitHub Actions com OIDC** (role assumida pela pipeline), push no ECR, `kustomize edit set image`, **ArgoCD** (GitOps, auto-heal ao deletar o deployment), variável `AWS_ROLE_ARN` |

### Observabilidade — bônus do eks-express (54 min)
AMP workspace com log group (Terraform) → add-on Node Exporter → **AMP Scraper gerenciado** para EKS → Grafana workspace
→ IAM Identity Center (login) → dashboard Node Exporter.

### Infra dos materiais (Terraform real, por stack)
- `dvn-workshop-maio`: `00-remote-backend` (S3 versionado + criptografia + lifecycle, **sem DynamoDB**) → `01-networking`
  (VPC, subnets, IGW, NAT/EIP, **flow logs**) → `02-eks` (cluster, node group, add-ons, **ECR**, SG) → `03-ci-cd` (**OIDC GitHub** + role).
- `eks-express-iac`: `00-backend` (S3 + DynamoDB) → `01-networking` (+ subnets de observabilidade) → `02-eks-cluster`
  (ACM, Route 53, access entries, OIDC/IRSA, Helm) → `03-karpenter` → `04-security` (WAFv2) → `05-monitoring` (AMP, scraper, AMG).

---

## 3. Curso × seus repositórios × plano
| Capacidade do curso | Enterprise Cloud Automation | meu-projeto-aws | ArgusAI / RetentIQ | Ação |
|---|---|---|---|---|
| VPC, subnets, IGW, NAT, route tables | ✅ `modules/networking` | — | — | **ADAPT**: flag `nat_mode = none\|single\|per_az`; adicionar flow logs opcional |
| Remote backend S3 + locking | ⚠️ não há stack de backend | parcial (S3 versionado/KMS) | — | **NEW** stack `00-backend` com `use_lockfile` (Terraform ≥ 1.10), sem DynamoDB |
| IAM / OIDC GitHub → AWS | ✅ `aws_iam_openid_connect_provider` existe | — | — | **REUSE** + role de deploy mínima (ECR push + EKS describe) |
| EKS (cluster, node group, add-ons, access entries) | ❌ (só EC2 ASG + ALB) | — | ⚠️ **Argus já tem `terraform/modules/aws/eks`** mínimo (cluster + node group + roles; sem add-ons, access entries, OIDC/IRSA) e `k8s/` (10 manifestos) | **ADAPT**: promover o módulo do Argus para o Enterprise como `modules/eks` completo (padrões do curso) e o `environments/dev-aws` do Argus passa a consumi-lo por `source` git com tag |
| Rede AWS duplicada | `modules/networking` | — | Argus `modules/aws/network` | **DEDUP**: uma única fonte (Enterprise); Argus referencia |
| ECR | ❌ | — | — | **NEW** (só durante sessão); fonte da verdade = **GHCR** |
| Kubernetes: probes, PDB, HPA, Kustomize | Helm chart `automation-controller` | — | Argus `k8s/`; RetentIQ só Docker | **ADAPT**: overlays Kustomize `local/` e `eks/` para RetentIQ API e Argus API |
| GitOps ArgoCD | 📄 só ADR (`docs/decisions/ADR-002-gitops-argocd.md`) | — | Argus cita (ADR-023 EKS/Istio) | **IMPLEMENT** o ADR existente: `kind` primeiro, depois EKS |
| GitHub Actions build/push/promote | ✅ 7 workflows (tf-ci, trivy, policy-gate…) | ✅ `ci.yml` | ✅ Argus 9 workflows | **ADAPT**: workflow OIDC → GHCR (sempre) e ECR (sessão) + `kustomize edit set image` |
| Prometheus/Grafana | ✅ `modules/monitoring` (CloudWatch + SNS); stack Prom/Grafana/Loki citada no README | ✅ dashboard CloudWatch | — | **ADAPT**: kube-prometheus-stack local; AMP+scraper 1 sessão; **sem AMG** |
| Karpenter, WAF, ACM/Route 53 | ❌ | — | — | **P2 / opcional** (custo e domínio) |
| Serverless (Lambda, API GW, Cognito, SageMaker, Step Functions) | — | ✅ já real (v1) | — | **REUSE** como evidência AWS mais barata; fora do escopo do curso |
| Budget/alarmes | ✅ `modules/budget` | ✅ budget + alarmes | — | **REUSE** + budget com créditos excluídos |
| Harness de agentes (agents/skills/rules/MCP) | — | — | — | **ADAPT** para `~/.claude/skills` (Jarvis): `terraform-multi-stack`, `docker-build-push`, `dockerfile-generator`; MCP Terraform + AWS docs (somente leitura) |
| Dados/ML/LLM (Sprints 1–5 do v0.1) | — | ✅ MLOps | ✅ | **O curso não cobre** — continuam locais como no v0.1 |

Detalhe quantitativo por termo: `_kb\COVERAGE.md` (ocorrências textuais, indicador de presença — não prova de funcionamento).
Resultado da varredura (108 termos com ≥ 2 menções no curso, 8 bases): **80 já aparecem em algum repo seu**, **18 só nos materiais
do curso** (Kustomize, `aws_eks_addon`, `aws_eks_access_entry`, `aws_prometheus_scraper`, `aws_flow_log`, `aws_ecr_repository`,
Karpenter, external-dns, AWS LB Controller, lifecycle de S3…) e **10 lacunas totais** (Managed Grafana e seus recursos,
Node Exporter, cert-manager, rule groups do AMP). "Aparece" muitas vezes é README/ADR: EKS e ArgoCD no Enterprise são só documentação.

**O que muda no v0.1:** o Sprint 7 (EKS/Platform) ganha conteúdo concreto e sobe de prioridade **depois** do Gate A; entra um
item novo (harness de agentes/MCP, que o curso trata como eixo e o v0.1 não tinha); o perfil AWS-LITE passa a ser
"sessões burst" com orçamento por sessão; AMG sai do escopo.

---

## 4. Avaliação "AWS de graça"
### 4.1 Fatos (documentação AWS, 05/11/2026)
- Free Plan: US$ 100 de crédito + até US$ 100 em 5 atividades (EC2, Bedrock playground, AWS Budgets, Lambda web app, RDS).
  Sem cobrança enquanto durar; termina em 6 meses ou ao zerar créditos; **conta fecha** e conteúdo é retido 90 dias.
- Upgrade automático para pago se: entrar no **AWS Organizations**, criar landing zone do **Control Tower**, entrar na APN,
  contrato de Professional Services/Enterprise Agreement, Skill Builder Team, ou marcar conta como HIPAA/SEC.
- Free Plan só dá acesso a "serviços selecionados"; Savings Plans, Reserved Instances e parte do Marketplace ficam de fora.
  **Trials de curto prazo** (ex.: o trial de 90 dias do Managed Grafana) são listados como benefício do **plano pago**.
- **A verificar no console antes de planejar sessões** (não encontrei lista oficial): EKS, AMP e Spot disponíveis no Free Plan?

### 4.2 Custo estimado por sessão de laboratório EKS (us-east-1, sob demanda — conferir no Pricing Calculator antes do apply)
| Recurso | US$/h aprox. | Observação |
|---|---|---|
| EKS control plane | 0,10 | o item que mais pesa; não deixar ligado |
| 2 × t3.medium (nós) | 0,083 | spot reduz bastante, se disponível no plano |
| 1 NAT Gateway + EIP | 0,045 + 0,005 | 3 NATs (padrão multi-AZ do agente) triplicam |
| ALB (se usar Ingress) | ~0,025 | preferir `port-forward` na maior parte da sessão |
| EBS, logs, ECR, AMP | centavos | definir retenção curta de logs |
| **Total** | **≈ 0,25–0,30/h** | sessão de 4 h ≈ **US$ 1–1,20** |

Erros que estouram o orçamento: esquecer o cluster ligado (~US$ 6–7/dia), NAT por AZ, Managed Grafana, IPv4 públicos
esquecidos, zona Route 53, Fargate 24×7, endpoints SageMaker.

### 4.3 Guardrails (fazer antes da primeira sessão — tudo grátis)
1. AWS Budgets: um **zero-spend** e um mensal **com créditos excluídos** (senão os créditos escondem o gasto), alertas por e-mail
   — e isso já conta como 1 das 5 atividades de crédito.
2. **Budget action** que anexa política *deny* (EC2/EKS/NAT/ELB/RDS/SageMaker) ao seu usuário/role de lab ao atingir o limite.
   Lembrando: bloqueia novas criações, **não** desliga o que já está rodando.
3. Tags obrigatórias `project, owner, ttl, session` (default_tags no provider) + script `lab-teardown` que roda `terraform destroy`
   nas stacks em ordem reversa e depois lista recursos remanescentes por tag (Resource Groups Tagging API).
4. Credenciais: substituir as chaves antigas (que falhavam) por usuário/role de lab com MFA; no CI, **somente OIDC**.
   Nunca `AdministratorAccess` como sugerem os READMEs do curso.
5. Não tocar em Organizations, Control Tower, Identity Center em modo organização, Marketplace.

### 4.4 Atividades para ganhar os +US$ 100 (fazer cedo, com teardown imediato)
Budget (grátis) · EC2 t3.micro → terminar · Lambda web app → apagar · 1 prompt no Bedrock playground · RDS db.t4g.micro sem
snapshot final → apagar. Custo líquido: centavos dos US$ 100 iniciais; retorno até +US$ 100.

---

## 5. Armazenar dados fora da AWS
| Tipo de dado | Destino primário (grátis) | Na AWS, só durante a sessão | Por quê |
|---|---|---|---|
| Código, IaC, manifestos, ADRs, evidências | GitHub (repos existentes) | — | sobrevive ao fechamento da conta |
| Imagens de container | **GHCR** (GitHub Container Registry) | ECR (push na sessão; lifecycle apaga) | pipeline publica nas duas; cluster local usa GHCR |
| Terraform state | S3 + `use_lockfile` **na própria AWS** (padrão do curso) | — | como toda stack é destruída no fim da sessão, o state fica vazio → perder o bucket não custa nada; a stack `00-backend` usa state local versionado no Git |
| Datasets, Parquet/Delta, modelos, artefatos | **Cloudflare R2** (10 GB, sem egress, API S3) ou disco local + Drive | S3 temporário | R2 fala API S3 → mesmo código boto3/Spark com endpoint diferente |
| Bancos relacionais/documentos | Supabase / Neon (Postgres), MongoDB Atlas M0 (já usados) | RDS só no exercício DBRE, com `pg_dump` → R2 | evita RDS ligado |
| Métricas/dashboards | Prometheus + Grafana locais (kube-prometheus-stack) | AMP + scraper em 1 sessão | AMG fora por causa do Organizations |
| Base de conhecimento do curso | `Q:\...\_kb` + backup no Drive | — | privada |

Alternativa ao state na AWS, se quiser state persistente entre sessões: HCP Terraform Free (500 recursos gerenciados,
1 execução simultânea, desde 31/03/2026) em modo de execução local — sem depender da conta AWS.

---

## 6. Plano de execução integrado
Ordem pensada para gerar evidência cedo e gastar crédito só onde o local não alcança.

| Fase | Onde | Entregas | Aulas | Custo AWS | Aceite |
|---|---|---|---|---|---|
| **F0 — Guardrails + harness** | conta AWS, `~/.claude` | budgets (4.3), atividades de crédito (4.4), MCP Terraform + AWS docs **somente leitura**; skills `terraform-multi-stack`, `docker-build-push`, `dockerfile-generator` adaptadas (não copiadas) | D1 01:00–02:30, 04:00; D2 02:30–03:15 | ~0 (+ até US$ 100) | budgets ativos, créditos conferidos, skills com teste |
| **F1 — Kubernetes local** | RetentIQ, ArgusAI | `kind` + ArgoCD + Kustomize (`local/`, `eks/`), probes/PDB/HPA, kube-prometheus-stack, imagens no GHCR via Actions | D2 00:15–01:00, 03:15–05:17 | 0 | `make k8s-up` sobe tudo; ArgoCD sincroniza; deletar um deployment volta sozinho |
| **F2 — Terraform base** | Enterprise Cloud Automation | stacks `00-backend` (`use_lockfile`), `01-networking` (`nat_mode`), `03-ci-cd` (OIDC); `fmt/validate/tflint/checkov` + Infracost no CI; ensaio em LocalStack onde suportado | D1 00:30–01:00, 03:00–05:38 | 0 | `plan` limpo, custo estimado no PR |
| **F3 — 1ª sessão real: rede** | idem | apply backend + VPC (1 NAT) → evidência → destroy | D1 | < US$ 0,50 | recursos criados/destruídos registrados, inventário por tag vazio |
| **F4 — Sessão EKS + GitOps** | idem + RetentIQ/Argus | `02-eks` (2 nós, spot se permitido), ECR, Actions OIDC → ECR, ArgoCD no EKS, deploy RetentIQ API | D2 01:00–05:17 | US$ 1–2 por sessão | rollout/rollback, auto-heal e pipeline verde com evidência; destroy completo |
| **F5 — Observabilidade** | idem | Node Exporter + AMP scraper; Grafana via Helm lendo AMP por SigV4 (**sem AMG**) | Obs. 01–04, 07 | < US$ 1 | dashboard Node Exporter com dados do EKS |
| **F6 — Opcionais** | idem | Karpenter (corrigir `limits.cpu = "1Gi"` antes), WAF em COUNT, ACM só com domínio próprio | eks-express 03/04 | US$ 1–3 | apenas com aprovação explícita |
| **F7 — Portfólio** | READMEs | matriz LOCAL_REAL / AWS_REAL / PLANNED, vídeo curto, custos reais por sessão | — | 0 | `readme-check` passa; nada inventado |

Em paralelo, sem depender do curso: Sprints 1–5 do v0.1 (Customer360, Spark/Delta, DBRE PostgreSQL, ML, agentes) seguem locais.

---

## 7. Riscos e pendências
| Risco | Mitigação |
|---|---|
| Upgrade involuntário para pago (Organizations via AMG/Identity Center) | proibido no runbook; Grafana auto-hospedado |
| Recurso esquecido ligado | TTL + teardown + inventário por tag + budget action; nunca encerrar sessão sem inventário vazio |
| Serviço indisponível no Free Plan (EKS/AMP/Spot) | **verificar no console antes da F3**; se EKS estiver bloqueado, F4 vira k3s em 1 EC2 t3.small ou fica local |
| IaC do curso com permissões amplas e erros conhecidos | auditoria da seção G do HANDOFF; reescrever em módulos próprios |
| Transcrição com termos errados ("Cloud Code", "Carpenter") | conferir na tela/keyframe antes de usar como fonte |
| Conteúdo pago publicado por engano | `_kb` fora de git; nada de transcrição em repo público |

**Decisões que dependem de você**
1. Abrir os consoles EKS e Prometheus na conta e me dizer se aparecem bloqueados no Free Plan (define F4/F5).
2. Confirmar o state: padrão do curso (S3 na AWS, efêmero) — recomendado — ou HCP Terraform.
3. Autorizar a F3 (primeira sessão real, < US$ 0,50 de crédito) quando a F0–F2 estiverem verdes.
