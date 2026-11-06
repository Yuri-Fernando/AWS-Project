# PLANO DE AÇÃO v1 — Curso DevOps na Nuvem 100% local (floci + MCP), AWS real opcional
**Data:** 05/11/2026 · **Complementa:** `PLANO_v0.2_Curso_DevOps_x_Repos_AWS_Free.md` (a avaliação de custos e guardrails da AWS real continua valendo para o passo opcional S10).

## 0. Resposta curta
Sim. O **floci** (`F:\Jarvis\repos\floci`, MIT, commit `f4c8237` de 13/10/2026, imagem `floci/floci`, porta 4566) emula a API da AWS
localmente **sem conta, sem token e sem custo**. O provider oficial `hashicorp/aws` funciona contra ele. **EKS vira um k3s real**,
**ECR é um registry real**, EC2/RDS/MSK sobem containers de verdade. No pool não há outro emulador (LocalStack Community
foi descontinuado em mar/2026, segundo o README do floci). A AWS real fica para 1–2 sessões de prova, com os mesmos
arquivos Terraform (só troca o alvo).

**Mudança de estratégia:** alvo padrão = `floci` (ilimitado, R$ 0); alvo `aws` = evidência final opcional.

## 1. O que o curso usa × o que o floci entrega
Legenda: ✅ funciona com fidelidade útil · 🟡 só a API (o recurso existe no estado, sem efeito real) · ❌ não há → substituto.
"CI" = coberto pelo teste de compatibilidade Terraform do próprio floci; "doc" = só documentado → validar no spike (S2).

| Aula / stack | Recurso | floci | Substituto / observação |
|---|---|---|---|
| D1 backend remoto | `aws_s3_bucket`, versioning, lifecycle, SSE | ✅ CI | state em S3 emulado; locking: `use_lockfile` (validar) ou tabela DynamoDB (CI usa) |
| D1 rede | VPC, subnet, IGW, route table, SG | 🟡 CI | sem roteamento real (não precisa para aprender o IaC) |
| D1 rede | NAT Gateway, EIP, flow logs | 🟡 doc | **local não custa nada → pode usar 3 NATs como no curso** |
| D2 EKS | `aws_eks_cluster` | ✅ CI | **k3s com API server real**; `aws eks update-kubeconfig` → kubectl |
| D2 EKS | node group, add-ons, Fargate profile | 🟡 doc | metadados; o "nó" é o container k3s |
| D2 EKS | access entries, Pod Identity, IRSA | ✅ doc | STS `AssumeRoleWithWebIdentity` valida tokens do IRSA do EKS emulado |
| D2 ECR | repositório, `docker push/pull` | ✅ CI | lifecycle/scan guardados, não aplicados |
| D2 CI/CD | OIDC provider + role GitHub | 🟡 doc | token real do GitHub não valida → **no CI, o floci sobe como service container** com credencial de teste |
| D2 K8s | Deployments, probes, PDB, HPA, Service, Kustomize, ArgoCD | ✅ | rodam no k3s do EKS emulado (Kubernetes real) |
| Ingress / ALB | ELBv2 | 🟡 | usar `port-forward` ou ingress do próprio k3s (Traefik) |
| eks-express 03 | Karpenter | ❌ | precisa de frota EC2 real → só no S10 (AWS real) ou fica de fora |
| eks-express 04 | WAFv2 | 🟡 CI | sem filtragem de tráfego |
| eks-express 02 | ACM, Route 53 | 🟡 CI | **local dispensa domínio** (na AWS real custaria) |
| Obs. 01–04 | AMP workspace, rule groups | 🟡 doc | sem ingestão/scraper → **Prometheus real no k3s** (kube-prometheus-stack) |
| Obs. 05 | Managed Grafana | ❌ | **Grafana OSS** via Helm no k3s |
| Obs. 06 | IAM Identity Center, Organizations | 🟡 doc | dá para praticar **sem risco** de converter o Free Plan |
| Obs. 07 | Dashboard Node Exporter | ✅ | Grafana OSS + node-exporter (dashboard 1860) |
| D1/D2 agentes | Claude Code + MCP (Terraform, AWS, EKS) | ✅ | ver S3; o MCP de AWS aponta para o floci |
| — | Budgets, Cost Explorer, Pricing | 🟡 | custo **sintetizado** do estado do floci: ótimo para treinar FinOps sem gastar |

Resultado: **todas as aulas do Dia 1 e do Dia 2 rodam localmente**. Da observabilidade, só não existe o que é "gerenciado":
scraper, ingestão no AMP e o Grafana gerenciado, que viram Prometheus e Grafana OSS reais. Karpenter fica para a AWS real.

