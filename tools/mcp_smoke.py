#!/usr/bin/env python
"""Teste de fumaça dos servidores MCP de um perfil (mcp/<perfil>.mcp.json), via protocolo stdio (JSON-RPC 2.0).

  python tools/mcp_smoke.py free [--only aws-api-floci,eks-floci] [--timeout 240]

Para cada servidor: sobe o processo com o env do perfil, faz initialize -> tools/list -> chama UMA ferramenta de
leitura conhecida (quando existe) e mostra o resultado resumido. Não altera nada (chamadas só de leitura).
Relatório em platform/.state/mcp-smoke-<perfil>.json.
"""
from __future__ import annotations

import argparse
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]

# chamada de leitura por ferramenta (primeira que existir no servidor)
READ_CALLS = [
    ("aws___search_documentation", {"search_phrase": "EKS Pod Identity association", "limit": 2}),
    ("call_aws", {"cli_command": "aws ec2 describe-vpcs --region us-east-1"}),
    ("list_k8s_resources", {"cluster_name": "argus-platform-lab-eks", "kind": "Pod", "api_version": "v1", "namespace": "ecosystem"}),
    ("search_documentation", {"search_phrase": "EKS Pod Identity", "limit": 2}),
    ("search_providers", {"provider_name": "aws", "provider_namespace": "hashicorp", "service_slug": "eks_cluster",
                          "provider_data_type": "resources", "provider_version": "latest"}),
]


class Client:
    def __init__(self, cmd: list[str], env: dict):
        exe = shutil.which(cmd[0]) or cmd[0]
        self.p = subprocess.Popen([exe, *cmd[1:]], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, env=env, text=True, encoding="utf-8", bufsize=1)
        self.q: queue.Queue = queue.Queue()
        self.err: list[str] = []
        threading.Thread(target=self._read, daemon=True).start()
        threading.Thread(target=self._read_err, daemon=True).start()
        self.n = 0

    def _read(self):
        for line in self.p.stdout:
            line = line.strip()
            if line.startswith("{"):
                try:
                    self.q.put(json.loads(line))
                except json.JSONDecodeError:
                    pass

    def _read_err(self):
        for line in self.p.stderr:
            self.err.append(line.rstrip())
            del self.err[:-40]

    def request(self, method: str, params: dict, timeout: float) -> dict:
        self.n += 1
        rid = self.n
        self.p.stdin.write(json.dumps({"jsonrpc": "2.0", "id": rid, "method": method, "params": params}) + "\n")
        self.p.stdin.flush()
        end = time.time() + timeout
        while time.time() < end:
            try:
                msg = self.q.get(timeout=1)
            except queue.Empty:
                if self.p.poll() is not None:
                    raise RuntimeError(f"processo saiu ({self.p.returncode}): {' | '.join(self.err[-5:])}")
                continue
            if msg.get("id") == rid:
                if "error" in msg:
                    raise RuntimeError(json.dumps(msg["error"])[:400])
                return msg.get("result", {})
        raise TimeoutError(f"{method} sem resposta em {timeout:.0f}s; stderr: {' | '.join(self.err[-3:])}")

    def notify(self, method: str):
        self.p.stdin.write(json.dumps({"jsonrpc": "2.0", "method": method}) + "\n")
        self.p.stdin.flush()

    def close(self):
        try:
            self.p.kill()
        except Exception:
            pass


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("profile", choices=["free", "real", "agent-toolkit"])
    ap.add_argument("--only")
    ap.add_argument("--timeout", type=float, default=240)
    a = ap.parse_args()
    cfg = json.loads((ROOT / "mcp" / f"{a.profile}.mcp.json").read_text(encoding="utf-8"))["mcpServers"]
    report = {}
    for name, srv in cfg.items():
        if a.only and name not in a.only.split(","):
            continue
        env = {**os.environ, **srv.get("env", {})}
        print(f"\n=== {name}: {srv['command']} {' '.join(srv.get('args', []))}", flush=True)
        c = Client([srv["command"], *srv.get("args", [])], env)
        r = {"ok": False}
        try:
            init = c.request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                            "clientInfo": {"name": "mcp-smoke", "version": "0.1"}}, a.timeout)
            c.notify("notifications/initialized")
            tools = [t["name"] for t in c.request("tools/list", {}, 60).get("tools", [])]
            r.update(server=init.get("serverInfo", {}), tools=tools)
            print(f"  servidor {init.get('serverInfo', {}).get('name')} {init.get('serverInfo', {}).get('version', '')} — {len(tools)} ferramentas", flush=True)
            print(f"  {', '.join(tools[:14])}{' …' if len(tools) > 14 else ''}", flush=True)
            call = next(((t, args) for t, args in READ_CALLS if t in tools), None)
            if call:
                res = c.request("tools/call", {"name": call[0], "arguments": call[1]}, 180)
                text = " ".join(x.get("text", "") for x in res.get("content", []) if isinstance(x, dict))
                r.update(call=call[0], is_error=res.get("isError", False), sample=text[:600])
                print(f"  chamada {call[0]} -> {'ERRO' if res.get('isError') else 'ok'}: {text[:400].replace(chr(10), ' ')}", flush=True)
                r["ok"] = not res.get("isError", False)
            else:
                r["ok"] = True
        except Exception as e:
            r["error"] = f"{type(e).__name__}: {e}"[:600]
            print(f"  FALHA: {r['error']}", flush=True)
        finally:
            c.close()
        report[name] = r
    out = ROOT / "platform" / ".state" / f"mcp-smoke-{a.profile}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = sum(1 for v in report.values() if v.get("ok"))
    print(f"\n{ok}/{len(report)} servidores OK -> {out}")


if __name__ == "__main__":
    main()
