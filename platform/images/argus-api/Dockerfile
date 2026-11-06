# Argus API (FastAPI) — imagem de laboratório. Contexto = raiz do repo Argus.
# Só as dependências alcançadas por api/main.py (análise de imports): sem torch/spark/LLM.
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN pip install "fastapi>=0.111" "uvicorn[standard]>=0.30" "pandas>=2.2" "pydantic>=2.7" "duckdb>=1.0" "pyyaml>=6.0" "pyarrow>=16.0"
COPY . .
RUN useradd -u 10001 -m app && chown -R app /app
USER app
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --retries=5 CMD python -c "import urllib.request,sys; urllib.request.urlopen('http://localhost:8000/health')" || exit 1
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