## 2. Arquitetura do laboratório
```
Claude Code ──MCP──► Terraform MCP (docs do registry)
     │         ├────► AWS API MCP  (AWS_ENDPOINT_URL=http://localhost:4566)
     │         └────► EKS/Kubernetes MCP (kubeconfig do k3s)
     ▼
Terraform (hashicorp/aws ~> 6) ──► floci :4566 ──► S3, IAM/STS, EC2/VPC, ECR(registry real), EKS(k3s real), AMP, WAF…
                                                   └► k3s: ArgoCD · RetentIQ API · Argus API · Prometheus · Grafana OSS
GitHub Actions: services: floci → terraform apply → smoke → destroy   (de graça em repo público)
Persistência fora da AWS: GitHub (código/IaC), GHCR (imagens), D:\floci-data (estado local), R2/Supabase (dados)
```
**Alvo duplo sem duplicar código:** cada stack recebe `var.aws_endpoint` (`"http://localhost:4566"` no floci, `null` na AWS).
No provider, `endpoints { s3 = var.aws_endpoint, ec2 = var.aws_endpoint, … }` e `skip_* = var.aws_endpoint != null`.
Valor `null` = padrão real da AWS. Alternar = `TARGET=floci|aws` no Makefile.

## 3. Passos
Cada passo diz onde roda, os comandos, o critério de pronto e o tempo estimado. A ordem importa: S2 decide o resto.

### S0 — Preparar a máquina (30 min) · local
- [ ] Iniciar o Docker Desktop (dados em `F:\Docker`); `docker info` responde.
- [ ] `terraform version` ≥ 1.10 (para `use_lockfile`); instalar **helm** (`winget install Helm.Helm`); `kubectl` já existe.
- [ ] Pasta de dados do floci **fora do Drive**: `D:\floci-data` (o G: sincronizado trava com milhares de arquivos).
- **Pronto quando:** docker, terraform, helm e kubectl respondem.

### S1 — Subir o floci e fazer o smoke test (30 min) · `Enterprise Cloud Automation Platform/labs/floci/`
- [ ] `docker-compose.yml` com `floci/floci` em versão fixa (não usar `latest`), volume `D:/floci-data:/app/data`, porta 4566, UI 4500.
- [ ] `.env.floci` com `AWS_ENDPOINT_URL=http://localhost:4566`, `AWS_ACCESS_KEY_ID=test`, `AWS_SECRET_ACCESS_KEY=test`,
      `AWS_DEFAULT_REGION=us-east-1`. Sem segredo real: são credenciais fictícias do emulador.
- [ ] `aws sts get-caller-identity`, `aws s3 mb s3://smoke`, `aws eks list-clusters`.
- **Pronto quando:** os três comandos respondem pelo floci e a UI abre em `localhost:4500`.

### S2 — Spike de compatibilidade com o IaC do curso (2–3 h) · `D:\Claude Temp\staging\floci-spike`
- [ ] Copiar as stacks do `dvn-workshop-maio` (00→03) e do `eks-express-iac` (00→05) para a staging. **Nunca alterar** os materiais em `Q:`.
- [ ] Adicionar `providers_override.tf` apontando para o floci; `terraform init/apply` em ordem; depois `destroy` em ordem reversa.
- [ ] Registrar cada recurso como PASS, FAIL ou PARCIAL em `docs/floci-compat-matrix.md` (Enterprise), com versão do floci e do provider.
- **Pronto quando:** a matriz existe e mostra o que precisa de substituto. É a prova empírica da tabela da seção 1.

### S3 — Harness de agentes + MCP (1–2 h) · user scope do Claude Code
Os MCPs usados no curso: Terraform MCP (HashiCorp), AWS API MCP, EKS MCP e AWS Documentation MCP. Pelas regras AIOX, configurar MCP é
tarefa do `@devops`, com sua aprovação.
- [ ] Perfil **floci**: AWS API MCP com `AWS_ENDPOINT_URL=http://localhost:4566` e credencial de teste. Validar que a ferramenta respeita a variável.
- [ ] EKS/Kubernetes MCP usando o kubeconfig do k3s (`aws eks update-kubeconfig --name lab --endpoint-url http://localhost:4566`).
- [ ] Terraform MCP e AWS Documentation MCP (somente leitura; funcionam igual em qualquer alvo).
- [ ] Teste: "liste as VPCs" e "liste os pods" pelo agente devolvem dados do floci.
- **Pronto quando:** o agente opera o laboratório local como o instrutor opera a AWS, sem nenhuma credencial real carregada.

### S4 — Terraform de alvo duplo no Enterprise (2–3 dias) · `Enterprise Cloud Automation Platform/terraform/stacks/`
- [ ] `00-backend` (S3 + locking), `01-networking` (`nat_mode = none|single|per_az`), `02-eks` (promover o
      `ArgusAI/terraform/modules/aws/eks` e completar com access entries, add-ons, OIDC/IRSA), `03-ci-cd` (OIDC GitHub),
      `04-security` (WAF), `05-monitoring` (AMP workspace). Remote state entre stacks igual ao curso.
- [ ] Reaproveitar `modules/networking`, `iam` e `budget` existentes; **deduplicar** o `ArgusAI/terraform/modules/aws/network`.
- [ ] `Makefile`/`justfile`: `make up TARGET=floci`, `make down`, `make plan TARGET=aws` (o plan na AWS real não cria nada).
- [ ] Testes: `terraform test` ou bats no estilo do `floci/compatibility-tests/compat-terraform`.
- **Pronto quando:** `make up && make down` roda limpo no floci e `make plan TARGET=aws` gera um plano coerente.

