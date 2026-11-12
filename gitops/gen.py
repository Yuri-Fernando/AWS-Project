#!/usr/bin/env python
"""Gera os manifests Kustomize do ecossistema a partir de gitops/apps.json (stdlib; YAML escrito à mão).

  python gitops/gen.py            # (re)gera gitops/apps/<app>/{base,overlays/floci,overlays/aws}
Padrões do workshop aplicados: probes readiness/liveness, PDB, requests/limits, securityContext não-root,
imagem trocada pela pipeline com `kustomize edit set image`. Overlay floci: 1 réplica + endpoint do emulador;
overlay aws: 2 réplicas, sem credenciais (IRSA/Pod Identity).
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SPEC = json.loads((ROOT / "apps.json").read_text(encoding="utf-8"))
NS = SPEC["namespace"]
HDR = "# GERADO por gitops/gen.py a partir de gitops/apps.json — edite o spec, não este arquivo.\n"


def w(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(HDR + text.lstrip("\n"), encoding="utf-8")


def env_block(env: dict, secret_env: list, app: str, optional: bool, indent: int) -> str:
    pad = " " * indent
    lines = [f"{pad}- name: {k}\n{pad}  value: \"{v}\"" for k, v in env.items()]
    for s in secret_env:
        lines.append(f"{pad}- name: {s}\n{pad}  valueFrom:\n{pad}    secretKeyRef:\n{pad}      name: {app}-secrets\n"
                     f"{pad}      key: {s}\n{pad}      optional: {'true' if optional else 'false'}")
    return ("\n".join(lines) + "\n") if lines else ""


def probe(app: dict, kind: str) -> str:
    delay, period = (10, 10) if kind == "readinessProbe" else (30, 20)
    if app["health"]:
        how = f"httpGet:\n              path: {app['health']}\n              port: http"
    else:
        how = "tcpSocket:\n              port: http"
    return (f"          {kind}:\n            {how}\n            initialDelaySeconds: {delay}\n"
            f"            periodSeconds: {period}\n            failureThreshold: 6\n")


def gen_app(name: str, app: dict) -> None:
    base = ROOT / "apps" / name / "base"
    env = env_block(app["env"], app.get("secretEnv", []), name, app.get("optionalSecret", False), 12)
    w(base / "deployment.yaml", f"""
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {name}
  labels: {{app.kubernetes.io/name: {name}, app.kubernetes.io/part-of: argus-ecosystem}}
  annotations: {{argus.dev/source-repo: "{app['repo']}"}}
spec:
  replicas: 1
  revisionHistoryLimit: 3
  selector:
    matchLabels: {{app.kubernetes.io/name: {name}}}
  template:
    metadata:
      labels: {{app.kubernetes.io/name: {name}, app.kubernetes.io/part-of: argus-ecosystem}}
    spec:
      securityContext: {{runAsNonRoot: true, runAsUser: 10001, fsGroup: 10001, seccompProfile: {{type: RuntimeDefault}}}}
      containers:
        - name: {name}
          image: {name}
          imagePullPolicy: IfNotPresent
          ports:
            - {{name: http, containerPort: {app['port']}}}
          envFrom:
            - configMapRef: {{name: platform-env, optional: true}}
          env:
{env if env else "            []" + chr(10)}          resources:
            requests: {{cpu: {app['cpu']}, memory: {app['memory']}}}
            limits: {{memory: {app['limit']}}}
          securityContext: {{allowPrivilegeEscalation: false, capabilities: {{drop: [ALL]}}}}
{probe(app, "readinessProbe")}{probe(app, "livenessProbe")}""")
    w(base / "service.yaml", f"""
apiVersion: v1
kind: Service
metadata:
  name: {name}
  labels: {{app.kubernetes.io/name: {name}}}
spec:
  selector: {{app.kubernetes.io/name: {name}}}
  ports:
    - {{name: http, port: 80, targetPort: http}}
""")
    w(base / "pdb.yaml", f"""
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: {name}
spec:
  maxUnavailable: 1
  selector:
    matchLabels: {{app.kubernetes.io/name: {name}}}
