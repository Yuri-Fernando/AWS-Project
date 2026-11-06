# platform/ — AWS da plataforma Argus rodando local (floci), sem conta AWS

Infra do workshop **DevOps na Nuvem** (VPC → EKS → ECR → OIDC → WAF → observabilidade) reescrita como código próprio,
com **alvo duplo**: o mesmo Terraform aplica no emulador [floci](https://github.com/floci-io/floci) (padrão, R$ 0) ou na
AWS real (`--target aws`, opcional, exige `--yes-real-aws`). O ecossistema de apps (Argus, RetentIQ, ThemisAI, OmniMind,
Churn Intelligence, RiskCredit, Credit Score) roda no EKS emulado via Kustomize/GitOps.

## Pré-requisitos
Docker Desktop (≥ 4 CPU / 12 GB para a VM), Terraform ≥ 1.10, AWS CLI v2, kubectl, Helm, Python 3.10+. Nenhuma credencial real.

## Subir tudo (≈ 15–25 min na primeira vez)
```bash
python platform/lab.py floci-up                 # floci 2.4.0 em http://localhost.floci.io:4566 (UI em :4500)
python platform/lab.py up                       # stacks 00-backend … 05-monitoring (Terraform)
python platform/lab.py kubeconfig               # platform/.kube/floci.yaml (token IAM via webhook do EKS emulado)
export KUBECONFIG=platform/.kube/floci.yaml

helm upgrade --install argocd argo/argo-cd --version 10.13.1 -n argocd --create-namespace -f - < platform/k8s/argocd-values.yaml
helm upgrade --install monitoring prometheus-community/kube-prometheus-stack --version 92.21.1 -n monitoring --create-namespace \
     -f - --set-string grafana.adminPassword="$(cat platform/.kube/grafana-admin.txt)" < platform/k8s/monitoring-values.yaml

python platform/images/build.py                 # 7 imagens (contexto = clones dos repos em ECO_DIR) -> ECR emulado
python platform/lab.py deploy                   # gitops/overlays/floci + endpoint do floci + segredos de lab
python platform/serverless/package_creditscore.py   # pacote Lambda (≤ 50 MB) do Credit Score
python platform/e2e.py                          # 10 verificações de ponta a ponta
```
Derrubar: `python platform/lab.py down` (ordem reversa) e `python platform/lab.py floci-down`.
> `-f - < arquivo` no Helm: o `-f` aceita lista separada por vírgula e quebra caminhos que contêm vírgula.

## Estrutura
| Caminho | O quê |
|---|---|
| `floci/docker-compose.yml` | emulador fixado em 2.4.0; ECR estilo `path`; EKS/ECR sobrevivem a restart; host da Runtime API das Lambdas |
| `floci/spike.py` | aplica stacks de terceiros **sem editá-las** (override files) e gera matriz de compatibilidade |
| `terraform/_shared/` | provider com `var.aws_endpoint` (null = AWS real) + backend S3 por alvo (`use_lockfile`, sem DynamoDB) |
| `terraform/00…05` | backend · networking (reusa `repos/enterprise-automation/terraform/modules/networking`) · eks (`…/modules/eks`) · ci-cd OIDC (`…/modules/iam`) · WAF · AMP |
| `k8s/` | valores Helm de ArgoCD e kube-prometheus-stack (Grafana OSS substitui o Managed Grafana) |
| `images/` | Dockerfiles enxutos por app, `build.py` (build+push ECR), `smoke.py` (health local) |
| `serverless/` | empacotamento da Lambda v3 do Credit Score |
| `lab.py` · `e2e.py` | orquestrador (floci-up/up/plan/down/kubeconfig/deploy/status) e teste de ponta a ponta |

## Resultado verificado (06/11/2026, Windows 11 + Docker Desktop)
- IaC do curso no floci: dvn-workshop-maio 4/4 stacks; eks-express-iac 3/6 completas (detalhes em `docs/floci-compat-matrix.md`).
- Stacks próprias 00→05 aplicadas (5 + 23 + 27 + 4 + 1 recursos; AMP desligado automaticamente no emulador).
- 6 apps + 1 job no EKS emulado (k3s v1.33), ArgoCD e kube-prometheus-stack saudáveis.
- Credit Score serverless real no floci: Lambda (modelo v3) → resposta 200 com PD/faixa → registro no DynamoDB.
- `platform/e2e.py`: **10/10 verificações**.
- **Ainda não executado:** o workflow `.github/workflows/platform-floci.yml` no GitHub (depende de push) e qualquer `--target aws`.

## Limites honestos do emulador
Sem roteamento real de VPC/NAT, sem filtragem do WAF, sem ingestão/scraper/logging do AMP, sem Managed Grafana,
sem Karpenter, sem SageMaker Model Package Group, add-ons EKS restritos a 4. Experiência aqui é **FLOCI_LOCAL**, não AWS em produção.
