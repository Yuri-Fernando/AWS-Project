# Guia de estudo — tudo o que fica FORA da AWS (e por que existe)

Este guia explica, peça por peça, o código e as decisões que **não são recursos da AWS** mas fazem a plataforma
funcionar: o orquestrador, o truque do "alvo duplo" no Terraform, o emulador, o gerador de GitOps, as imagens, o teste
de ponta a ponta, as evidências, o offload de dados, o MCP, os contratos e o CI. A ideia é que alguém consiga
**estudar, entender e replicar** sem precisar adivinhar nada. Os recursos AWS em si (VPC, EKS, IAM…) estão nas stacks
`platform/terraform/NN-*` e no relato [`AWS_REAL_SESSION.md`](AWS_REAL_SESSION.md).

> Convenção: `free` = AWS emulada (floci, R$ 0) · `real` = conta AWS de verdade. No código, `--target free|real`
> vira internamente `floci|aws`.

---

## 0. Mapa: o que é AWS e o que é "cola"

```text
                       ┌──────────────────────── você (terminal / Claude Code via MCP) ────────────────────────┐
                       │                                                                                        │
   ecosystem/repos.json ─► tools/repos.py ─► clones dos apps (ECO_DIR, fora do Google Drive)                     │
                       │                         │                                                              │
                       │                platform/images/build.py ──► imagens Docker ──► ECR (floci ou real)    │
                       │                                                                                        │
   platform/terraform/_shared/providers.tf ──(lab.py sync)──► 7 stacks NN-* ──(lab.py up/down)──► AWS (floci|real)
                       │                                                                                        │
   gitops/apps.json ──► gitops/gen.py ──► Kustomize base/overlays ──(lab.py deploy)──► EKS ──► pods            │
                       │                                                                                        │
   platform/e2e.py ──► 13 verificações (+ contracts/validate.py)      platform/evidence.py ──► PNGs mascarados  │
   tools/offload.py ──► dados para fora da AWS                        mcp/*.mcp.json + tools/mcp_* ──► agente   │
   .github/workflows/platform-floci.yml ──► o mesmo fluxo no GitHub Actions contra o floci                      │
                       └────────────────────────────────────────────────────────────────────────────────────────┘
```

**Regra de ouro do projeto:** o mesmo código serve aos dois alvos. Nada de "uma versão para o emulador e outra para a
nuvem". O que muda entre `free` e `real` é decidido em **um lugar só** (variável `aws_endpoint` e o `--target`).

---

## 1. Pré-requisitos e conceitos que você precisa saber antes

| Ferramenta | Versão usada | Para quê |
|---|---|---|
| Python | 3.10+ (stdlib na maioria dos scripts) | orquestração, gerador, testes |
| Terraform | 1.15.8 (mínimo 1.10 por causa do `use_lockfile`) | infraestrutura |
| Docker Desktop | 29.x (VM com ≥ 4 CPU / 12 GB para o lab completo) | emulador, k3s, builds |
| AWS CLI v2 | 2.39 | chamadas à AWS (emulada ou real) |
| kubectl / Helm | 1.36 / 4.3 | cluster, ArgoCD, monitoramento |
| uv/uvx | — | sobe os servidores MCP sem instalar nada globalmente |

Conceitos-chave (se algum for novo, estude antes):
- **Terraform state e backend**: onde o Terraform guarda "o que ele criou". Aqui: S3 emulado (free) ou **arquivo
  local** (real — regra de não guardar dados na AWS).
- **Override files do Terraform** (`*_override.tf`): arquivos que *mesclam* por cima dos `.tf` normais. Usados para
  trocar o backend sem editar a stack.
- **Kustomize**: base comum + overlays que só declaram diferenças (réplicas, imagem, patches).
- **EKS Pod Identity**: o pod recebe credenciais temporárias de uma role IAM ligada à sua ServiceAccount — sem chave.
- **MCP (Model Context Protocol)**: protocolo JSON-RPC 2.0 sobre stdio pelo qual um agente (Claude Code) chama
  ferramentas (AWS, Kubernetes, Terraform).

---

## 2. O emulador: `platform/floci/`