""")
    w(base / "kustomization.yaml", """
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources: [deployment.yaml, service.yaml, pdb.yaml]
""")
    ing = name in SPEC.get("ingress", {}).get("apps", [])
    for target, replicas in (("floci", 1), ("aws", 2)):
        extra = (", serviceaccount.yaml" + (", ingress.yaml" if ing else "")) if target == "aws" else ""
        w(ROOT / "apps" / name / "overlays" / target / "kustomization.yaml", f"""
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: {NS}
resources: [../../base{extra}]
replicas:
  - {{name: {name}, count: {replicas}}}
images:
  - name: {name}
    newName: {SPEC['registry'][target]}/{name}
    newTag: lab
""" + (sa_patch("Deployment", name) if target == "aws" else ""))
        if target == "aws":
            gen_sa(name)
            if ing:
                gen_ingress(name, app)


def gen_ingress(name: str, app: dict) -> None:
    """AWS real: Ingress -> ALB compartilhado (group.name) com HTTP->HTTPS. O certificado é achado pelo controller
    via host do `tls` (ACM, stack 02) — nenhum ARN/ID de conta no git."""
    cfg = SPEC["ingress"]
    host = f"{name.split('-')[0]}.{cfg['domain']}"
    health = app["health"] or "/"
    w(ROOT / "apps" / name / "overlays" / "aws" / "ingress.yaml", f"""
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {name}
  labels: {{app.kubernetes.io/name: {name}, app.kubernetes.io/part-of: argus-ecosystem}}
  annotations:
    alb.ingress.kubernetes.io/scheme: internet-facing
    alb.ingress.kubernetes.io/target-type: ip
    alb.ingress.kubernetes.io/group.name: {cfg['group']}
    alb.ingress.kubernetes.io/listen-ports: '[{{"HTTP": 80}}, {{"HTTPS": 443}}]'
    alb.ingress.kubernetes.io/ssl-redirect: "443"
    alb.ingress.kubernetes.io/ssl-policy: ELBSecurityPolicy-TLS13-1-2-2021-06
    alb.ingress.kubernetes.io/healthcheck-path: {health}
    alb.ingress.kubernetes.io/tags: Project=argus-platform,Environment=lab,ManagedBy=aws-load-balancer-controller
spec:
  ingressClassName: alb
  tls:
    - hosts: [{host}]
  rules:
    - host: {host}
      http:
        paths:
          - {{path: /, pathType: Prefix, backend: {{service: {{name: {name}, port: {{number: 80}}}}}}}}
""")


def gen_job(name: str, job: dict) -> None:
    base = ROOT / "apps" / name / "base"
    env = env_block(job["env"], [], name, False, 12)
    w(base / "job.yaml", f"""
apiVersion: batch/v1
kind: Job
metadata:
  name: {name}
  labels: {{app.kubernetes.io/name: {name}, app.kubernetes.io/part-of: argus-ecosystem}}
  annotations: {{argus.dev/source-repo: "{job['repo']}"}}
spec:
  backoffLimit: 1
  ttlSecondsAfterFinished: 86400
  template:
    metadata:
      labels: {{app.kubernetes.io/name: {name}}}
    spec:
      restartPolicy: Never
      securityContext: {{runAsNonRoot: true, runAsUser: 10001, seccompProfile: {{type: RuntimeDefault}}}}
      containers:
        - name: {name}
          image: {name}
          envFrom:
            - configMapRef: {{name: platform-env, optional: true}}
          env:
{env}          resources:
            requests: {{cpu: {job['cpu']}, memory: {job['memory']}}}
            limits: {{memory: {job['limit']}}}
          securityContext: {{allowPrivilegeEscalation: false, capabilities: {{drop: [ALL]}}}}
""")
    w(base / "kustomization.yaml", """
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources: [job.yaml]
""")
    for target in ("floci", "aws"):
        w(ROOT / "apps" / name / "overlays" / target / "kustomization.yaml", f"""
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: {NS}
resources: [../../base{', serviceaccount.yaml' if target == 'aws' else ''}]
images:
  - name: {name}
    newName: {SPEC['registry'][target]}/{name}
    newTag: lab
""" + (sa_patch("Job", name) if target == "aws" else ""))
        if target == "aws":
            gen_sa(name)


def gen_sa(name: str) -> None:
    """AWS real: ServiceAccount por app — a stack 06 associa a role (EKS Pod Identity) a <namespace>/<app>."""
    w(ROOT / "apps" / name / "overlays" / "aws" / "serviceaccount.yaml", f"""
