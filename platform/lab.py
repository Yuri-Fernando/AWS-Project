#!/usr/bin/env python
"""Orquestrador da plataforma (stdlib only). Mesmo código para o emulador floci e para a AWS real.

  python platform/lab.py floci-up | floci-down          # emulador local (docker compose)
  python platform/lab.py sync                           # copia _shared/providers.tf para cada stack
  python platform/lab.py up    [--target floci|aws] [--stacks 01-networking,02-eks]
  python platform/lab.py plan  [--target ...]
  python platform/lab.py down  [--target ...]           # destroy em ordem reversa
  python platform/lab.py kubeconfig [--target ...]      # escreve platform/.kube/<target>.yaml
  python platform/lab.py deploy [--target ...]          # aplica o ecossistema (gitops) no cluster
  python platform/lab.py status [--target ...]          # outputs de cada stack

TARGET=aws exige confirmação interativa (--yes-real-aws) e credenciais do ambiente: o padrão é floci (R$ 0).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent
TF = ROOT / "terraform"
SHARED = TF / "_shared"
STACKS = ["00-backend", "01-networking", "02-eks", "03-ci-cd", "04-security", "05-monitoring", "06-identity"]
FLOCI = os.environ.get("FLOCI_ENDPOINT", "http://localhost.floci.io:4566")
# .terraform e cache de providers FORA da pasta sincronizada (Google Drive trava com milhares de arquivos)
CACHE = Path(os.environ.get("LAB_CACHE_DIR", r"D:\Claude Temp\cache" if Path("D:/").exists() else Path.home() / ".cache"))
HEADER = "# GERADO por platform/lab.py sync a partir de _shared/providers.tf — edite o original, não esta cópia.\n"


def sh(cmd: list[str], env: dict | None = None, check: bool = True, cwd: Path | None = None) -> int:
    print("  $", " ".join(cmd), flush=True)
    r = subprocess.run(cmd, env=env, cwd=cwd)
    if check and r.returncode != 0:
        sys.exit(f"falhou ({r.returncode}): {' '.join(cmd)}")
    return r.returncode


def tf_env(stack: str, target: str) -> dict:
    env = dict(os.environ)
    data_dir = CACHE / "tfdata" / f"{stack}-{target}"
    plugin = CACHE / "terraform"
    data_dir.mkdir(parents=True, exist_ok=True)
    plugin.mkdir(parents=True, exist_ok=True)
    env.update(TF_DATA_DIR=str(data_dir), TF_PLUGIN_CACHE_DIR=str(plugin), TF_IN_AUTOMATION="1")
    # No Windows, os.environ devolve as chaves em MAIÚSCULAS e o Terraform casa TF_VAR_<nome> com o nome exato
    # da variável (minúsculo aqui). Sem isso, TF_VAR_enable_workload_identity=false era ignorado em silêncio.
    for k in [k for k in env if k.upper().startswith("TF_VAR_")]:
        env["TF_VAR_" + k[7:].lower()] = env.pop(k)
    if target == "floci":
        env.update(AWS_ACCESS_KEY_ID="test", AWS_SECRET_ACCESS_KEY="test", AWS_DEFAULT_REGION="us-east-1",
                   AWS_ENDPOINT_URL=FLOCI)
    else:
        env.setdefault("AWS_PROFILE", REAL_PROFILE)  # usuário IAM com MFA (envs/real/aws-config.example)
    return env


REAL_PROFILE = os.environ.get("LAB_REAL_PROFILE", "argus-lab")
# Valores locais do alvo real (ex.: budget_email, enable_workload_identity) — gitignored, nunca versionado.
REAL_TFVARS = ROOT.parent / "envs" / "real" / "real.auto.tfvars"


def tf_vars(target: str) -> list[str]:
    if target == "floci":
        return [f"-var=aws_endpoint={FLOCI}"]
    state_dir = (ROOT / ".state").as_posix()  # stacks leem saídas umas das outras do state local
    return [f"-var=local_state_dir={state_dir}"] + ([f"-var-file={REAL_TFVARS}"] if REAL_TFVARS.exists() else [])


def sync() -> None:
    src = (SHARED / "providers.tf").read_text(encoding="utf-8")
    for s in STACKS:
        (TF / s / "providers.tf").write_text(HEADER + src, encoding="utf-8")
    print(f"providers.tf sincronizado em {len(STACKS)} stacks")


LOCAL_OVERRIDE = "backend_override.tf"  # gitignored; só existe durante execuções --target real


def init(stack: str, target: str) -> None:
    d = TF / stack
    env = tf_env(stack, target)
    override = d / LOCAL_OVERRIDE
    if target == "aws" and stack != "00-backend":
        # Regra do dono: NENHUM dado persistido na AWS (Free Plan; a conta fecha sem upgrade). O state das stacks
        # reais fica local (platform/.state/, gitignored) via override file do Terraform, sem bucket S3.
        state = ROOT / ".state" / f"{stack}-aws.tfstate"
        state.parent.mkdir(exist_ok=True)
        override.write_text('# GERADO por platform/lab.py (--target real): state local, nada salvo na AWS.\n'
                            'terraform {\n  backend "local" {}\n}\n', encoding="utf-8")
        sh(["terraform", f"-chdir={d}", "init", "-input=false", "-reconfigure", f"-backend-config=path={state}"], env)
        return
    override.unlink(missing_ok=True)
    if stack == "00-backend":
        state = ROOT / ".state" / f"00-backend-{target}.tfstate"
        state.parent.mkdir(exist_ok=True)
        sh(["terraform", f"-chdir={d}", "init", "-input=false", "-reconfigure", f"-backend-config=path={state}"], env)
        return
    be = SHARED / f"backend-{target}.hcl"
    if not be.exists():
        sys.exit(f"falta {be} (copie de backend-{target}.hcl.example)")
    sh(["terraform", f"-chdir={d}", "init", "-input=false", "-reconfigure",
        f"-backend-config={be}", f"-backend-config=key={stack}.tfstate"], env)


def run(action: str, stacks: list[str], target: str) -> None:
    sync()
    order = list(reversed(stacks)) if action == "destroy" else stacks
    for s in order:
        if target == "aws" and s == "00-backend":
            print("\n=== 00-backend pulada no alvo real: state é local (regra: nada salvo na AWS) ===", flush=True)
            continue
        print(f"\n=== {action} {s} ({target}) ===", flush=True)
        init(s, target)
        if action == "destroy" and s == "01-networking" and target == "floci":
            floci_vpc_orphans(target)
        args = {"apply": ["apply", "-input=false", "-auto-approve"],
                "destroy": ["destroy", "-input=false", "-auto-approve"],
                "plan": ["plan", "-input=false"]}[action]
        sh(["terraform", f"-chdir={TF / s}", *args, *tf_vars(target)], tf_env(s, target))


def floci_vpc_orphans(target: str) -> None:
    """Só no emulador: o EKS emulado não remove o security group/ENIs que cria na VPC ao apagar o cluster (na AWS real
    o EKS remove), e o DeleteVpc falha com DependencyViolation. Apaga o que o Terraform NÃO gerencia antes do destroy."""
    vpc = outputs("01-networking", target).get("vpc_id")
    if not vpc:
        return
    env = tf_env("01-networking", target)

    def aws(*args: str) -> dict:
        r = subprocess.run(["aws", *args, "--output", "json"], env=env, capture_output=True, text=True)
        return json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else {}

    for eni in aws("ec2", "describe-network-interfaces", "--filters", f"Name=vpc-id,Values={vpc}").get("NetworkInterfaces", []):
        print(f"  órfão (emulador): ENI {eni['NetworkInterfaceId']}", flush=True)
        if eni.get("Attachment", {}).get("AttachmentId"):
            aws("ec2", "detach-network-interface", "--attachment-id", eni["Attachment"]["AttachmentId"], "--force")
        aws("ec2", "delete-network-interface", "--network-interface-id", eni["NetworkInterfaceId"])
    for sg in aws("ec2", "describe-security-groups", "--filters", f"Name=vpc-id,Values={vpc}").get("SecurityGroups", []):
        if sg["GroupName"] != "default":
            print(f"  órfão (emulador): security group {sg['GroupId']} ({sg['GroupName']})", flush=True)
            aws("ec2", "delete-security-group", "--group-id", sg["GroupId"])


def outputs(stack: str, target: str) -> dict:
    r = subprocess.run(["terraform", f"-chdir={TF / stack}", "output", "-json"], env=tf_env(stack, target),
                       capture_output=True, text=True)
    return {k: v.get("value") for k, v in json.loads(r.stdout or "{}").items()} if r.returncode == 0 else {}


def kubeconfig(target: str) -> Path:
    name = outputs("02-eks", target).get("cluster_name")
    if not name:
        sys.exit("cluster não encontrado: rode `up --stacks 02-eks` antes")
    out = ROOT / ".kube" / f"{target}.yaml"
    out.parent.mkdir(exist_ok=True)
    env = tf_env("02-eks", target)
    extra = ["--profile", env["AWS_PROFILE"]] if target == "aws" else []  # grava o perfil no exec do kubeconfig
    sh(["aws", "eks", "update-kubeconfig", "--name", name, "--kubeconfig", str(out), "--region", "us-east-1", *extra], env)
    if target == "floci":
        # O webhook de autenticação do EKS emulado só aceita tokens assinados por uma access key que EXISTA no IAM
        # do floci (a credencial genérica "test" é rejeitada — igual à AWS real, que exige identidade IAM válida).
        # Cria um usuário IAM de laboratório e injeta a chave no exec do kubeconfig (arquivo em .gitignore).
        key_file = ROOT / ".kube" / "floci-kube-admin.json"
        if not key_file.exists():
            subprocess.run(["aws", "iam", "create-user", "--user-name", "lab-kube-admin"], env=env, capture_output=True)
            r = subprocess.run(["aws", "iam", "create-access-key", "--user-name", "lab-kube-admin", "--output", "json"],
                               env=env, capture_output=True, text=True, check=True)
            key_file.write_text(r.stdout, encoding="utf-8")
        key = json.loads(key_file.read_text(encoding="utf-8"))["AccessKey"]
        txt = out.read_text(encoding="utf-8")
        if "AWS_ENDPOINT_URL" not in txt:
            # STS sem prefixo de conta: localhost funciona; o host precisa bater com o que o floci revalida
            envs = "".join(f"      - name: {k}\n        value: \"{v}\"\n" for k, v in
                           {"AWS_ENDPOINT_URL": FLOCI.replace("localhost.floci.io", "localhost"),
                            "AWS_ACCESS_KEY_ID": key["AccessKeyId"], "AWS_SECRET_ACCESS_KEY": key["SecretAccessKey"],
                            "AWS_SESSION_TOKEN": ""}.items())
            txt = txt.replace("      command: aws\n", "      command: aws\n      env:\n" + envs)
            out.write_text(txt, encoding="utf-8")
    print(f"export KUBECONFIG={out}")
    return out


def deploy(target: str) -> None:
    """Aplica o ecossistema (gitops/overlays/<target>) com kubectl; no floci injeta endpoint e segredos de lab."""
    import secrets
    repo = ROOT.parent
    kube = ROOT / ".kube" / f"{target}.yaml"
    env = {**os.environ, "KUBECONFIG": str(kube)}
    sh([sys.executable, str(repo / "gitops" / "gen.py")])
    # 1) manifests (inclui namespace + ConfigMap padrão); 2) no floci, sobrescreve endpoint/segredo; 3) restart
    if target == "aws":
        # o ID da conta não vai para o git: o overlay usa ACCOUNT_ID e a troca acontece só aqui, em memória
        acct = subprocess.run(["aws", "sts", "get-caller-identity", "--query", "Account", "--output", "text"],
                              env=tf_env("02-eks", target), capture_output=True, text=True, check=True).stdout.strip()
        rendered = subprocess.run(["kubectl", "kustomize", str(repo / "gitops" / "overlays" / target)],
                                  capture_output=True, text=True, check=True).stdout.replace("ACCOUNT_ID", acct)
        print("  $ kubectl kustomize gitops/overlays/aws | (ACCOUNT_ID -> conta) | kubectl apply -f -", flush=True)
        subprocess.run(["kubectl", "apply", "-f", "-"], input=rendered, text=True, env=env, check=True)
        if subprocess.run(["kubectl", "get", "secret", "retentiq-api-secrets", "-n", "ecosystem"], env=env, capture_output=True).returncode != 0:
            sh(["kubectl", "create", "secret", "generic", "retentiq-api-secrets", "-n", "ecosystem",
                f"--from-literal=JWT_SECRET={secrets.token_urlsafe(32)}"], env)
    else:
        sh(["kubectl", "apply", "-k", str(repo / "gitops" / "overlays" / target)], env)
    if target == "floci":
        # pods alcançam o floci pelo IP dele na rede docker floci_default (mesmo endpoint do mirror do k3s)
        ip = subprocess.run(["docker", "inspect", "-f", "{{(index .NetworkSettings.Networks \"floci_default\").IPAddress}}", "floci"],
                            capture_output=True, text=True, check=True).stdout.strip()
        cm = subprocess.run(["kubectl", "create", "configmap", "platform-env", "-n", "ecosystem", "--dry-run=client", "-o", "yaml",
                             f"--from-literal=AWS_ENDPOINT_URL=http://{ip}:4566", "--from-literal=AWS_ACCESS_KEY_ID=test",
                             "--from-literal=AWS_SECRET_ACCESS_KEY=test", "--from-literal=AWS_DEFAULT_REGION=us-east-1"],
                            env=env, capture_output=True, text=True, check=True).stdout
        subprocess.run(["kubectl", "apply", "-f", "-"], input=cm, text=True, env=env, check=True)
        # segredo de laboratório gerado na hora (nunca versionado)
        has = subprocess.run(["kubectl", "get", "secret", "retentiq-api-secrets", "-n", "ecosystem"], env=env, capture_output=True)
        if has.returncode != 0:
            sh(["kubectl", "create", "secret", "generic", "retentiq-api-secrets", "-n", "ecosystem",
                f"--from-literal=JWT_SECRET={secrets.token_urlsafe(32)}"], env)
        sh(["kubectl", "rollout", "restart", "deployment", "-n", "ecosystem"], env, check=False)
    sh(["kubectl", "rollout", "status", "deployment", "-n", "ecosystem", "--timeout=600s"], env, check=False)
    sh(["kubectl", "get", "pods", "-n", "ecosystem", "-o", "wide"], env, check=False)


def floci(cmd: str) -> None:
    compose = ROOT / "floci" / "docker-compose.yml"
    sh(["docker", "compose", "-f", str(compose), *(["up", "-d", "--wait"] if cmd == "up" else ["down"])])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["floci-up", "floci-down", "sync", "up", "plan", "down", "kubeconfig", "deploy", "status"])
    ap.add_argument("--target", choices=["free", "real", "floci", "aws"], default=os.environ.get("TARGET", "free"),
                    help="free = AWS emulada no floci (R$ 0, padrão) | real = AWS de verdade (créditos; exige --yes-real-aws)")
    ap.add_argument("--stacks", help="lista separada por vírgula (padrão: todas)")
    ap.add_argument("--yes-real-aws", action="store_true", help="obrigatório para --target real em up/down")
    a = ap.parse_args()
    a.target = {"free": "floci", "real": "aws"}.get(a.target, a.target)  # perfis envs/free e envs/real
    stacks = [s for s in STACKS if not a.stacks or s in a.stacks.split(",")]
    if a.target == "aws" and a.cmd in ("up", "down") and not a.yes_real_aws:
        sys.exit("TARGET=aws cria/destrói recursos REAIS (créditos). Revise o plano v0.2 e use --yes-real-aws.")
    if not shutil.which("terraform"):
        sys.exit("terraform não encontrado no PATH")
    if a.cmd == "floci-up":
        floci("up")
    elif a.cmd == "floci-down":
        floci("down")
    elif a.cmd == "sync":
        sync()
    elif a.cmd == "up":
        run("apply", stacks, a.target)
    elif a.cmd == "plan":
        run("plan", stacks, a.target)
    elif a.cmd == "down":
        run("destroy", stacks, a.target)
    elif a.cmd == "kubeconfig":
        kubeconfig(a.target)
    elif a.cmd == "deploy":
        deploy(a.target)
    elif a.cmd == "status":
        for s in stacks:
            print(f"## {s}: {json.dumps(outputs(s, a.target), ensure_ascii=False)[:600]}")


if __name__ == "__main__":
    main()
