#!/usr/bin/env python
"""Empacota a Lambda v3 do Credit-Score-Predictor (src/mlops/handler.py, inferência local com o modelo v3).

  python platform/serverless/package_creditscore.py [--repo D:\\...\\eco\\creditscore]
Gera <repo>/dist/lambda_v3.zip com: Nuvem/, src/ (pacote mlops), model_artifacts/riskcredit-v3/ e dependências
Linux (manylinux, Python 3.11) de numpy/pandas/xgboost-cpu — o repositório original não é alterado.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

DEPS = ["numpy<2.3", "pandas<2.3", "scipy<1.16"]
NODEPS = ["xgboost-cpu>=2.1"]
# xgboost.core faz `import scipy.sparse` no import; o resto do scipy (~70 MB) não é usado na inferência.
SCIPY_UNUSED = ["stats", "optimize", "signal", "interpolate", "integrate", "io", "ndimage", "spatial", "fft", "fftpack",
                "odr", "cluster", "datasets", "misc", "differentiate", "constants"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.environ.get("CREDITSCORE_REPO", r"D:\Claude Temp\staging\eco\creditscore"))
    a = ap.parse_args()
    repo = Path(a.repo)
    build = repo / "dist" / "lambda_build"
    shutil.rmtree(build, ignore_errors=True)
    build.mkdir(parents=True)
    pip = [sys.executable, "-m", "pip", "install", "--quiet", "--target", str(build), "--platform", "manylinux2014_x86_64",
           "--python-version", "3.11", "--implementation", "cp", "--only-binary=:all:", "--upgrade"]
    subprocess.run(pip + DEPS, check=True)
    subprocess.run(pip + ["--no-deps"] + NODEPS, check=True)
    for sub in SCIPY_UNUSED:
        shutil.rmtree(build / "scipy" / sub, ignore_errors=True)
    # Limite da AWS (e do floci): 50 MB por upload direto do zip. Remove o que não é usado em runtime.
    for pattern in ["**/tests", "**/test", "**/*.dist-info", "**/__pycache__", "**/include", "**/*.pyi",
                    "pandas/io/formats/templates", "xgboost/testing", "numpy/_pyinstaller"]:  # numpy.typing e numpy.f2py ficam: scipy os acessa no import
        for p in list(build.glob(pattern)):
            if p.relative_to(build).as_posix().startswith("numpy/_core/tests"):  # numpy.testing importa daqui
                continue
            shutil.rmtree(p, ignore_errors=True) if p.is_dir() else p.unlink(missing_ok=True)
    for d in ["Nuvem", "src", "model_artifacts/riskcredit-v3"]:
        shutil.copytree(repo / d, build / d, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "tests"))
    out = repo / "dist" / "lambda_v3.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for p in build.rglob("*"):
            if p.is_file() and "__pycache__" not in p.parts:
                z.write(p, p.relative_to(build).as_posix())
    print(f"{out} ({out.stat().st_size / 2**20:.1f} MB)")


if __name__ == "__main__":
    main()
