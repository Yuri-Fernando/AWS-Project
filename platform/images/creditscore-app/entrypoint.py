"""Troca a URL fixa da API (AWS real, sa-east-1) pela de CREDITSCORE_API_URL e sobe o Streamlit."""
import os
import re
import sys
from pathlib import Path

src = Path("/app/App/app.py").read_text(encoding="utf-8")
url = os.environ.get("CREDITSCORE_API_URL")
if url:
    src = re.sub(r"https://[\w.-]+\.execute-api\.[\w-]+\.amazonaws\.com/\w+", url, src)
out = Path("/tmp/app.py")
out.write_text(src, encoding="utf-8")
os.execvp(sys.executable, [sys.executable, "-m", "streamlit", "run", str(out),
                           "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"])
