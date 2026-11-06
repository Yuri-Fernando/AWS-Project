# RiskCredit — job de treino (champion/challenger v3) que publica o artefato aprovado no S3 (floci ou AWS).
# Contexto = raiz do repo RiskCredit. Roda como Kubernetes Job.
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 MPLBACKEND=Agg
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
RUN pip install $(grep -iE '^(numpy|pandas|scipy|scikit-learn|xgboost|lightgbm|pyyaml|matplotlib|joblib|shap|seaborn|reportlab)([<>=~!\[ ]|$)' requirements.txt | tr '\n' ' ') boto3
COPY . .
COPY --from=platform publish.py /publish.py
RUN useradd -u 10001 -m app && chown -R app /app
USER app
CMD ["sh", "-c", "python run_pipeline_v3.py && python /publish.py"]
