# PLANO DE AÇÃO v2 — Ecossistema Argus completo na "AWS local" em 2 dias
**Data:** 05/11/2026 · **Substitui o cronograma de 4 semanas do v1** (`PLANO_DE_ACAO_v1_floci_MCP.md` continua como referência técnica).
**Restrição:** R$ 0. Tudo roda no **floci** (emulador AWS local) + k3s do EKS emulado. AWS real fora do escopo destes 2 dias.

## Meta ao fim do Dia 2
`make up` no Enterprise sobe, sem conta AWS:
1. A infra do curso (backend S3 → VPC → EKS → ECR → OIDC → WAF → AMP) aplicada via Terraform no floci.
2. Um cluster EKS (k3s real) com **ArgoCD** implantando os apps dos repos da conversa.
3. O **Credit Score serverless** (Lambda + API Gateway + DynamoDB + S3 + Step Functions + Cognito) aplicado no floci com o Terraform que já existe.
4. Prometheus + Grafana com dashboards; agente Claude Code operando tudo via **MCP**.
5. Pipeline no GitHub Actions que sobe o floci no runner, aplica, testa e destrói.

## Repositórios da conversa → papel nos 2 dias
| Repo (GitHub) | Pasta local | Docker hoje | Papel | Como entra |
|---|---|---|---|---|
| Enterprise-Automation | `Enterprise Cloud Automation Platform` | ✅ Dockerfile + compose de observabilidade | **plataforma**: stacks Terraform, GitOps, Makefile, CI | recebe `platform/` e `gitops/` |
| Argus | `ArgusAI` | ✅ compose + `api/main.py` | produto principal (API de insights + lakehouse em S3) | imagem → EKS; buckets Bronze/Silver/Gold no S3 do floci |
| RetentIQ | `RetentIQ` | ✅ `apps/api`, `apps/web` | gerador de eventos de cliente | API → EKS; eventos → MSK (Redpanda) ou SQS do floci |
| ThemisAI | `ThemisIA` | ✅ Dockerfile + dashboard | policy gate de PII/LGPD | imagem → EKS |
| OmniMind_AI_OS | `Agente AIOS` | ✅ `infra/dockerfile` + `api/server.py` | agente/RAG que consulta os serviços | imagem → EKS; usa os MCPs |
| Churn_intelligence | `Comportamento e Churn` | ✅ `docker/` + `src/api/app.py` | serviço de modelo de churn | imagem → EKS |
| RiskCredit | `Risco de Credito` | ❌ | treina o modelo de crédito | job que grava o artefato no S3 do floci (Dockerfile novo, pequeno) |
| Credit-Score-Predictor-AWS | `meu-projeto-aws` | ❌ (Streamlit em `App/`) | serving serverless de crédito | `infra/terraform` aplicado no floci + Streamlit em container |
| IA_Agentica | só GitHub | — | tooling de agentes (não é runtime) | fonte das skills/MCP do harness |
| Projetos_Pessoais (hub) | só GitHub | — | catálogo | +2 submodules do curso (commit local; push via @devops) |
| dvn-workshop-maio / eks-express-iac | materiais em `Q:` | — | referência do curso | padrões reescritos em `platform/` (não copiar literal) |

