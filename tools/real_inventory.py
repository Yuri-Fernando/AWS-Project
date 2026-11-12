#!/usr/bin/env python
"""Inventário do que EXISTIU na AWS real, lido dos states locais do Terraform (inclusive os .backup de antes do destroy).

  python tools/real_inventory.py [--out docs/aws-real/INVENTARIO.md]

Por quê: depois do desmonte a conta fica vazia — este registro permite saber, sem acesso à nuvem, exatamente quais
recursos foram criados, com quais configurações. Para cada stack usa o snapshot mais completo disponível (o state
atual ou o .backup gravado imediatamente antes do destroy). Mascara ID da conta, IDs únicos IAM, e-mails e IPs
públicos; nunca copia atributos sensíveis (senhas, tokens, chaves).
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "platform" / ".state"
STACKS = {
    "06-identity-aws": "R0 — identidade, guardrails de custo e Pod Identity (`platform/terraform/06-identity`)",
    "01-networking-aws": "R1 — rede (`platform/terraform/01-networking`)",
    "02-eks-aws": "R2 — EKS e ECR (`platform/terraform/02-eks`)",
    "r4-creditscore-aws": "R4 — Credit Score serverless (repo `meu-projeto-aws/infra/terraform`)",
}
# atributos úteis para entender o recurso (whitelist: nada fora daqui é copiado)
KEEP = ["name", "function_name", "bucket", "cluster_name", "node_group_name", "addon_name", "addon_version",
        "repository_name", "role", "policy_arn", "cidr_block", "availability_zone", "map_public_ip_on_launch",
        "version", "platform_version", "instance_types", "capacity_type", "ami_type", "disk_size", "scaling_config",
        "runtime", "handler", "memory_size", "timeout", "reserved_concurrent_executions", "billing_mode", "hash_key",
        "range_key", "protocol_type", "route_key", "stage_name", "retention_in_days", "limit_amount", "limit_unit",
        "time_unit", "budget_type", "enable_key_rotation", "deletion_window_in_days", "image_tag_mutability",
        "scan_on_push", "namespace", "service_account", "max_session_duration", "description", "alias", "status",
        "traffic_type", "log_destination_type", "comparison_operator", "threshold", "metric_name", "dashboard_name",
        "mfa_configuration", "image_scanning_configuration", "point_in_time_recovery", "vpc_config", "tags"]
SENSITIVE = re.compile(r"(?i)(password|secret|token|private|certificate_authority|kubeconfig|policy_document)")


def mask(text: str) -> str:
    text = re.sub(r"\b\d{12}\b", "<conta>", text)
    text = re.sub(r"\bA(IDA|ROA|SIA|KIA)[A-Z0-9]{12,}\b", "<id-iam>", text)
    text = re.sub(r"[\w.+-]+@[\w-]+\.[\w.]+", "<email>", text)
    return re.sub(r"\b(?!10\.)\d{1,3}(\.\d{1,3}){3}\b", "<ip-publico>", text)


def compact(v) -> str:
    if isinstance(v, (dict, list)):
        v = json.dumps(v, ensure_ascii=False, separators=(",", ":"))
    s = str(v)
    return s if len(s) <= 120 else s[:117] + "…"


def snapshot(stack: str) -> tuple[dict, str]:
    """Escolhe o arquivo com MAIS recursos entre o state atual e o .backup (pré-destroy)."""
    best, src = {"resources": []}, ""
    for f in (STATE / f"{stack}.tfstate", STATE / f"{stack}.tfstate.backup"):
        if f.exists():
            d = json.loads(f.read_text(encoding="utf-8"))
            n = sum(len(r.get("instances", [])) for r in d.get("resources", []) if r.get("mode") == "managed")
            if n > sum(len(r.get("instances", [])) for r in best.get("resources", []) if r.get("mode") == "managed"):
                best, src = d, f.name
    return best, src


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "docs" / "aws-real" / "INVENTARIO.md"))
    a = ap.parse_args()
    lines = ["# Inventário dos recursos que existiram na AWS real", "",
             f"Gerado por `tools/real_inventory.py` em {datetime.now():%Y-%m-%d} a partir dos states locais do Terraform "
             "(snapshot de antes do `destroy`). ID da conta, IDs IAM, e-mails e IPs públicos mascarados; atributos "
             "sensíveis nunca são copiados. Todos estes recursos foram **destruídos** em 11/11/2026, exceto a R0 "
             "(roles, policy e budgets, sem custo).", ""]
    total = 0
    summary = []
    body: list[str] = []
    for stack, title in STACKS.items():
        d, src = snapshot(stack)
        res = [r for r in d.get("resources", []) if r.get("mode") == "managed"]
        n = sum(len(r.get("instances", [])) for r in res)
        total += n
        summary.append(f"| {title} | {n} | `{src or '—'}` |")
        body += ["", f"## {title}", "", f"Fonte: `platform/.state/{src}` · {n} recursos", "",
                 "| Recurso (endereço Terraform) | Tipo | Configuração relevante |", "|---|---|---|"]
        for r in sorted(res, key=lambda r: (r.get("module", ""), r["type"], r["name"])):
            for inst in r.get("instances", []):
                addr = ".".join(x for x in [r.get("module", ""), r["type"], r["name"]] if x)
                if "index_key" in inst:
                    addr += f"[{json.dumps(inst['index_key'])}]"
                attrs = inst.get("attributes", {})
                kv = [f"`{k}`={compact(attrs[k])}" for k in KEEP
                      if k in attrs and attrs[k] not in (None, "", [], {}) and not SENSITIVE.search(k)]
                body.append(f"| `{mask(addr)}` | `{r['type']}` | {mask(' · '.join(kv)).replace('|', '/')} |")
    lines += ["| Sessão | Recursos | Snapshot |", "|---|---|---|", *summary, f"| **Total** | **{total}** | |", *body, ""]
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"{total} recursos -> {out}")


if __name__ == "__main__":
    main()