**O que é:** [floci](https://github.com/floci-io/floci) (MIT) é um emulador de AWS num único endpoint
(`:4566`). Diferente de mocks, ele sobe **containers reais** para EKS (um k3s), ECR (registry), Lambda e RDS — por
isso o compose monta o `docker.sock`.

**Arquivo `docker-compose.yml` — cada linha que importa:**

| Configuração | Por quê |
|---|---|
| `image: floci/floci:2.4.0` | versão fixa = reprodutível (nunca `latest`) |
| `/var/run/docker.sock` montado | o emulador cria os containers do k3s, ECR e Lambdas |
| `FLOCI_STORAGE_MODE: persistent` | o estado sobrevive a reinício do container |
| `FLOCI_SERVICES_ECR_URI_STYLE: path` | Windows/Docker Desktop não resolvem `*.localhost`; URIs viram `localhost:4566/<conta>/<região>/<repo>` |
| `*_KEEP_RUNNING_ON_SHUTDOWN` (EKS, ECR) | reiniciar o floci não derruba o cluster nem o registry |
| `FLOCI_SERVICES_LAMBDA_DOCKER_HOST_OVERRIDE: floci` | sem isso as Lambdas falham com "Failed to get next invocation" (autodetecção do host quebra no WSL2) |
| alias de rede `localhost.floci.io` | o mesmo nome funciona de dentro e de fora da rede Docker |

**`spike.py` (estudo de compatibilidade):** antes de escrever stacks próprias, ele aplicou stacks Terraform
*existentes, sem editá-las*, contra o floci: gera `zz_floci_override.tf` (provider + backend apontando para o
emulador), roda `init/apply`, registra PASS/FAIL por recurso e destrói em ordem reversa. O resultado está em
[`floci-compat-matrix.md`](floci-compat-matrix.md) — é a prova de quais serviços o emulador realmente suporta.

**Replicar:** `python platform/lab.py floci-up` (= `docker compose ... up -d --wait`). UI em `http://localhost:4500`.

---

## 3. O truque do "alvo duplo": `platform/terraform/_shared/providers.tf`

Este é o coração da reutilização. Um único `providers.tf` é copiado para as 7 stacks por `lab.py sync` (com um
cabeçalho "GERADO — edite o original"). Ele faz três coisas:

**3.1 Endpoint nulo = AWS real.**
```hcl
variable "aws_endpoint" { type = string, default = null }
locals { is_emulator = var.aws_endpoint != null }
provider "aws" {
  access_key = local.is_emulator ? "test" : null      # null = "não definido" = cadeia padrão da AWS
  endpoints { ec2 = var.aws_endpoint ... }           # null em todos = endpoints reais
}
```
Em Terraform, um argumento `null` é tratado como "não informado". Então, sem `aws_endpoint`, o mesmo provider fala com
a AWS de verdade, usando o perfil do ambiente. Com `aws_endpoint = http://localhost.floci.io:4566`, tudo vai para o
emulador com credencial fictícia `test`.

**3.2 `emulator_backend` e o truque `for ... if`.** Quando uma stack lê saídas de outra (`terraform_remote_state`),
no emulador o backend S3 precisa de credenciais fictícias e `use_path_style`. O código faz:
```hcl
config = merge({ bucket = ..., key = "01-networking.tfstate" },
               [for c in [local.emulator_backend] : c if local.is_emulator]...)
```
Um `condicional ? objeto : {}` daria erro de "tipos inconsistentes"; a lista filtrada + `...` (expansão) mescla o
objeto só quando é emulador.

**3.3 `local_state_dir` (adicionado para a AWS real).** Como na conta real o state é local, as stacks que leem
outras (02 lê 01; 03 e 06 leem 02) ganharam um segundo `terraform_remote_state` com `backend = "local"`, ativado
quando `local_state_dir != null`. Um `locals { network = var.local_state_dir == null ? s3[0] : local[0] }` escolhe a
fonte. Assim o floci continua igual e a AWS real não precisa de bucket.

**Tags padrão** (`default_tags`): `Project`, `Environment`, `ManagedBy`, `Owner`, `CostCenter`, `Target` — é por
elas que se prova, depois do desmonte, que não sobrou nada do projeto.

---

## 4. O orquestrador: `platform/lab.py`

Um único CLI (stdlib) para os dois alvos. Comandos:

| Comando | O que faz |
|---|---|
| `floci-up` / `floci-down` | sobe/derruba o emulador |
| `sync` | copia `_shared/providers.tf` para as 7 stacks |
| `plan` / `up` / `down` | `terraform plan/apply/destroy` nas stacks (`--stacks a,b` filtra; `down` vai em ordem reversa) |
| `kubeconfig` | gera `platform/.kube/<alvo>.yaml` |
| `deploy` | aplica o GitOps no cluster |
| `status` | mostra os outputs de cada stack |

**Proteções:** `--target real` com `up`/`down` exige `--yes-real-aws`; o padrão é sempre `free`.

**Como ele prepara cada `terraform` (função `tf_env`):**
- `TF_DATA_DIR` por stack e alvo em `D:\Claude Temp\cache\tfdata\<stack>-<alvo>` e `TF_PLUGIN_CACHE_DIR` compartilhado:
  os `.terraform/` (centenas de MB de providers) ficam **fora** da pasta sincronizada pelo Google Drive.
- No floci: injeta `AWS_ACCESS_KEY_ID=test`, `AWS_ENDPOINT_URL=...`.
- Na AWS real: `AWS_PROFILE=argus-lab` por padrão.
- **Correção de Windows:** `os.environ` devolve as chaves em MAIÚSCULAS; o Terraform casa `TF_VAR_<nome>` com o nome
  exato da variável. O script renomeia `TF_VAR_X` → `TF_VAR_x`. Sem isso, `TF_VAR_enable_workload_identity=false` era
  ignorado em silêncio (foi um bug real desta sessão).

**Como ele escolhe o backend (função `init`):**
```text
00-backend ............ state LOCAL em platform/.state/00-backend-<alvo>.tfstate   (o "ovo e galinha": cria o bucket)
floci, demais stacks .. backend S3 emulado (_shared/backend-floci.hcl) com key=<stack>.tfstate e use_lockfile
real, demais stacks ... gera backend_override.tf  (terraform { backend "local" {} })  e grava em
                        platform/.state/<stack>-aws.tfstate   → nada salvo na AWS; 00-backend é pulada
```
O `backend_override.tf` é apagado automaticamente quando você volta a rodar contra o floci.

**Variáveis por alvo (`tf_vars`):** floci recebe `-var=aws_endpoint=...`; real recebe `-var=local_state_dir=...` e
`-var-file=envs/real/real.auto.tfvars` (gitignored: e-mail do budget, `enable_workload_identity`, `node_group`).

**`kubeconfig`:** chama `aws eks update-kubeconfig`. Na AWS real grava `--profile` dentro do `exec` do kubeconfig. No
floci há um detalhe: o webhook de autenticação do EKS emulado só aceita tokens assinados por uma access key que
**exista** no IAM do floci — então o script cria o usuário `lab-kube-admin`, gera a chave e injeta no `exec` (arquivo
gitignored).

**`deploy`:** roda `gitops/gen.py`, depois:
- floci: `kubectl apply -k gitops/overlays/floci`, sobrescreve o ConfigMap `platform-env` com o IP do floci na rede
  Docker, cria o Secret de laboratório (`JWT_SECRET` aleatório, nunca versionado) e reinicia os deployments;
- real: `kubectl kustomize gitops/overlays/aws` → troca `ACCOUNT_ID` pelo ID real **só em memória** → `kubectl apply -f -`.
  O ID da conta nunca é escrito em arquivo.

---

## 5. As stacks e os módulos reaproveitados

| Stack | Cria | Observação |
|---|---|---|
| `00-backend` | bucket S3 do state (versionado, criptografado, público bloqueado) | só no floci; na real é pulada |
| `01-networking` | VPC 3 AZ, subnets públicas/privadas, IGW, NAT opcional, flow logs | NAT desligado por padrão (custo) |
| `02-eks` | cluster, node group, add-ons, OIDC, 7 repositórios ECR | sem NAT → nós em subnet pública |
| `03-ci-cd` | OIDC do GitHub + role com push no ECR | trust restrito a repo/branch |
| `04-security` | guardrails de segurança | |
| `05-monitoring` | AMP (workspace + regras) quando habilitado | |
| `06-identity` | `free-plan-guard`, roles `deployer`/`mcp-readonly` (MFA), budgets, Pod Identity por app | ver `docs/IAM_ROLES.md` |

Os módulos (`networking`, `eks`, `iam`, `budget`, `monitoring`…) vêm do submódulo
`repos/enterprise-automation` (repositório
[enterprise-cloud-automation-platform](https://github.com/Yuri-Fernando/enterprise-cloud-automation-platform),
branch `feat/floci-local-platform`). O master **consome** os módulos; não os duplica.

---

## 6. Os repositórios do ecossistema: `ecosystem/repos.json` + `tools/repos.py`

O master não copia o código dos apps; ele **referencia** cada repositório num commit fixado (`ref`), como um lockfile.

| Campo | Significado |
|---|---|
| `how` | `submodule` (módulos Terraform), `image` (vira container) ou `job` |
| `ref` | commit exato usado no build (reprodutível) |
| `context` | subpasta do build (ex.: `apps/api` no RetentIQ) |
| `produces` / `consumes` | contratos de dados entre os repos |

`tools/repos.py`:
- `status`: compara `ref` fixado × HEAD local × presença em `ECO_DIR`;
- `sync`: clona/atualiza cada repo no `ref` dentro de `ECO_DIR` (`D:\Claude Temp\staging\eco`) — **fora** do Google
  Drive, porque builds geram milhares de arquivos pequenos que travam a sincronização. Fonte do clone: pasta irmã local
  (inclui commits não enviados) ou o GitHub;
- `pin`: grava o HEAD atual como novo `ref`.

---

## 7. As imagens: `platform/images/`

Cada app tem um `Dockerfile` **neste repositório** (os repositórios dos apps não são alterados). Padrão comum:

```dockerfile
FROM python:3.10-slim
RUN pip install $(grep -iE '^(pandas|numpy|scikit-learn|...)([<>=~!\[ ]|$)' requirements.txt | tr '\n' ' ')
RUN useradd -u 10001 -m app && chown -R app /app
USER app
HEALTHCHECK ... urllib.request.urlopen('http://localhost:8000/health')
```
- **`grep` no `requirements.txt`**: instala só os pacotes do caminho de serving, **com as versões fixadas pelo repo
  original** — essencial para o `.pkl` do modelo carregar (pickle quebra com versão diferente de scikit-learn).
- **UID 10001 não-root**: casa com o `securityContext` gerado pelo `gen.py` (`runAsNonRoot`).
- **`--build-context platform=...`** (BuildKit): permite que o Dockerfile copie arquivos daqui (ex.: `publish.py`)
  enquanto o contexto principal é o clone do app.

`build.py`: para cada imagem, `docker build` com duas tags — `<sha curto do app>` (rastreável) e `lab` (a que os
manifests usam) — e label OCI `revision`. Alvo `floci`: registry `localhost:4566/000000000000/us-east-1`. Alvo `aws`:
descobre a conta via `sts get-caller-identity` e usa `<conta>.dkr.ecr.us-east-1.amazonaws.com`. `--no-push` constrói
sem enviar (útil para construir antes de o cluster existir e não pagar por hora esperando build).

Peças especiais:
- `riskcredit-train/publish.py`: depois do treino, sobe `artifacts/champion/` para o S3 com um **manifesto sha256 por
  arquivo** e grava o ponteiro `riskcredit/champion/LATEST`. É o elo MLOps RiskCredit → Credit Score (contrato
  `model_manifest.v1`). Credenciais: no floci vêm do ConfigMap; na AWS real, do **Pod Identity** (boto3 acha sozinho).
- `creditscore-app/entrypoint.py`: o Streamlit original tem a URL da API de produção fixa no código; o entrypoint troca
  por `CREDITSCORE_API_URL` com uma regex em tempo de execução e sobe o Streamlit — sem editar o repositório do app.
- `smoke.py`: sobe cada container localmente e espera o healthcheck — pega imagem quebrada antes do cluster.

---

## 8. O GitOps: `gitops/apps.json` + `gitops/gen.py`

Em vez de escrever 40 YAMLs à mão, um **spec** (`apps.json`) descreve cada app (porta, health, CPU/memória, envs,
segredos) e o `gen.py` gera os manifests. Isso garante que todos sigam os mesmos padrões.

O que é gerado por app:
```text
gitops/apps/<app>/base/        deployment.yaml (probes readiness/liveness, requests/limits, securityContext
                               não-root + seccomp RuntimeDefault + drop ALL), service.yaml, pdb.yaml (maxUnavailable 1)
gitops/apps/<app>/overlays/floci/   1 réplica, imagem do ECR emulado
gitops/apps/<app>/overlays/aws/     2 réplicas, imagem ACCOUNT_ID.dkr.ecr..., serviceaccount.yaml + patch JSON
                                    serviceAccountName: <app>   (para o EKS Pod Identity)
gitops/env/<alvo>/             namespace + ConfigMap platform-env (floci: endpoint e chaves fictícias; aws: só região)
gitops/overlays/<alvo>/        "app-of-apps": inclui env + todos os overlays (um kubectl apply -k sobe tudo)
gitops/argocd/                 ApplicationSet (uma Application por app) para quando o ArgoCD sincronizar do GitHub
```
Detalhes que valem estudo:
- Probes: se `health` é `null` (OmniMind), usa `tcpSocket` em vez de `httpGet`.
- Segredos: entram como `secretKeyRef` para `<app>-secrets` — o valor é criado no cluster pelo `deploy`, nunca no git.
- O CI verifica que o que está commitado é exatamente o que o `gen.py` gera (`git diff --exit-code`).

---

## 9. Contratos de dados: `contracts/`

Três JSON Schemas (draft 2020-12) definem o que um repositório entrega ao outro:

| Contrato | Produtor → Consumidor |
|---|---|
| `scoring_result.v1` | Churn (`/predict`) e Credit Score (Lambda) → OmniMind/dashboards (`anyOf`: formato churn ou crédito) |
| `model_manifest.v1` | RiskCredit (job) → Credit Score (serving) |
| `customer_activity.v1` | RetentIQ → Argus (definido; fluxo ainda não implementado) |

`validate.py` usa `jsonschema` se existir; senão, um **validador mínimo próprio** (type, required, properties, enum,
min/max, pattern, items, anyOf…) — suficiente para esses schemas e sem dependência. O e2e chama
`validate("scoring_result.v1", resposta)` em respostas reais.

---

## 10. O serverless: `platform/serverless/package_creditscore.py`

Monta o zip da Lambda v3 do Credit Score respeitando o limite de **50 MB por upload direto**:
1. `pip install --platform manylinux2014_x86_64 --python-version 3.11 --only-binary=:all:` — baixa wheels **Linux**
   mesmo rodando no Windows (cross-install), porque a Lambda roda em Amazon Linux;
2. `xgboost-cpu` com `--no-deps` (evita puxar dependências de GPU);
3. remove submódulos do SciPy não usados, `tests/`, `*.dist-info`, `__pycache__`, stubs `.pyi` — mas preserva
   `numpy/_core/tests` (o `numpy.testing` importa de lá; removê-lo quebra o import);
4. copia `Nuvem/`, `src/` e `model_artifacts/riskcredit-v3/` e zipa. Resultado medido: **49 MB**.

---

## 11. O teste de ponta a ponta: `platform/e2e.py`

13 verificações, mesmo script para os dois alvos (`--target floci|aws`):
1. **health** de cada um dos 6 serviços via `kubectl port-forward` em porta livre (`free_port()` abre um socket na
   porta 0 para o SO escolher) — testa o caminho real Service → Pod;
2. **predição** do churn + validação do contrato;
3. **S3**: lê `riskcredit/champion/LATEST`, baixa o manifesto e conta arquivos com sha256 + valida o contrato;
4. **Lambda**: invoca com um evento no formato API Gateway HTTP v2 (`routeKey`, `requestContext.http`) e confere
   `statusCode 200`, `pd` e o contrato;
5. **DynamoDB**: conta itens antes/depois da invocação — prova a persistência.
Saída: `platform/.state/e2e-<alvo>.json` e código de saída ≠ 0 se algo falhar (serve para CI).

---

## 12. As evidências: `platform/evidence.py`

Playwright (Chromium headless) tira screenshots com o cluster aberto via port-forward: Grafana (login automático com a
senha lida do Secret do cluster **em memória**), Prometheus, Streamlit, Swagger e ArgoCD. No alvo `aws` gera também o
painel `aws-inventory.png`: monta um HTML com saídas reais da AWS CLI/kubectl e aplica máscaras por regex antes de
renderizar:
```python
re.sub(r"\b\d{12}\b", "<conta>", out)                               # ID da conta
re.sub(r"\bA(IDA|ROA|SIA|KIA)[A-Z0-9]{12,}\b", "<id-iam>", out)     # IDs IAM e chaves
re.sub(r"\b(?!10\.)\d{1,3}(\.\d{1,3}){3}\b", "<ip-publico>", out)   # IPs públicos (privados 10.x ficam)
```
As imagens vão para `docs/evidence/aws/` (separadas das do floci).

---

## 13. Dados fora da AWS: `tools/offload.py`

No Free Plan, quando a conta é suspensa, os dados somem após 90 dias. Por isso nada importante fica só na AWS:
`offload.py --target real` lista os buckets do projeto (`argus-platform-lab*`, `credit-score-*`) e faz `aws s3 sync`
para `D:\argus-data\<alvo>\<data>`; exporta as tabelas DynamoDB do projeto em JSONL. Com `--r2`, envia também para o
Cloudflare R2 (credenciais no cofre local; sem elas o passo fica `BLOCKED_BY_CONFIGURATION`). Roda **antes** de
qualquer `destroy`.

---

## 14. O agente: MCP (`mcp/`, `tools/mcp_*.py`)

| Arquivo | Papel |
|---|---|
| `mcp/free.mcp.json` | servidores apontando para o floci (`aws-api` com `AWS_ENDPOINT_URL`, `eks`, `terraform`) |
| `mcp/real.mcp.json` | AWS MCP Server gerenciado (proxy SigV4), `eks-mcp-server`, `terraform-mcp-server` — perfil `argus-lab-mcp` |
| `mcp/agent-toolkit.mcp.json` | só documentação e skills da AWS (`--skip-auth`) |
| `tools/mcp_profile.py` | copia o perfil escolhido para `.mcp.json` (gitignored) ou remove |
| `tools/mcp_smoke.py` | teste de fumaça: sobe cada servidor, `initialize` → `tools/list` → **uma** chamada de leitura |
| `tools/mcp_session.py` | resolve o MFA: assume a role somente leitura e grava credenciais de 1 h no perfil `argus-lab-mcp` |

Como o `mcp_smoke.py` fala o protocolo (vale estudar — é MCP "na unha"):
```text
processo filho (stdin/stdout) ── JSON-RPC 2.0, uma mensagem por linha
→ {"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18",...}}
← {"id":1,"result":{"serverInfo":{"name":"MCP Proxy for AWS","version":"1.7.0"}}}
→ {"method":"notifications/initialized"}                (notificação: sem id, sem resposta)
→ {"id":2,"method":"tools/list"}        ← lista de ferramentas
→ {"id":3,"method":"tools/call","params":{"name":"aws___run_script","arguments":{...}}}
```
Uma thread lê o stdout e põe as respostas numa fila; `request()` espera o `id` certo com timeout.

Segurança (duas camadas): a role do MCP tem `ReadOnlyAccess` e a policy `free-plan-guard` nega criações caras quando
`aws:ViaAWSMCPService = true`. Achado medido: a flag `--read-only` do proxy esconde o `aws___run_script` — então o
perfil real **não** a usa e confia no IAM.

---

## 15. O CI: `.github/workflows/platform-floci.yml`

O mesmo fluxo do laboratório no GitHub Actions, **sem conta AWS e sem segredo**: o floci roda como *service container*
(com o `docker.sock` do runner, para o k3s subir). Passos: `terraform fmt -check` → `gen.py` + `git diff --exit-code`
(GitOps commitado = gerado) → `lab.py sync` + diff (providers sincronizados) → `up` das stacks no floci →
`kubectl get nodes` no EKS emulado → diagnóstico em falha (logs do floci e do k3s) → `down` sempre → se o `down`
falhar, lista o que segura a VPC (SGs, ENIs, subnets, rotas, IGW, endpoints, NAT). Estado em 12/11/2026: **verde**.
Detalhe que já quebrou o workflow: o contexto `runner` **não existe** no `env` do job (`${{ runner.temp }}` faz o
GitHub rejeitar o arquivo) — por isso `LAB_CACHE_DIR: /tmp/lab-cache`.

---

## 16. O que nunca vai para o git (e por quê) — `.gitignore`

| Ignorado | Motivo |
|---|---|
| `platform/.state/`, `*.tfstate*` | state contém IDs e às vezes valores sensíveis |
| `platform/.kube/` | kubeconfig e chave IAM do emulador, senha do Grafana |
| `envs/real/*.auto.tfvars`, `envs/real/backend.hcl` | e-mail, configuração da conta real |
| `*_override.tf` | gerados pelo `lab.py` |
| `.mcp.json`, `.claude/settings.local.json` | configuração local do agente |
| `_private/`, `*.msi`, `.env*`, `*.pem`, `*.key` | material pessoal, instaladores, segredos |

Antes de publicar, o histórico inteiro foi varrido por padrões de segredo (chaves AWS, tokens GitHub/OpenAI/Supabase,
JWT, URIs com senha, chaves privadas, ID da conta real, e-mail pessoal) — sem achados reais.

---

## 17. Replicar do zero (roteiro de estudo)

```bash
# 1) Emulador e repositórios
git clone --recurse-submodules https://github.com/Yuri-Fernando/AWS-Project.git && cd AWS-Project
python tools/repos.py sync                       # clones dos apps no commit fixado (ECO_DIR)
python platform/lab.py floci-up

# 2) Infraestrutura emulada (R$ 0)
python platform/lab.py up                        # 00 -> 06 no floci
python platform/lab.py kubeconfig && export KUBECONFIG=platform/.kube/floci.yaml

# 3) Plataforma no cluster
helm upgrade --install argocd argo/argo-cd --version 10.13.1 -n argocd --create-namespace -f - < platform/k8s/argocd-values.yaml
helm upgrade --install monitoring prometheus-community/kube-prometheus-stack --version 92.21.1 -n monitoring --create-namespace -f - < platform/k8s/monitoring-values.yaml

# 4) Apps, serverless e validação
python platform/images/build.py                  # 7 imagens -> ECR emulado
python platform/lab.py deploy
python platform/serverless/package_creditscore.py
python platform/e2e.py                           # 13/13
python platform/evidence.py

# 5) AWS real (opcional, Free Plan): ver docs/AWS_REAL_SESSION.md, seção 8
python platform/lab.py down && python platform/lab.py floci-down
```

**Exercícios sugeridos (para fixar):**
1. Mude `replicas` do overlay `aws` no `gen.py`, regenere e veja o diff — entenda por que o CI exige `git diff` limpo.
2. Rode `python platform/lab.py plan --target free --stacks 01-networking` com e sem `-var=aws_endpoint` e compare.
3. Remova `numpy/_core/tests` do zip da Lambda e veja o import quebrar — entenda por que a exceção existe.
4. Rode `python tools/mcp_smoke.py agent-toolkit` e leia o JSON-RPC trocado.
5. Faça uma predição no churn e valide a resposta com `python contracts/validate.py scoring_result.v1 resposta.json`.

---

## 18. Problemas reais encontrados (e a lição de cada um)

| Problema | Lição |
|---|---|
| `TF_VAR_*` ignorado no Windows | ambiente do Python em Windows normaliza para maiúsculas; o Terraform é sensível a maiúsculas |
| Node group parado no Free Plan | contas Free Plan só lançam tipos `free-tier-eligible`; consulte antes com `describe-instance-types` |
| KMS × CloudWatch Logs | log group criptografado exige key policy liberando `logs.<região>.amazonaws.com` |
| Concorrência da Lambda | conta nova tem limite 10 e a AWS exige 10 não reservadas |
| `--read-only` no MCP | esconde a ferramenta que lê a conta; a barreira certa é o IAM |
| Workflow rejeitado | `runner` não existe no `env` do job |
| `DeleteVpc` → `DependencyViolation` só no emulador | o EKS emulado deixa o security group `eks-cluster-sg-*` na VPC (a AWS real remove); `lab.py` apaga ENIs/SGs não gerenciados antes do destroy da rede (`floci_vpc_orphans`) — causa confirmada pelo diagnóstico do CI |
| Placeholder no budget | conferir valores no state depois do apply, não só o "Apply complete" |
| `npm`/builds no Google Drive | milhares de arquivos pequenos travam a sincronização: builds e caches ficam fora (D:) |

## 19. Glossário rápido

**Alvo duplo** — mesmo Terraform para emulador e nuvem. **Backend** — onde o state fica. **Override file** — `.tf`
que mescla por cima. **Overlay** — diferenças por ambiente no Kustomize. **Pod Identity** — credencial de IAM por
ServiceAccount, sem chave. **Free Plan** — plano gratuito da AWS (créditos, 6 meses, suspende em vez de cobrar).
**Offload** — copiar dados para fora antes de destruir. **Contrato** — schema que define a interface entre repos.
**MCP** — protocolo de ferramentas para agentes (JSON-RPC 2.0).

---

## 20. GitOps de verdade: ArgoCD puxando do GitHub (`lab.py argocd`)

Até a sessão 1 o deploy era **push** (`kubectl apply` a partir da sua máquina). Em GitOps de verdade o cluster
**puxa** o estado desejado do repositório e o reconcilia sozinho. Como foi feito:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet            # um "gerador" de Applications: uma por item da lista
spec:
  goTemplate: true
  generators: [{list: {elements: [{app: argus-api}, {app: churn-api}, ...]}}]
  template:
    metadata: {name: '{{.app}}'}
    spec:
      source:
        repoURL: https://github.com/Yuri-Fernando/AWS-Project.git
        targetRevision: main
        path: 'gitops/apps/{{.app}}/overlays/aws'
        kustomize:
          images: ['{{.app}}=<conta>.dkr.ecr.us-east-1.amazonaws.com/argus-platform/{{.app}}:lab']
      syncPolicy: {automated: {prune: true, selfHeal: true}, syncOptions: [CreateNamespace=true]}
```
- **`automated` + `prune` + `selfHeal`**: o que muda no git é aplicado; o que some do git é removido; alteração manual no
  cluster é desfeita.
- **O problema do ID da conta:** o overlay `aws` no git usa `ACCOUNT_ID` (o ID não é versionado). O `lab.py` gera o
  ApplicationSet **em memória** com `kustomize.images`, que o ArgoCD aplica como `kustomize edit set image` — a imagem
  correta chega ao cluster sem o ID ir para o repositório.
- **Segredos** continuam fora do git: o `lab.py` cria o Secret no cluster antes de ligar o ArgoCD.
- Um `Application` separado (`platform-env-aws`) aplica `gitops/env/aws` (namespace + ConfigMap).

## 21. Entrada pública: Ingress → ALB com HTTPS

Peças, de baixo para cima:
1. **Tags nas subnets** (`01-networking`, `aws_ec2_tag`): `kubernetes.io/role/elb=1` diz ao controller onde criar um
   ALB público.
2. **AWS Load Balancer Controller** (Helm 3.6.2, `lab.py addons`): um operador no cluster que observa objetos `Ingress`
   e cria/atualiza ALB, listeners, regras e target groups. Ele precisa de permissão na AWS → role com a **policy
   oficial** daquela versão, entregue por **Pod Identity** (`06-identity`).
3. **Certificado** (`02-eks`): sem domínio próprio, um certificado público válido é impossível; o provider `tls` gera
   chave + certificado **autoassinado** `*.argus.lab` e o `aws_acm_certificate` o importa. Criptografia real; o
   navegador avisa que a cadeia não é confiável.
4. **Ingress** (gerado pelo `gen.py`, overlay `aws`):
   ```yaml
   alb.ingress.kubernetes.io/group.name: argus        # vários Ingress → UM ALB (custo)
   alb.ingress.kubernetes.io/listen-ports: '[{"HTTP": 80}, {"HTTPS": 443}]'
   alb.ingress.kubernetes.io/ssl-redirect: "443"      # HTTP responde 301 para HTTPS
   alb.ingress.kubernetes.io/ssl-policy: ELBSecurityPolicy-TLS13-1-2-2021-06
   alb.ingress.kubernetes.io/target-type: ip          # ALB fala direto com o IP do pod (VPC CNI)
   spec.tls: [{hosts: [creditscore.argus.lab]}]        # o controller acha o certificado no ACM por este host
   ```
5. **Testar sem DNS:** os hosts `*.argus.lab` não existem na internet. O e2e conecta no DNS do ALB e manda o cabeçalho
   `Host:`; as evidências usam `--host-resolver-rules="MAP *.argus.lab <ip-do-alb>"` no Chromium.

**A armadilha do desmonte (aconteceu de verdade):** o ALB é criado pelo controller, não pelo Terraform. Se o EKS for
destruído antes, o ALB fica órfão — continua cobrando e impede apagar a VPC. E se o Pod Identity for desligado antes de
apagar o Ingress, o controller perde a credencial e não consegue apagar o ALB (o Ingress trava no *finalizer*). Por
isso o `lab.py` (`release_k8s_cloud_resources`) apaga Applications e Ingress e **espera o ALB sumir** antes de
desligar o Pod Identity ou destruir o EKS — e aborta se o ALB não sumir em 10 min. Depois do ALB, ele também apaga os security groups do
controller (`k8s-traffic-<cluster>`), que sobravam e prendiam o `DeleteVpc`.

## 22. Registro do que existiu na nuvem

| Ferramenta | Quando roda | O que grava |
|---|---|---|
| `tools/real_snapshot.py` | com a sessão **no ar** | `docs/aws-real/sessao-AAAA-MM-DD/`: EKS, node group, add-ons, Pod Identity, nós, pods, Ingress, Helm, ArgoCD, ALB (listeners, target groups, saúde), certificado (metadados), Lambda, DynamoDB, API Gateway, plano e budgets |
| `tools/real_inventory.py` | **depois** do destroy | `docs/aws-real/INVENTARIO.md`: cada recurso Terraform com sua configuração, lido do `.tfstate.backup` (o snapshot que o Terraform grava imediatamente antes de destruir) |

As duas mascaram ID da conta, IDs IAM, e-mails e IPs públicos e não leem segredos. Com elas, dá para responder "o que
exatamente rodou na AWS?" sem nenhum acesso à conta.
