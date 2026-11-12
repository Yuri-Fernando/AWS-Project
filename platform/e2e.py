#!/usr/bin/env python
"""Teste de ponta a ponta do ecossistema no laboratório (floci + EKS emulado). stdlib + kubectl + aws cli.

  python platform/e2e.py [--target floci]

Verifica: (1) health de cada serviço no cluster via port-forward; (2) previsão real do churn-api;
(3) artefato do RiskCredit publicado no S3 com manifesto; (4) Lambda do Credit Score (serverless) com modelo v3
e persistência no DynamoDB. Sai com código != 0 se algo falhar. Grava o relatório em platform/.state/e2e-<target>.json.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))
from contracts.validate import validate  # noqa: E402  (contratos entre os repos)

NS = "ecosystem"
SERVICES = {"argus-api": "/health", "retentiq-api": "/health", "themis-api": "/health", "omnimind-api": "/docs",
            "churn-api": "/health", "creditscore-app": "/_stcore/health"}


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def http(method: str, url: str, body: dict | None = None, timeout: int = 10) -> tuple[int, str]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def port_forward(svc: str, env: dict) -> tuple[subprocess.Popen, int]:
    port = free_port()
    p = subprocess.Popen(["kubectl", "port-forward", "-n", NS, f"svc/{svc}", f"{port}:80"], env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(40):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return p, port
        time.sleep(0.5)
    return p, port


def aws(args: list[str], env: dict) -> dict:
    r = subprocess.run(["aws", *args, "--output", "json"], env=env, capture_output=True, text=True)
    return json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else {"_error": r.stderr.strip()[:300]}


def aws_edge_checks(kenv: dict, record) -> None:
    """AWS real: (a) ArgoCD sincronizou as apps do GitHub; (b) ALB público com HTTPS (certificado autoassinado no ACM,
    por isso sem verificação de cadeia) e redirect HTTP -> HTTPS."""
    import http.client
    import ssl
    r = subprocess.run(["kubectl", "get", "applications", "-n", "argocd", "-o", "json"], env=kenv, capture_output=True, text=True)
    items = json.loads(r.stdout).get("items", []) if r.returncode == 0 and r.stdout.strip() else []
    good = [i["metadata"]["name"] for i in items
            if i.get("status", {}).get("sync", {}).get("status") == "Synced" and i.get("status", {}).get("health", {}).get("status") == "Healthy"]
    record("argocd/apps-synced-healthy", bool(items) and len(good) == len(items),
           f"{len(good)}/{len(items)} Applications Synced+Healthy (fonte: GitHub main)")
    for name, host, path in (("churn-api", "churn.argus.lab", "/health"), ("creditscore-app", "creditscore.argus.lab", "/_stcore/health")):
        lb = ""
        for _ in range(60):  # o controller leva alguns minutos para criar o ALB e o DNS propagar
            lb = subprocess.run(["kubectl", "get", "ingress", name, "-n", NS, "-o",
                                 "jsonpath={.status.loadBalancer.ingress[0].hostname}"], env=kenv, capture_output=True, text=True).stdout.strip()
            if lb:
                try:
                    socket.gethostbyname(lb)
                    break
                except OSError:
                    pass
            time.sleep(10)
        if not lb:
            record(f"alb/{name}/https", False, "Ingress sem hostname de ALB")
            continue
        try:
            ctx = ssl._create_unverified_context()  # autoassinado: valida o túnel TLS, não a cadeia de confiança
            c = http.client.HTTPSConnection(lb, 443, timeout=15, context=ctx)
            c.request("GET", path, headers={"Host": host})
            resp = c.getresponse()
            proto = c.sock.version() if c.sock else "?"
            record(f"alb/{name}/https", resp.status == 200, f"HTTPS {resp.status} via ALB ({proto}), Host {host}")
            c.close()
            h = http.client.HTTPConnection(lb, 80, timeout=15)
            h.request("GET", path, headers={"Host": host})
            rr = h.getresponse()
            record(f"alb/{name}/redirect", rr.status in (301, 302) and rr.getheader("Location", "").startswith("https://"),
                   f"HTTP {rr.status} -> {rr.getheader('Location', '')[:60]}")
        except Exception as e:
            record(f"alb/{name}/https", False, f"{type(e).__name__}: {e}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default="floci")
    a = ap.parse_args()
    kenv = {**os.environ, "KUBECONFIG": str(ROOT / ".kube" / f"{a.target}.yaml")}
    if a.target == "aws":  # AWS real: perfil do usuário IAM, endpoints reais
        aenv = {k: v for k, v in os.environ.items() if k.upper() not in ("AWS_ENDPOINT_URL", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY")}
        aenv.update(AWS_DEFAULT_REGION="us-east-1", AWS_PAGER="")
        aenv.setdefault("AWS_PROFILE", os.environ.get("LAB_REAL_PROFILE", "argus-lab"))
    else:
        aenv = {**os.environ, "AWS_ENDPOINT_URL": os.environ.get("FLOCI_ENDPOINT", "http://localhost.floci.io:4566"),
                "AWS_ACCESS_KEY_ID": "test", "AWS_SECRET_ACCESS_KEY": "test", "AWS_DEFAULT_REGION": "us-east-1", "AWS_PAGER": ""}
    checks: list[dict] = []

    def record(name: str, ok: bool, detail: str) -> None:
        checks.append({"check": name, "ok": ok, "detail": detail[:400]})
        print(f"[{'OK ' if ok else 'FALHA'}] {name}: {detail[:200]}", flush=True)

    # 1) health de cada serviço + 2) previsão do churn
    for svc, path in SERVICES.items():
        p, port = port_forward(svc, kenv)
        try:
            code, body = http("GET", f"http://127.0.0.1:{port}{path}")
            record(f"k8s/{svc}{path}", code == 200, f"HTTP {code}")
            if svc == "churn-api" and code == 200:
                c, b = http("POST", f"http://127.0.0.1:{port}/predict",
                            {"user_id": "u_e2e", "recency_days": 40, "frequency": 1, "avg_session_duration": 2.0,
                             "intensity": 1.1, "engagement_trend": -0.6})
                record("k8s/churn-api/predict", c == 200, f"HTTP {c} {b[:160]}")
                if c == 200:
                    errs = validate("scoring_result.v1", json.loads(b))
                    record("contrato/scoring_result.v1 (churn)", not errs, "; ".join(errs) or "válido")
        except Exception as e:
            record(f"k8s/{svc}{path}", False, f"{type(e).__name__}: {e}")
        finally:
            p.terminate()

    # 3) RiskCredit: artefato champion publicado no S3 pelo Job
    bucket = "argus-platform-lab-ml-artifacts"
    latest = subprocess.run(["aws", "s3", "cp", f"s3://{bucket}/riskcredit/champion/LATEST", "-"], env=aenv,
                            capture_output=True, text=True).stdout.strip()
    man = subprocess.run(["aws", "s3", "cp", f"s3://{bucket}/{latest}/manifest.json", "-"], env=aenv,
                         capture_output=True, text=True).stdout if latest else ""
    n = len(json.loads(man).get("files", {})) if man.strip().startswith("{") else 0
    record("s3/riskcredit-champion", n > 0, f"{latest} ({n} arquivos com sha256)")
    if man.strip().startswith("{"):
        errs = validate("model_manifest.v1", json.loads(man))
        record("contrato/model_manifest.v1 (riskcredit->creditscore)", not errs, "; ".join(errs) or "válido")

    # 4) Credit Score serverless: Lambda (modelo v3) + DynamoDB
    event = {"version": "2.0", "routeKey": "POST /predict", "rawPath": "/predict", "isBase64Encoded": False,
             "headers": {"content-type": "application/json"},
             "requestContext": {"requestId": "e2e", "http": {"method": "POST", "path": "/predict"}},
             "body": json.dumps({"data": {"LIMIT_BAL": 50000, "PAY_0": 0, "PAY_2": 0, "PAY_3": 0, "PAY_4": 0, "PAY_5": 0,
                                          "PAY_6": 0, "BILL_AMT1": 12000, "BILL_AMT2": 11000, "BILL_AMT3": 10500,
                                          "BILL_AMT4": 9800, "BILL_AMT5": 9000, "BILL_AMT6": 8700, "PAY_AMT1": 2000,
                                          "PAY_AMT2": 1800, "PAY_AMT3": 1500, "PAY_AMT4": 1500, "PAY_AMT5": 1400,
                                          "PAY_AMT6": 1300}})}
    ev_file = ROOT / ".state" / "e2e-event.json"
    out_file = ROOT / ".state" / "e2e-lambda-out.json"
    ev_file.parent.mkdir(exist_ok=True)
    ev_file.write_text(json.dumps(event), encoding="utf-8")
    before = aws(["dynamodb", "scan", "--table-name", "credit-score-lab-inference-log", "--select", "COUNT"], aenv).get("Count", 0)
    subprocess.run(["aws", "lambda", "invoke", "--function-name", "credit-score-lab-predict", "--cli-binary-format",
                    "raw-in-base64-out", "--payload", f"fileb://{ev_file}", "--cli-read-timeout", "300", str(out_file)],
                   env=aenv, capture_output=True)
    try:
        resp = json.loads(out_file.read_text(encoding="utf-8"))
        body = json.loads(resp.get("body", "{}"))
        res = body.get("results", [{}])[0]
        record("lambda/credit-score-predict", resp.get("statusCode") == 200 and "pd" in res,
               f"status {resp.get('statusCode')} modelo {body.get('model_version')} pd={res.get('pd')} faixa={res.get('risk_band')}")
        errs = validate("scoring_result.v1", body)
        record("contrato/scoring_result.v1 (creditscore)", not errs, "; ".join(errs) or "válido")
    except Exception as e:
        record("lambda/credit-score-predict", False, f"{type(e).__name__}: {e}")
    after = aws(["dynamodb", "scan", "--table-name", "credit-score-lab-inference-log", "--select", "COUNT"], aenv).get("Count", 0)
    record("dynamodb/inference-log", after > before, f"registros {before} -> {after}")

    if a.target == "aws":
        aws_edge_checks(kenv, record)

    ok = all(c["ok"] for c in checks)
    report = {"target": a.target, "at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "ok": ok, "checks": checks}
    (ROOT / ".state" / f"e2e-{a.target}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{'PASSOU' if ok else 'FALHOU'}: {sum(c['ok'] for c in checks)}/{len(checks)} verificações")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
