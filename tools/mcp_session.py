#!/usr/bin/env python
"""Sessão temporária do MCP na AWS real: resolve o MFA ANTES de abrir o Claude Code.

  python tools/mcp_session.py            # pede o código de 6 dígitos do MFA (digitado por você, no terminal)
  python tools/mcp_session.py --status   # mostra quando a sessão expira

Por quê: as roles do projeto (stack 06-identity) exigem MFA, e um servidor MCP roda sem terminal — não tem como
pedir o código. Este script assume a role SOMENTE LEITURA `argus-platform-lab-mcp-readonly` com o MFA do seu usuário
e grava as credenciais temporárias (1 h) no perfil `argus-lab-mcp` do ~/.aws/credentials. O `mcp/real.mcp.json`
usa esse perfil. Nenhuma credencial é impressa nem versionada; ao expirar, basta rodar de novo.
Pré-requisito: perfil `argus-lab-readonly` em ~/.aws/config (envs/real/aws-config.example), com role_arn,
source_profile e mfa_serial.
"""
from __future__ import annotations

import argparse
import configparser
import getpass
import json
import os
import subprocess
import sys
from pathlib import Path

SOURCE = os.environ.get("MCP_SOURCE_PROFILE", "argus-lab-readonly")  # perfil com role_arn + mfa_serial
TARGET = os.environ.get("MCP_SESSION_PROFILE", "argus-lab-mcp")      # perfil que o MCP usa
AWS_DIR = Path.home() / ".aws"


def read_profile(name: str) -> dict:
    cfg = configparser.RawConfigParser()
    cfg.read(AWS_DIR / "config", encoding="utf-8")
    section = f"profile {name}"
    if not cfg.has_section(section):
        sys.exit(f"perfil '{name}' não existe em ~/.aws/config (ver envs/real/aws-config.example)")
    return dict(cfg.items(section))


def aws_set(key: str, value: str) -> None:
    subprocess.run(["aws", "configure", "set", key, value, "--profile", TARGET], check=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--duration", type=int, default=3600, help="segundos (máx. da role: 3600)")
    a = ap.parse_args()
    if a.status:
        cfg = configparser.RawConfigParser()
        cfg.read(AWS_DIR / "credentials", encoding="utf-8")
        print(f"{TARGET}: expira em {cfg.get(TARGET, 'x_expiration', fallback='(sem sessão)')}")
        return
    prof = read_profile(SOURCE)
    for k in ("role_arn", "source_profile", "mfa_serial"):
        if k not in prof:
            sys.exit(f"perfil '{SOURCE}' sem '{k}'")
    code = getpass.getpass("Código MFA (6 dígitos, não aparece na tela): ").strip()
    if not (code.isdigit() and len(code) == 6):
        sys.exit("código inválido")
    r = subprocess.run(["aws", "sts", "assume-role", "--role-arn", prof["role_arn"], "--role-session-name", "argus-mcp",
                        "--serial-number", prof["mfa_serial"], "--token-code", code, "--duration-seconds", str(a.duration),
                        "--profile", prof["source_profile"], "--output", "json"], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"assume-role falhou: {r.stderr.strip()[:300]}")
    c = json.loads(r.stdout)["Credentials"]
    aws_set("aws_access_key_id", c["AccessKeyId"])
    aws_set("aws_secret_access_key", c["SecretAccessKey"])
    aws_set("aws_session_token", c["SessionToken"])
    aws_set("region", prof.get("region", "us-east-1"))
    aws_set("x_expiration", c["Expiration"])
    print(f"ok: perfil '{TARGET}' válido até {c['Expiration']} (role somente leitura). Abra o Claude Code com o perfil MCP 'real'.")


if __name__ == "__main__":
    main()
