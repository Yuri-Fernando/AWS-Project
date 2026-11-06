# MCP — o agente opera a plataforma como o instrutor opera a AWS no workshop

Os mesmos servidores MCP usados no curso (Dia 1 01:45–03:00, Dia 2 01:00–02:30), em dois perfis:

| Servidor | `free.mcp.json` (floci) | `real.mcp.json` (AWS) |
|---|---|---|
| `terraform` (HashiCorp) | docs do registry | idem |
| `aws-docs` (awslabs) | documentação AWS | idem |
| `aws-api` (awslabs) | `AWS_ENDPOINT_URL` = floci, credencial fictícia | perfil `argus-lab-readonly`, `READ_OPERATIONS_ONLY=true` |
| `eks` (awslabs) | cluster emulado (`--allow-write`, lab local) | somente leitura |

**Estado:** CONFIGURADO como modelo, **não testado**. Pendências de validação: (1) o `aws-api-mcp-server` respeitar
`AWS_ENDPOINT_URL`; (2) o `eks-mcp-server` gerar token aceito pelo webhook do floci (exige access key existente no IAM
emulado — ver `docs/floci-compat-matrix.md`); (3) fixar versões em vez de `@latest` após validar.

## Ativar (exige aprovação — regra AIOX: configuração de MCP é do `@devops`)
```bash
python tools/mcp_profile.py free     # escreve .mcp.json na raiz (gitignored); o Claude Code pede confirmação ao abrir
python tools/mcp_profile.py real     # só depois de configurar o perfil AWS somente leitura
python tools/mcp_profile.py off      # remove .mcp.json
```
Teste esperado no perfil `free`: "liste as VPCs" e "liste os pods do namespace ecosystem" devolvem dados do floci.
