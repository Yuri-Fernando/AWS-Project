#!/usr/bin/env python
"""Comunicação do Master com os repositórios do ecossistema (lê ecosystem/repos.json). stdlib only.

  python tools/repos.py status          # ref fixado x HEAD local x presença no ECO_DIR
  python tools/repos.py sync            # clona/atualiza cada repo de imagem/job no ref fixado em ECO_DIR
  python tools/repos.py pin [nome ...]  # grava o HEAD local atual como novo ref fixado

ECO_DIR (padrão D:\\Claude Temp\\staging\\eco) fica FORA da pasta sincronizada: builds e testes usam essas cópias;
o código-fonte de cada app continua no próprio repositório. Fonte do clone: pasta local irmã (se existir, inclui
commits ainda não enviados) senão o GitHub.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "ecosystem" / "repos.json"
SIBLINGS = ROOT.parent  # pasta "Projetos Extras (Portfolio)"
ECO = Path(os.environ.get("ECO_DIR", r"D:\Claude Temp\staging\eco" if Path("D:/").exists() else ROOT / ".eco"))


def git(*args: str, cwd: Path | None = None) -> str:
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def load() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def buildable(repos: dict) -> dict:
    return {k: v for k, v in repos.items() if v.get("how") in ("image", "job", "image+terraform")}


def status() -> None:
    repos = load()["repos"]
    print(f"{'repo':<12} {'como':<16} {'ref fixado':<10} {'HEAD local':<10} {'ECO_DIR':<10} papel")
    for name, r in repos.items():
        local = SIBLINGS / r["local"] if r.get("local") else None
        head = git("rev-parse", "HEAD", cwd=local)[:8] if local and local.exists() else "-"
        eco = git("rev-parse", "HEAD", cwd=ECO / name)[:8] if (ECO / name).exists() else "-"
        ref = (r.get("ref") or "")[:8] or ("submodule" if r.get("how") == "submodule" else "-")
        drift = " (desvio)" if r.get("ref") and head not in ("-", ref) else ""
        print(f"{name:<12} {r.get('how', ''):<16} {ref:<10} {head + drift:<10} {eco:<10} {r.get('role', '')[:60]}")


def sync() -> None:
    ECO.mkdir(parents=True, exist_ok=True)
    for name, r in buildable(load()["repos"]).items():
        dest = ECO / name
        local = SIBLINGS / r["local"] if r.get("local") else None
        src = f"file:///{local.as_posix()}" if local and local.exists() else r["github"]
        if not dest.exists():
            subprocess.run(["git", "clone", "-q", "--no-checkout", src, str(dest)], check=True)
        else:
            subprocess.run(["git", "-C", str(dest), "fetch", "-q", src, r.get("branch", "HEAD")], check=False)
        subprocess.run(["git", "-C", str(dest), "fetch", "-q", src, r["ref"]], check=False)
        rc = subprocess.run(["git", "-C", str(dest), "checkout", "-q", "--detach", r["ref"]]).returncode
        print(f"[{'ok' if rc == 0 else 'FALHA'}] {name} @ {r['ref'][:8]} <- {src[:80]}")


def pin(names: list[str]) -> None:
    data = load()
    for name, r in data["repos"].items():
        if r.get("ref") is None or (names and name not in names):
            continue
        local = SIBLINGS / r["local"]
        head = git("rev-parse", "HEAD", cwd=local)
        if head and head != r["ref"]:
            print(f"{name}: {r['ref'][:8]} -> {head[:8]}")
            r["ref"] = head
    MANIFEST.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    {"status": status, "sync": sync}.get(cmd, lambda: pin(sys.argv[2:]))() if cmd != "pin" else pin(sys.argv[2:])
