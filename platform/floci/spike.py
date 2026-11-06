#!/usr/bin/env python
"""Spike de compatibilidade: aplica stacks Terraform (sem editá-las) contra o floci usando override files.

Para cada stack, em ordem: gera `zz_floci_override.tf` (provider + backend apontando p/ floci), roda
`terraform init` e `apply`, registra PASS/FAIL por recurso; no fim faz `destroy` em ordem reversa.

  python spike.py inspect <dir-com-stacks>
  python spike.py run <dir-com-stacks> [--stacks 00-x,01-y] [--no-destroy] [--var-file-dir DIR]
Saída: <dir>/floci-compat.json + floci-compat.md
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ENDPOINT = os.environ.get("FLOCI_ENDPOINT", "http://localhost.floci.io:4566")
# serviços do provider aws que as stacks do curso usam (+ folga)
SERVICES = ["acm", "amp", "apigateway", "apigatewayv2", "autoscaling", "budgets", "cloudformation", "cloudtrail", "cloudwatch",
            "cognitoidp", "dynamodb", "ec2", "ecr", "ecrpublic", "ecs", "eks", "elb", "elbv2", "events", "grafana", "iam",
            "identitystore", "kms", "lambda", "logs", "organizations", "rds", "route53", "s3", "s3control", "sagemaker", "secretsmanager",
            "sfn", "sns", "sqs", "ssm", "ssoadmin", "sts", "wafv2"]


def remote_state_overrides(stack: Path) -> str:
    """Reescreve data.terraform_remote_state (backend s3) para ler o state do floci."""
    out = []
    for p in stack.glob("*.tf"):
        if "override" in p.name:
            continue
        txt = p.read_text(encoding="utf-8", errors="ignore")
        for m in re.finditer(r'data\s+"terraform_remote_state"\s+"(\w+)"\s*\{(.*?)\n\}', txt, re.S):
            name, body = m.group(1), m.group(2)
            get = lambda k: (re.search(rf'{k}\s*=\s*"([^"]+)"', body) or [None, None])[1]
            out.append(f'''
data "terraform_remote_state" "{name}" {{
  backend = "s3"
  config = {{
    bucket                      = "{get('bucket')}"
    key                         = "{get('key')}"
    region                      = "us-east-1"
    access_key                  = "test"
    secret_key                  = "test"
    skip_credentials_validation = true
    skip_requesting_account_id  = true
    skip_region_validation      = true
    use_path_style              = true
    endpoints                   = {{ s3 = "{ENDPOINT}", sts = "{ENDPOINT}" }}
  }}
}}''')
    return "\n".join(out)


SPIKE_ROLE = "arn:aws:iam::000000000000:role/floci-spike-admin"


def ensure_spike_role() -> None:
    """Role usada quando a stack declara assume_role (ex.: eks-express-iac com <YOUR_ROLE>)."""
    env = {**os.environ, "AWS_ENDPOINT_URL": ENDPOINT, "AWS_ACCESS_KEY_ID": "test", "AWS_SECRET_ACCESS_KEY": "test",
           "AWS_DEFAULT_REGION": "us-east-1"}
    trust = json.dumps({"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Principal": {"AWS": "*"},
                                                                  "Action": ["sts:AssumeRole", "sts:TagSession"]}]})
    subprocess.run(["aws", "iam", "create-role", "--role-name", "floci-spike-admin", "--assume-role-policy-document", trust],
                   capture_output=True, env=env)


def override_tf(backend: str | None, state_key: str, bucket: str, lock_table: str | None, assume_role: bool = False) -> str:
    eps = "\n".join(f'    {s} = "{ENDPOINT}"' for s in SERVICES)
    ar = f'\n  assume_role {{\n    role_arn = "{SPIKE_ROLE}"\n  }}\n' if assume_role else ""
    be = ""
    if backend == "s3":
        lock = f'    dynamodb_table = "{lock_table}"\n' if lock_table else '    use_lockfile = true\n'
        be = f'''
terraform {{
  backend "s3" {{
    bucket                      = "{bucket}"
    key                         = "{state_key}"
    region                      = "us-east-1"
    access_key                  = "test"
    secret_key                  = "test"
    skip_credentials_validation = true
    skip_requesting_account_id  = true
    skip_region_validation      = true
    use_path_style              = true
    endpoints = {{
      s3       = "{ENDPOINT}"
      dynamodb = "{ENDPOINT}"
      sts      = "{ENDPOINT}"
    }}
{lock}  }}
}}
'''
    return f'''# GERADO por platform/floci/spike.py — aponta a stack para o floci. Não versionar nas stacks do curso.
provider "aws" {{
  access_key                  = "test"
  secret_key                  = "test"
  region                      = "us-east-1"
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = false
  s3_use_path_style           = true{ar}
  endpoints {{
{eps}
  }}
}}
{be}'''


def inspect(stack: Path) -> dict:
    txt = "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in stack.glob("*.tf") if "override" not in p.name)
    m = re.search(r'backend\s+"(\w+)"\s*\{(.*?)\n\s*\}', txt, re.S)
    backend, bcfg = (m.group(1), m.group(2)) if m else (None, "")
    get = lambda k: (re.search(rf'{k}\s*=\s*"([^"]+)"', bcfg) or [None, None])[1]
    return {
        "stack": stack.name, "backend": backend, "bucket": get("bucket"), "key": get("key"),
        "lock_table": get("dynamodb_table"), "use_lockfile": "use_lockfile" in bcfg,
        "providers": sorted(set(re.findall(r'provider\s+"(\w+)"', txt))),
        "resources": sorted(set(re.findall(r'resource\s+"(\w+)"\s+"', txt))),
        "data": sorted(set(re.findall(r'data\s+"(\w+)"\s+"', txt))),
        "remote_state": "terraform_remote_state" in txt,
    }


def tf(stack: Path, *args: str, timeout: int = 1800) -> tuple[int, str]:
    env = {**os.environ, "TF_IN_AUTOMATION": "1", "TF_PLUGIN_CACHE_DIR": os.environ.get("TF_PLUGIN_CACHE_DIR", r"D:\Claude Temp\cache\terraform"),
           "AWS_ACCESS_KEY_ID": "test", "AWS_SECRET_ACCESS_KEY": "test", "AWS_DEFAULT_REGION": "us-east-1",
           "AWS_ENDPOINT_URL": ENDPOINT}
    r = subprocess.run(["terraform", f"-chdir={stack}", *args, "-no-color"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env, timeout=timeout)
    return r.returncode, (r.stdout + "\n" + r.stderr)


def errors_of(out: str) -> list[str]:
    errs = []
    for blk in re.split(r"\n(?=Error: )", out):
        if blk.startswith("Error: "):
            head = blk.splitlines()[0][7:]
            res = re.search(r"with (\S+),", blk)
            errs.append(f"{res.group(1) if res else '?'}: {head}"[:300])
    return errs


def run(root: Path, stacks: list[Path], destroy: bool, var_dir: Path | None) -> None:
    results = []
    os.environ.setdefault("TF_PLUGIN_CACHE_DIR", r"D:\Claude Temp\cache\terraform")
    Path(os.environ["TF_PLUGIN_CACHE_DIR"]).mkdir(parents=True, exist_ok=True)
    applied = []
    for st in stacks:
        info = inspect(st)
        # placeholders como "<tfstate-bucket>" viram um bucket do lab
        bucket = info["bucket"] if info["bucket"] and "<" not in info["bucket"] else "floci-spike-tfstate"
        src_txt = "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in st.glob("*.tf") if "override" not in p.name)
        has_ar = bool(re.search(r"assume_role\s*\{", src_txt))
        if has_ar:
            ensure_spike_role()
        (st / "zz_floci_override.tf").write_text(
            override_tf(info["backend"], info["key"] or f"{st.name}.tfstate", bucket, info["lock_table"], has_ar)
            + remote_state_overrides(st), encoding="utf-8")
        varargs = []
        if var_dir and (var_dir / f"{st.name}.tfvars").exists():
            varargs = [f"-var-file={(var_dir / f'{st.name}.tfvars').resolve()}"]
        if info["backend"] == "s3":  # o bucket de state precisa existir no floci
            subprocess.run(["aws", "s3", "mb", f"s3://{bucket}"], capture_output=True,
                           env={**os.environ, "AWS_ENDPOINT_URL": ENDPOINT, "AWS_ACCESS_KEY_ID": "test",
                                "AWS_SECRET_ACCESS_KEY": "test", "AWS_DEFAULT_REGION": "us-east-1"})
        t0 = time.time()
        rc, out = tf(st, "init", "-input=false", "-reconfigure")
        rec = {**info, "init_ok": rc == 0}
        if rc != 0:
            rec.update(apply_ok=False, errors=errors_of(out) or [out[-800:]])
        else:
            rc, out = tf(st, "apply", "-input=false", "-auto-approve", *varargs)
            rec["apply_ok"] = rc == 0
            rec["errors"] = errors_of(out) if rc else []
            created = re.findall(r"^(\S+): Creation complete", out, re.M)
            rec["created"] = created
            if rc == 0 or created:
                applied.append((st, varargs))
        rec["seconds"] = round(time.time() - t0, 1)
        results.append(rec)
        print(f"[{'PASS' if rec.get('apply_ok') else 'FAIL'}] {st.parent.name}/{st.name} "
              f"criados={len(rec.get('created', []))} erros={len(rec.get('errors', []))} {rec['seconds']}s", flush=True)
        for e in rec.get("errors", [])[:8]:
            print("     -", e, flush=True)
    if destroy:
        for st, varargs in reversed(applied):
            rc, out = tf(st, "destroy", "-input=false", "-auto-approve", *varargs)
            print(f"[destroy {'ok' if rc == 0 else 'FALHOU'}] {st.parent.name}/{st.name}", flush=True)
            for r in results:
                if r["stack"] == st.name:
                    r["destroy_ok"] = rc == 0
                    if rc:
                        r["destroy_errors"] = errors_of(out)
    (root / "floci-compat.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    L = ["# Matriz de compatibilidade floci", "", f"floci endpoint {ENDPOINT}", "",
         "| Stack | Backend | init | apply | destroy | criados | erros |", "|---|---|---|---|---|---|---|"]
    for r in results:
        L.append(f"| {r['stack']} | {r['backend']} | {'✅' if r['init_ok'] else '❌'} | {'✅' if r.get('apply_ok') else '❌'} | "
                 f"{'✅' if r.get('destroy_ok') else ('—' if 'destroy_ok' not in r else '❌')} | {len(r.get('created', []))} | "
                 f"{'<br>'.join(e.replace('|', '/') for e in r.get('errors', [])[:6])} |")
    (root / "floci-compat.md").write_text("\n".join(L), encoding="utf-8")
    print(f"-> {root / 'floci-compat.md'}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["inspect", "run"])
    ap.add_argument("root")
    ap.add_argument("--stacks")
    ap.add_argument("--no-destroy", action="store_true")
    ap.add_argument("--var-file-dir")
    a = ap.parse_args()
    root = Path(a.root)
    stacks = sorted(p for p in root.iterdir() if p.is_dir() and list(p.glob("*.tf")))
    if a.stacks:
        want = a.stacks.split(",")
        stacks = [s for s in stacks if s.name in want]
    if a.cmd == "inspect":
        for s in stacks:
            i = inspect(s)
            print(f"## {s.name} backend={i['backend']} bucket={i['bucket']} key={i['key']} lock={i['lock_table'] or ('lockfile' if i['use_lockfile'] else '-')}"
                  f" remote_state={i['remote_state']}\n   providers={i['providers']}\n   resources={i['resources']}\n   data={i['data']}")
    else:
        run(root, stacks, not a.no_destroy, Path(a.var_file_dir) if a.var_file_dir else None)


if __name__ == "__main__":
    main()
