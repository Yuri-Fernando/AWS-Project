# MCP — o agente opera a plataforma como o instrutor opera a AWS no workshop

Os mesmos servidores MCP usados no curso (Dia 1 01:45–03:00, Dia 2 01:00–02:30), em três perfis:

| Servidor | `free.mcp.json` (floci) | `real.mcp.json` (AWS) | `agent-toolkit.mcp.json` |
|---|---|---|---|
| `terraform` (HashiCorp 1.4.1) | docs do registry | idem | — |
| **AWS MCP Server** gerenciado (via `mcp-proxy-for-aws-cli` 1.7.0) | vem do plugin `aws-core` (escopo de usuário) | `aws-mcp-readonly`: perfil `argus-lab-readonly`, `--read-only` | `--skip-auth`: só documentação e skills |
| `aws-api` (awslabs 1.6.0) | `AWS_ENDPOINT_URL` = floci, credencial fictícia | — (substituído pelo AWS MCP Server) | — |
| `eks` (awslabs 0.2.1) | cluster emulado (`--allow-write`, lab local) | somente leitura | — |

Em 10/11/2026 os antigos `aws-documentation-mcp-server` e `aws-api-mcp-server` saíram do perfil real: a AWS recomenda
o **AWS MCP Server** gerenciado (Agent Toolkit for AWS), que traz documentação, skills e chamadas à conta num servidor
só. O `aws-api` continua no perfil `free` porque é o único que aceita `AWS_ENDPOINT_URL` apontando para o floci.

## Guardrail no IAM
Toda chamada feita pelo AWS MCP Server leva a chave de condição `aws:ViaAWSMCPService = true`. A policy
`free-plan-guard` (stack `06-identity`, statement `NoCostlyCreatesViaAgent`) nega por essa chave a criação de EC2, NAT,
EIP, EKS, ELB, RDS, ElastiCache, OpenSearch, Redshift e MSK — mesmo que alguém configure o proxy sem `--read-only`.
Criar recursos na AWS real continua sendo papel do Terraform (`lab.py --target real`, role de deploy + MFA).

## Estado
| Perfil | Estado | Evidência |
|---|---|---|
| `agent-toolkit` | TESTADO (10/11/2026) | `tools/mcp_smoke.py agent-toolkit`: 8 ferramentas, `aws___search_documentation` ok |
| `free` | CONFIGURADO, validação parcial | ver `docs/floci-compat-matrix.md` (token do `eks-mcp-server` × webhook do floci) |
| `real` | CONFIGURADO, **bloqueado por configuração** | exige o perfil `argus-lab-readonly` em `~/.aws/config` (runbook, seção 2) |

## Ativar (exige aprovação — regra AIOX: configuração de MCP é do `@devops`)
```bash
python tools/mcp_profile.py free     # escreve .mcp.json na raiz (gitignored); o Claude Code pede confirmação ao abrir
python tools/mcp_profile.py real     # só depois de configurar o perfil AWS somente leitura
python tools/mcp_profile.py off      # remove .mcp.json
python tools/mcp_smoke.py <perfil>   # teste de fumaça stdio (initialize → tools/list → 1 chamada de leitura)
```
Teste esperado no perfil `free`: "liste as VPCs" e "liste os pods do namespace ecosystem" devolvem dados do floci.
