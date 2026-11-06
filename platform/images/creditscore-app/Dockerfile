# Credit Score Predictor — front Streamlit. Contexto = raiz do repo Credit-Score-Predictor---AWS-Streamlit.
# O app tem a URL da API real (sa-east-1) fixa; entrypoint.py a troca por CREDITSCORE_API_URL em runtime
# (aponta para a API Gateway emulada no floci) sem alterar o repositório.
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY App/requirements.txt ./
RUN pip install -r requirements.txt
COPY App/ ./App/
COPY --from=platform entrypoint.py /entrypoint.py
RUN useradd -u 10001 -m app && chown -R app /app
USER app
EXPOSE 8501
CMD ["python", "/entrypoint.py"]
