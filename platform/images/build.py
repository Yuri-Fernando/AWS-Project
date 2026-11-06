#!/usr/bin/env python
"""Build + push das imagens do ecossistema para o ECR (floci por padrão).

  python platform/images/build.py [--only argus-api,churn-api] [--no-push] [--eco-dir D:\\...\\eco]

Contexto de cada imagem = clone do repositório do app (ECO_DIR/<repo>); Dockerfile = platform/images/<imagem>/.
Os repositórios dos apps não são alterados. Tag = <sha curto do app> e "lab".
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REGISTRY = os.environ.get("ECR_REGISTRY", "localhost:4566/000000000000/us-east-1")
PROJECT = os.environ.get("ECR_PROJECT", "argus-platform")
ECO = Path(os.environ.get("ECO_DIR", r"D:\Claude Temp\staging\eco"))

# imagem -> (clone, subpasta de contexto, Dockerfile próprio? (None = usa o do repo))
IMAGES = {
    "argus-api":        ("argus", ".", HERE / "argus-api/Dockerfile"),
    "retentiq-api":     ("retentiq", "apps/api", None),
    "themis-api":       ("themis", ".", HERE / "themis-api/Dockerfile"),
    "omnimind-api":     ("omnimind", ".", HERE / "omnimind-api/Dockerfile"),
    "churn-api":        ("churn", ".", HERE / "churn-api/Dockerfile"),
    "riskcredit-train": ("riskcredit", ".", HERE / "riskcredit-train/Dockerfile"),
    "creditscore-app":  ("creditscore", ".", HERE / "creditscore-app/Dockerfile"),
}


def sh(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    print("  $", " ".join(cmd), flush=True)
    return subprocess.run(cmd, **kw)


def floci_env() -> dict:
    return {**os.environ, "AWS_ENDPOINT_URL": os.environ.get("AWS_ENDPOINT_URL", "http://localhost:4566"),
            "AWS_ACCESS_KEY_ID": os.environ.get("AWS_ACCESS_KEY_ID", "test"),
            "AWS_SECRET_ACCESS_KEY": os.environ.get("AWS_SECRET_ACCESS_KEY", "test"), "AWS_DEFAULT_REGION": "us-east-1"}


def login() -> None:
    pw = subprocess.run(["aws", "ecr", "get-login-password"], env=floci_env(), capture_output=True, text=True, check=True).stdout
    # docker login recebe só o host do registry (no estilo path, REGISTRY = host/conta/região)
    sh(["docker", "login", "--username", "AWS", "--password-stdin", REGISTRY.split("/")[0]], input=pw, text=True, check=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    ap.add_argument("--no-push", action="store_true")
    a = ap.parse_args()
    names = [n for n in IMAGES if not a.only or n in a.only.split(",")]
    if not a.no_push:
        login()
    results = {}
    for name in names:
        repo, sub, dockerfile = IMAGES[name]
        ctx = ECO / repo / sub
        if not ctx.exists():
            results[name] = f"SKIP (sem clone em {ctx})"
            continue
        sha = subprocess.run(["git", "-C", str(ECO / repo), "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip() or "dev"
        uri = f"{REGISTRY}/{PROJECT}/{name}"
        cmd = ["docker", "build", "-t", f"{uri}:{sha}", "-t", f"{uri}:lab", "--label", f"org.opencontainers.image.revision={sha}"]
        if dockerfile:
            cmd += ["-f", str(dockerfile), "--build-context", f"platform={dockerfile.parent}"]
        print(f"\n=== {name} ({repo}@{sha}) ===", flush=True)
        if sh(cmd + [str(ctx)]).returncode != 0:
            results[name] = "BUILD FALHOU"
            continue
        if a.no_push:
            results[name] = f"built {uri}:{sha}"
            continue
        ok = all(sh(["docker", "push", f"{uri}:{t}"]).returncode == 0 for t in (sha, "lab"))
        results[name] = f"pushed {uri}:{sha}" if ok else "PUSH FALHOU"
    print("\n## resultado")
    for k, v in results.items():
        print(f"- {k}: {v}")
    sys.exit(0 if all(not v.startswith(("BUILD", "PUSH")) for v in results.values()) else 1)


if __name__ == "__main__":
    main()