apiVersion: v1
kind: ServiceAccount
metadata:
  name: {name}
  labels: {{app.kubernetes.io/name: {name}, app.kubernetes.io/part-of: argus-ecosystem}}
""")


def sa_patch(kind: str, name: str) -> str:
    return f"""patches:
  - target: {{kind: {kind}, name: {name}}}
    patch: |-
      - op: add
        path: /spec/template/spec/serviceAccountName
        value: {name}
"""


def gen_env() -> None:
    lines = "\n".join(f"  {k}: \"{v}\"" for k, v in SPEC["floci_env"].items())
    w(ROOT / "env" / "floci" / "platform-env.yaml", f"""
apiVersion: v1
kind: ConfigMap
metadata:
  name: platform-env
  namespace: {NS}
  labels: {{app.kubernetes.io/part-of: argus-ecosystem}}
data:
{lines}
""")
    w(ROOT / "env" / "floci" / "namespace.yaml", f"""
apiVersion: v1
kind: Namespace
metadata:
  name: {NS}
  labels: {{app.kubernetes.io/part-of: argus-ecosystem}}
""")
    w(ROOT / "env" / "floci" / "kustomization.yaml", """
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources: [namespace.yaml, platform-env.yaml]
""")
    # AWS real: sem endpoint nem chaves — credenciais vêm do EKS Pod Identity (stack 06)
    aws_lines = "\n".join(f"  {k}: \"{v}\"" for k, v in SPEC["aws_env"].items())
    w(ROOT / "env" / "aws" / "platform-env.yaml", f"""
apiVersion: v1
kind: ConfigMap
metadata:
  name: platform-env
  namespace: {NS}
  labels: {{app.kubernetes.io/part-of: argus-ecosystem}}
data:
{aws_lines}
""")
    w(ROOT / "env" / "aws" / "namespace.yaml", (ROOT / "env" / "floci" / "namespace.yaml").read_text(encoding="utf-8").replace(HDR, ""))
    w(ROOT / "env" / "aws" / "kustomization.yaml", """
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources: [namespace.yaml, platform-env.yaml]
""")
    # app-of-apps local (todas as apps de uma vez: kubectl apply -k gitops/overlays/<target>)
    apps = list(SPEC["apps"]) + list(SPEC["jobs"])
    for target in ("floci", "aws"):
        w(ROOT / "overlays" / target / "kustomization.yaml", "apiVersion: kustomize.config.k8s.io/v1beta1\nkind: Kustomization\nresources:\n"
          + f"  - ../../env/{target}\n" + "".join(f"  - ../../apps/{a}/overlays/{target}\n" for a in apps))


def gen_argocd() -> None:
    elems = "".join(f"          - app: {a}\n" for a in list(SPEC["apps"]) + list(SPEC["jobs"]))
    w(ROOT / "argocd" / "ecosystem.applicationset.yaml", f"""
# ApplicationSet: uma Application ArgoCD por app do ecossistema (overlay escolhido por TARGET).
# Requer a branch publicada no GitHub (push via @devops). Até lá: kubectl apply -k gitops/overlays/floci.
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: argus-ecosystem
  namespace: argocd
spec:
  goTemplate: true
  generators:
    - list:
        elements:
{elems}  template:
    metadata:
      name: "{{{{.app}}}}"
    spec:
      project: default
      source:
        repoURL: https://github.com/Yuri-Fernando/AWS-Project.git
        targetRevision: main
        path: "gitops/apps/{{{{.app}}}}/overlays/floci"
      destination:
        server: https://kubernetes.default.svc
        namespace: {NS}
      syncPolicy:
        automated: {{prune: true, selfHeal: true}}
        syncOptions: [CreateNamespace=true]
""")


if __name__ == "__main__":
    for n, a in SPEC["apps"].items():
        gen_app(n, a)
    for n, j in SPEC["jobs"].items():
        gen_job(n, j)
    gen_env()
    gen_argocd()
    print(f"gerado: {len(SPEC['apps'])} apps + {len(SPEC['jobs'])} jobs em {ROOT / 'apps'}")