**Velocidade:** os builds partem de clones em `D:\Claude Temp\staging\eco\` (fora do Google Drive). O código editado volta para o repo
real. Os manifests de Kubernetes de todos os apps ficam **centralizados** em `Enterprise/gitops/apps/<app>`, para não abrir 8 PRs.

---

## DIA 1 — Plataforma
| Hora | Bloco | Entregas | Pronto quando |
|---|---|---|---|
| 0:00–0:30 | **B1 Máquina** | Docker Desktop ligado; helm instalado; `D:\floci-data`; floci em versão fixa via compose (`platform/floci/`) | `aws sts get-caller-identity` responde do floci |
| 0:30–2:00 | **B2 Spike** | IaC do curso (cópia em staging) aplicado no floci; matriz PASS/FAIL em `docs/floci-compat-matrix.md` | matriz preenchida; lista de substitutos fechada |
| 2:00–4:30 | **B3 Stacks próprias** | `platform/terraform/00-backend … 05-monitoring` com `var.aws_endpoint` (alvo duplo); reaproveita `modules/networking`, `iam`, `budget`; `02-eks` promove o módulo EKS do Argus | `make up` / `make down` limpos no floci |
| 4:30–5:30 | **B4 Cluster** | `update-kubeconfig` do EKS emulado; ArgoCD via Helm; app-of-apps em `gitops/` | ArgoCD UI abre; app de exemplo Synced |
| 5:30–6:30 | **B5 Observabilidade** | kube-prometheus-stack (Prometheus, node-exporter, Grafana OSS) + dashboard 1860 | Grafana mostra métricas do k3s |
| 6:30–7:30 | **B6 MCP + skills** | MCP AWS com `AWS_ENDPOINT_URL` do floci, MCP EKS/K8s, Terraform MCP, docs AWS; skills `terraform-multi-stack` e `docker-build-push` | o agente lista VPCs e pods do lab pelo chat |
| 7:30–8:00 | **Checkpoint** | evidências (saídas de comando, prints), histórico Jarvis, commit local por bloco | — |

## DIA 2 — Workloads dos repos + pipeline
| Hora | Bloco | Entregas | Pronto quando |
|---|---|---|---|
| 0:00–2:00 | **B7 Imagens** | clones em staging; build das 6 imagens existentes (Argus, RetentIQ api, ThemisIA, OmniMind, Churn, Streamlit do Credit Score) + Dockerfile novo do RiskCredit; push para o ECR do floci (e GHCR se o token permitir) | `aws ecr list-images` mostra as 7 |
| 2:00–3:30 | **B8 Deploy GitOps** | `gitops/apps/<app>` com Kustomize (`base` + `overlays/floci`), probes, PDB e recursos mínimos; config por ConfigMap apontando para o floci (S3/SQS/MSK) | ArgoCD com todos Synced/Healthy; `/health` de cada app OK |
| 3:30–4:30 | **B9 Serverless real** | `meu-projeto-aws/infra/terraform` aplicado no floci (override de endpoint, sem mudar a lógica); smoke da API de score | `curl` na API Gateway do floci devolve um score |
| 4:30–5:30 | **B10 Fluxo de ponta a ponta** | RetentIQ publica evento → fila/stream do floci → Argus grava Bronze no S3 → Churn pontua → ThemisIA mascara PII → OmniMind responde com fonte | script `make e2e` passa ou registra exatamente onde parou |
| 5:30–6:30 | **B11 Pipeline** | GitHub Actions no Enterprise: `services: floci` → `make up` → smoke → `make down`; build das imagens | PR com jobs verdes |
| 6:30–7:30 | **B12 Hub + docs** | submodules do curso no Projetos_Pessoais (branch local; push via @devops); README do Enterprise com "rodar sem conta AWS"; matriz `FLOCI_LOCAL / AWS_REAL / PLANNED` | `readme-check` passa |
| 7:30–8:00 | **Fechamento** | histórico, pendências, o que fica para a AWS real (Karpenter, NAT real, scraper AMP, OIDC GitHub real) | — |

## O que precisa de você
| Quando | O quê |
|---|---|
| Início do Dia 1 | OK para ligar o Docker Desktop e baixar as imagens (floci, k3s, ArgoCD, Prometheus): só disco e rede, sem custo |
| B6 | Aprovar a configuração dos MCPs (regra AIOX: `@devops`) |
| B7 | Token do `gh` com `write:packages` se quiser imagens no GHCR (opcional; o ECR do floci basta para o lab) |
| B11–B12 | Autorizar o push dos commits e do submodule (regra: `@devops`) |

## Cortes conscientes para caber em 2 dias
- Não reescrevemos lógica de nenhum app. Só container, config de endpoint e manifest.
- O e2e (B10) usa dados sintéticos e o caminho mínimo. Se um elo falhar, fica documentado e o resto segue.
- Os Sprints de Data/ML/DBRE do v0.1 (CDC, Delta MERGE, PostgreSQL/Flyway, MLflow) ficam para depois. Os 2 dias entregam a
  **plataforma e a integração**, não a evolução de cada produto.
- Karpenter, Managed Grafana, scraper do AMP e OIDC do GitHub real ficam para uma sessão AWS real opcional (custos e guardrails no v0.2).

## Riscos que podem estourar o prazo
| Risco | Sinal | Plano B |
|---|---|---|
| Recurso do floci falha no Terraform | B2 | marcar no `count`/flag e seguir; não bloquear o dia |
| RAM com 7 apps + ArgoCD + Prometheus | B8 | réplicas = 1, limites baixos, subir os apps em duas ondas |
| Build lento ou `npm install` no Drive | B7 | clones em `D:` (já previsto); o RetentIQ web pode ficar fora |
| App sem `/health` ou dependente de serviço externo | B8 | probe TCP e variável de mock; registrar como pendência |
| Lentidão de I/O desta máquina (vista hoje) | todo | um build por vez; nada pesado em paralelo com o Docker |
