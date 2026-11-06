# ThemisAI — Governance Copilot API (policy gate PII/LGPD). Contexto = raiz do repo ThemisAI.
# requirements-core apenas: spacy/chromadb/sentence-transformers são importados sob demanda (não no caminho da API).
FROM python:3.10-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements-core.txt ./
RUN pip install -r requirements-core.txt
COPY . .
RUN useradd -u 10001 -m app && chown -R app /app
USER app
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --retries=5 CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1
CMD ["uvicorn", "core.governance_copilot:app", "--host", "0.0.0.0", "--port", "8000"]
