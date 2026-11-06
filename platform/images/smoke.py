#!/usr/bin/env python
"""Smoke test local das imagens: sobe cada container, espera o health responder, mostra log se falhar.

  python platform/images/smoke.py [--only argus-api,...] [--tag lab]
"""
from __future__ import annotations

import argparse
import os
import subprocess
import time
import urllib.request

REGISTRY = os.environ.get("ECR_REGISTRY", "localhost:4566/000000000000/us-east-1") + "/argus-platform"
# imagem -> (porta do container, caminho de health ou None = só verifica que o processo segue vivo, env extra)
SERVICES = {
    "argus-api": (8000, "/health", {}),
    "retentiq-api": (4000, "/health", {"JWT_SECRET": "smoke-only-not-a-secret", "PORT": "4000"}),
    "themis-api": (8000, "/health", {}),
    "omnimind-api": (8000, "/docs", {}),
    "churn-api": (8000, "/health", {}),
    "creditscore-app": (8501, "/_stcore/health", {}),
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    ap.add_argument("--tag", default="lab")
    ap.add_argument("--timeout", type=int, default=90)
    a = ap.parse_args()
    results = {}
    for i, (name, (port, path, env)) in enumerate(SERVICES.items()):
        if a.only and name not in a.only.split(","):
            continue
        host_port = 18000 + i
        cname = f"smoke-{name}"
        subprocess.run(["docker", "rm", "-f", cname], capture_output=True)
        cmd = ["docker", "run", "-d", "--name", cname, "-p", f"127.0.0.1:{host_port}:{port}"]
        for k, v in env.items():
            cmd += ["-e", f"{k}={v}"]
        subprocess.run(cmd + [f"{REGISTRY}/{name}:{a.tag}"], capture_output=True, check=True)
        ok, last = False, ""
        t0 = time.time()
        while time.time() - t0 < a.timeout:
            state = subprocess.run(["docker", "inspect", "-f", "{{.State.Running}}", cname], capture_output=True, text=True).stdout.strip()
            if state != "true":
                last = "container morreu"
                break
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{host_port}{path}", timeout=3) as r:
                    ok, last = r.status < 400, f"HTTP {r.status}"
                    if ok:
                        break
            except Exception as e:  # ainda subindo
                last = type(e).__name__
            time.sleep(3)
        logs = "" if ok else subprocess.run(["docker", "logs", "--tail", "25", cname], capture_output=True, text=True).stdout \
            + subprocess.run(["docker", "logs", "--tail", "25", cname], capture_output=True, text=True).stderr
        results[name] = (ok, f"{last} em {time.time() - t0:.0f}s")
        print(f"[{'OK ' if ok else 'FALHA'}] {name}: {results[name][1]}", flush=True)
        if logs:
            print("    " + logs.strip().replace("\n", "\n    ")[-2500:], flush=True)
        subprocess.run(["docker", "rm", "-f", cname], capture_output=True)
    raise SystemExit(0 if all(o for o, _ in results.values()) else 1)


if __name__ == "__main__":
    main()