### S5 — EKS emulado + workloads reais (2 dias) · RetentIQ, ArgusAI
- [ ] Dockerfiles com healthcheck (padrões da skill dockerfile-generator do curso); push para o ECR do floci e para o GHCR.
- [ ] Overlays Kustomize `base/`, `overlays/floci/`, `overlays/aws/` com probes, PDB, HPA e recursos (regras do CLAUDE.md do curso).
- [ ] ArgoCD via Helm no k3s, apontando para o repositório (GitOps). Teste de auto-heal: deletar o deployment e ver voltar.
- **Pronto quando:** RetentIQ API e Argus API respondem via `port-forward`, e o ArgoCD mostra Synced/Healthy.

### S6 — Pipeline (1 dia) · GitHub Actions do Enterprise e do RetentIQ
- [ ] Job `build`: imagem → GHCR (gratuito).
- [ ] Job `infra-e2e`: `services: floci` → `make up TARGET=floci` → smoke → `make down`. Prova o IaC a cada PR, de graça.
- [ ] Job `deploy-e2e`: cria o EKS no floci dentro do runner → `kubectl apply -k overlays/floci` → teste HTTP.
- [ ] O passo de OIDC para a AWS real fica escrito, mas atrás de `workflow_dispatch` manual (usado só no S10).
- **Pronto quando:** um PR mostra os três jobs verdes.

### S7 — Observabilidade (1 dia) · k3s
- [ ] `kube-prometheus-stack` (Prometheus, node-exporter, Grafana OSS). Importar o dashboard Node Exporter Full (1860).
- [ ] `aws_prometheus_workspace` e `rule_group_namespace` aplicados no floci para treinar o Terraform das aulas 03/04 (só API).
- **Pronto quando:** o dashboard mostra métricas reais do k3s e o Terraform de AMP aplica e destrói limpo.

### S8 — Skills reutilizáveis (meio dia) · `~/.claude/skills` (marcador `jarvis-control-plane`)
- [ ] Adaptar, sem copiar, os padrões do curso: `terraform-multi-stack` (deploy/destroy em ordem, com `TARGET`), `docker-build-push`
      (ECR do floci, GHCR, ECR real) e `dockerfile-generator`.
- **Pronto quando:** cada skill tem um teste de fumaça contra o floci.

### S9 — Evidência e README (meio dia)
- [ ] Matriz de status por capacidade: `FLOCI_LOCAL` / `AWS_REAL` / `PLANNED`, com commit SHA; prints sem segredos; vídeo curto.
- [ ] README com a seção "Rodar sem conta AWS: `make up TARGET=floci`". Passar no `jarvis.py readme-check`.
- **Pronto quando:** um recrutador clona e sobe tudo em 1 comando, sem conta AWS.

### S10 — (Opcional) prova na AWS real · mesmo código, `TARGET=aws`
Só o que o floci não faz: NAT e roteamento reais, nós EC2 reais, OIDC GitHub real, scraper AMP, Karpenter.
Seguir os guardrails do v0.2 (budgets com créditos excluídos, TTL, teardown, inventário por tag), em sessão única de
cerca de US$ 1–2 de crédito, com **sua autorização explícita**. Nunca Managed Grafana nem Identity Center no modo organização.

## 4. Cronograma sugerido (meio período)
| Semana | Passos | Entrega visível |
|---|---|---|
| 1 | S0, S1, S2, S3 | floci rodando, matriz de compatibilidade, agente operando o laboratório via MCP |
| 2 | S4 | 6 stacks do curso em código próprio, alvo duplo, `make up/down` |
| 3 | S5, S6 | apps no EKS emulado com GitOps e pipeline e2e verde no GitHub |
| 4 | S7, S8, S9 (+ S10 opcional) | observabilidade, skills e README de portfólio |

## 5. Riscos
| Risco | Mitigação |
|---|---|
| Fidelidade do emulador (🟡) ser vendida como experiência AWS | README separa `FLOCI_LOCAL` × `AWS_REAL`; nada de alegar produção |
| Recurso do curso falhar no floci | o S2 descobre cedo; abrir issue/PR no floci (MIT) é bônus de portfólio |
| RAM/CPU (k3s + ArgoCD + Prometheus + apps) | subir por perfil; Prometheus com retenção curta; já houve gargalo de I/O nesta máquina |
| Imagem `latest` mudar o comportamento | fixar a versão do floci no compose e no CI |
| MCP de AWS apontar para a conta real por engano | perfil floci com credencial `test`; nenhuma chave real carregada no perfil de laboratório |

## 6. Próximo passo imediato
S0 → S1 → S2. Cerca de 3 horas e nenhum custo. Ao final temos a matriz real de compatibilidade e uma resposta definitiva sobre o que roda local.
