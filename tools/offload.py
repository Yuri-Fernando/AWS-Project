#!/usr/bin/env python
"""Dados FORA da AWS: copia o que importa da conta (floci ou AWS real) para armazenamento externo.

Motivo: no Free Plan, ao fim dos créditos/6 meses a conta é suspensa e os dados apagados após 90 dias.
Nada que precise durar fica só na AWS.

  python tools/offload.py [--target free|real] [--dest D:\\argus-data] [--r2]

Copia: buckets S3 do projeto (artefatos de ML, state do Terraform, lakehouse) e tabelas DynamoDB do projeto
(exportadas em JSONL). Destinos: pasta local datada (padrão D:\\argus-data\\<data>) e, com --r2, Cloudflare R2
(API S3, 10 GB grátis, sem egress) usando credenciais do cofre ~/.claude/secrets/r2.env
(R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET) — sem elas, o passo R2 fica BLOCKED_BY_CONFIGURATION.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

PREFIX = os.environ.get("PROJECT_PREFIX", "argus-platform-lab")
TABLE_PREFIXES = ("credit-score-", "argus-platform-")


def aws_env(target: str) -> dict:
    env = {**os.environ, "AWS_PAGER": ""}
    if target == "free":
        env.update(AWS_ENDPOINT_URL=os.environ.get("FLOCI_ENDPOINT", "http://localhost.floci.io:4566"),
                   AWS_ACCESS_KEY_ID="test", AWS_SECRET_ACCESS_KEY="test", AWS_DEFAULT_REGION="us-east-1")
    else:
        env.setdefault("AWS_PROFILE", os.environ.get("LAB_REAL_PROFILE", "argus-lab"))
        env.setdefault("AWS_DEFAULT_REGION", "us-east-1")
    return env


def aws_json(args: list[str], env: dict) -> dict:
    r = subprocess.run(["aws", *args, "--output", "json"], env=env, capture_output=True, text=True)
    return json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else {}


def load_r2() -> dict | None:
    f = Path.home() / ".claude" / "secrets" / "r2.env"
    if not f.exists():
        return None
    vals = dict(line.split("=", 1) for line in f.read_text(encoding="utf-8").splitlines() if "=" in line and not line.startswith("#"))
    need = ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET")
    return vals if all(vals.get(k) for k in need) else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", choices=["free", "real"], default="free")
    ap.add_argument("--dest", default=r"D:\argus-data" if Path("D:/").exists() else str(Path.home() / "argus-data"))
    ap.add_argument("--r2", action="store_true")
    a = ap.parse_args()
    env = aws_env(a.target)
    out = Path(a.dest) / a.target / datetime.now().strftime("%Y-%m-%dT%H%M")
    out.mkdir(parents=True, exist_ok=True)
    report = {"target": a.target, "dest": str(out), "buckets": {}, "tables": {}}

    buckets = [b["Name"] for b in aws_json(["s3api", "list-buckets"], env).get("Buckets", []) if b["Name"].startswith((PREFIX, "credit-score-"))]
    for b in buckets:
        r = subprocess.run(["aws", "s3", "sync", f"s3://{b}", str(out / "s3" / b), "--only-show-errors"], env=env)
        n = sum(1 for p in (out / "s3" / b).rglob("*") if p.is_file()) if (out / "s3" / b).exists() else 0
        report["buckets"][b] = {"ok": r.returncode == 0, "files": n}
        print(f"[{'ok' if r.returncode == 0 else 'FALHA'}] s3://{b} -> {n} arquivos")

    tables = [t for t in aws_json(["dynamodb", "list-tables"], env).get("TableNames", []) if t.startswith(TABLE_PREFIXES)]
    for t in tables:
        items, token = [], None
        while True:
            args = ["dynamodb", "scan", "--table-name", t] + (["--starting-token", token] if token else [])
            page = aws_json(args, env)
            items += page.get("Items", [])
            token = page.get("NextToken")
            if not token:
                break
        dst = out / "dynamodb" / f"{t}.jsonl"
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text("\n".join(json.dumps(i, ensure_ascii=False) for i in items), encoding="utf-8")
        report["tables"][t] = len(items)
        print(f"[ok] dynamodb {t} -> {len(items)} itens")

    if a.r2:
        r2 = load_r2()
        if not r2:
            report["r2"] = "BLOCKED_BY_CONFIGURATION (faltam credenciais em ~/.claude/secrets/r2.env)"
        else:
            r2env = {**os.environ, "AWS_ACCESS_KEY_ID": r2["R2_ACCESS_KEY_ID"], "AWS_SECRET_ACCESS_KEY": r2["R2_SECRET_ACCESS_KEY"],
                     "AWS_DEFAULT_REGION": "auto", "AWS_PAGER": ""}
            endpoint = f"https://{r2['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com"
            rc = subprocess.run(["aws", "s3", "sync", str(out), f"s3://{r2['R2_BUCKET']}/{a.target}/{out.name}",
                                 "--endpoint-url", endpoint, "--only-show-errors"], env=r2env).returncode
            report["r2"] = "ok" if rc == 0 else f"falhou ({rc})"
        print(f"[r2] {report['r2']}")

    (out / "offload-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"-> {out}")


if __name__ == "__main__":
    main()
