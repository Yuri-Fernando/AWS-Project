#!/usr/bin/env python
"""Ativa um perfil MCP do projeto: copia mcp/<perfil>.mcp.json para .mcp.json (gitignored) ou remove.

  python tools/mcp_profile.py free | real | off
"""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
profile = sys.argv[1] if len(sys.argv) > 1 else ""
target = ROOT / ".mcp.json"
if profile == "off":
    target.unlink(missing_ok=True)
    print("MCP do projeto desativado")
elif profile in ("free", "real"):
    shutil.copyfile(ROOT / "mcp" / f"{profile}.mcp.json", target)
    print(f"perfil MCP '{profile}' ativo em {target} — reabra o Claude Code e aprove os servidores")
else:
    sys.exit("uso: python tools/mcp_profile.py free | real | off")
