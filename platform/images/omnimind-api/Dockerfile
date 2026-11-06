# OmniMind AI OS — API de agentes (/ask). Contexto = raiz do repo OmniMind_AI_OS.
# Sem whisper/ffmpeg/sentence-transformers (fora do caminho de api/server.py). /ask exige chave de LLM via Secret.
FROM python:3.10-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN pip install "fastapi" "uvicorn[standard]" "langgraph" "langchain-openai" "langchain-anthropic" "langchain-community" "python-dotenv" "requests"
COPY . .
RUN useradd -u 10001 -m app && chown -R app /app
USER app
EXPOSE 8000
CMD ["uvicorn", "api.server:app", "--host", "0.0.0.0", "--port", "8000"]
