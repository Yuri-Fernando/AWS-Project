# Perfil `free` — AWS emulada no floci (padrão, R$ 0)

| Item | Valor |
|---|---|
| Alvo Terraform | `python platform/lab.py <cmd> --target free` (`var.aws_endpoint = http://localhost.floci.io:4566`) |
| Emulador | `platform/floci/docker-compose.yml` (floci 2.4.0, MIT) |
| State | S3 emulado `argus-platform-lab-tfstate` + `use_lockfile` (`platform/terraform/_shared/backend-floci.hcl`) |
| Credenciais | fictícias (`test`); kubectl via usuário IAM `lab-kube-admin` criado no emulador |
| Cluster | EKS emulado = k3s real (`platform/.kube/floci.yaml`) |
| Imagens | ECR emulado `localhost:4566/000000000000/us-east-1/argus-platform/*` |
| MCP | `mcp/free.mcp.json` (AWS API e EKS apontando para o floci; Terraform e docs AWS somente leitura) |
| Custo | zero; consome só CPU/RAM/disco local |

Fluxo: `floci-up → up → kubeconfig → (helm argocd/monitoring) → images/build.py → deploy → e2e.py → down`.
Limites do emulador: `docs/floci-compat-matrix.md`.
