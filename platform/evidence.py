#!/usr/bin/env python
"""Captura evidências visuais do laboratório (Playwright headless) em docs/evidence/.

  python platform/evidence.py [--target floci]

Faz port-forward dos serviços do cluster e tira screenshots: Grafana (Node Exporter Full — aula 07; recursos do
cluster), Prometheus targets, app Streamlit do Credit Score, Swagger da API de churn e console do ArgoCD.
Senhas vêm dos Secrets do cluster em memória (nunca são gravadas nem impressas).
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parent / "docs" / "evidence"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def forward(ns: str, svc: str, remote: int, env: dict) -> tuple[subprocess.Popen, int]:
    port = free_port()
    p = subprocess.Popen(["kubectl", "port-forward", "-n", ns, f"svc/{svc}", f"{port}:{remote}"], env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(60):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return p, port
        time.sleep(0.5)
    return p, port


def secret(ns: str, name: str, key: str, env: dict) -> str:
    out = subprocess.run(["kubectl", "get", "secret", "-n", ns, name, "-o", f"jsonpath={{.data.{key}}}"],
                         env=env, capture_output=True, text=True).stdout
    return base64.b64decode(out).decode() if out else ""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default="floci")
    a = ap.parse_args()
    from playwright.sync_api import sync_playwright

    env = {**os.environ, "KUBECONFIG": str(ROOT / ".kube" / f"{a.target}.yaml")}
    OUT.mkdir(parents=True, exist_ok=True)
    shots: list[str] = []
    procs = []
    graf_pw = secret("monitoring", "monitoring-grafana", "admin-password", env)
    argo_pw = secret("argocd", "argocd-initial-admin-secret", "password", env)
    try:
        g, gport = forward("monitoring", "monitoring-grafana", 80, env)
        pr, pport = forward("monitoring", "monitoring-kube-prometheus-prometheus", 9090, env)
        cs, csport = forward("ecosystem", "creditscore-app", 80, env)
        ch, chport = forward("ecosystem", "churn-api", 80, env)
        ar, arport = forward("argocd", "argocd-server", 80, env)
        procs = [g, pr, cs, ch, ar]
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            ctx = browser.new_context(viewport={"width": 1600, "height": 1000}, device_scale_factor=1)
            page = ctx.new_page()

            def settle() -> None:
                # páginas com polling/websocket (Prometheus, Streamlit) nunca ficam "networkidle"
                try:
                    page.wait_for_load_state("networkidle", timeout=8000)
                except Exception:
                    page.wait_for_load_state("load")

            def shot(name: str, wait: float = 4.0, full: bool = False) -> None:
                time.sleep(wait)
                path = OUT / f"{name}.png"
                page.screenshot(path=str(path), full_page=full)
                shots.append(path.name)
                print(f"  ✓ {path.name}", flush=True)

            # Grafana: login + dashboards
            page.goto(f"http://127.0.0.1:{gport}/login")
            page.fill("input[name='user']", "admin")
            page.fill("input[name='password']", graf_pw)
            page.click("button[type='submit']")
            page.wait_for_url(lambda u: "/login" not in u, timeout=60000)  # sessão criada
            settle()
            res = page.request.get(f"http://127.0.0.1:{gport}/api/search?type=dash-db&limit=200").json()
            by_title = {d["title"]: d["url"] for d in res}
            wanted = [("grafana-node-exporter-full", ["Node Exporter Full"]),
                      ("grafana-k8s-cluster-compute", ["Kubernetes / Compute Resources / Cluster"]),
                      ("grafana-k8s-namespace-ecosystem", ["Kubernetes / Compute Resources / Namespace (Pods)"])]
            for name, titles in wanted:
                url = next((by_title[t] for t in titles if t in by_title), None)
                if not url:
                    print(f"  - dashboard ausente: {titles}")
                    continue
                q = "?orgId=1&from=now-1h&to=now&kiosk"
                if "Namespace" in titles[0]:
                    q += "&var-namespace=ecosystem"
                page.goto(f"http://127.0.0.1:{gport}{url}{q}")
                settle()
                shot(name, wait=8)

            # Prometheus: alvos de scrape
            page.goto(f"http://127.0.0.1:{pport}/targets")
            settle()
            shot("prometheus-targets", wait=4, full=True)

            # App Streamlit do Credit Score (front do repo Credit-Score-Predictor)
            page.goto(f"http://127.0.0.1:{csport}/")
            settle()
            shot("creditscore-streamlit", wait=8)

            # Swagger da API de churn (repo Churn_intelligence)
            page.goto(f"http://127.0.0.1:{chport}/docs")
            settle()
            shot("churn-api-swagger", wait=3)

            # ArgoCD
            if argo_pw:
                page.goto(f"http://127.0.0.1:{arport}/login")
                page.fill("input[name='username']", "admin")
                page.fill("input[name='password']", argo_pw)
                page.click("button[type='submit']")
                settle()
                shot("argocd-applications", wait=5)
            browser.close()
    finally:
        for p in procs:
            p.terminate()
    (OUT / "index.json").write_text(json.dumps({"target": a.target, "shots": shots}, indent=2), encoding="utf-8")
    print(f"{len(shots)} evidências em {OUT}")


if __name__ == "__main__":
    sys.exit(main())
