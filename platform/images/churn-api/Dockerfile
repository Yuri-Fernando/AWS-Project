# Churn Intelligence — serving do modelo (FastAPI). Contexto = raiz do repo Churn_intelligence.
# Mantém as versões fixadas no requirements.txt do repo para os pacotes do caminho da API (compatibilidade do .pkl).
FROM python:3.10-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install $(grep -iE '^(pandas|numpy|scikit-learn|joblib|fastapi|uvicorn|pydantic)([<>=~!\[ ]|$)' requirements.txt | tr '\n' ' ')
COPY src/ ./src/
COPY models/ ./models/
COPY data/processed/ ./data/processed/
RUN useradd -u 10001 -m app && chown -R app /app
USER app
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --retries=5 CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1
CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
