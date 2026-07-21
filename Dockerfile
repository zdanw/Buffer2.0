# Hugging Face Spaces (Docker SDK)
# 文档: https://huggingface.co/docs/hub/spaces-sdks-docker
#
# Space 只识别仓库【根目录】的 Dockerfile 与 README.md（sdk: docker）。
# 应用代码从 hf-space/ 复制进镜像。

FROM python:3.10-slim

RUN useradd -m -u 1000 user

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY hf-space/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY --chown=user:user hf-space/bebcare/ ./bebcare/
COPY --chown=user:user hf-space/scripts/ ./scripts/
COPY --chown=user:user hf-space/migrations/ ./migrations/
COPY --chown=user:user hf-space/alembic.ini ./
COPY --chown=user:user hf-space/app.py ./
COPY --chown=user:user hf-space/.env.example ./

RUN mkdir -p /app/chroma_data && chown -R user:user /app/chroma_data

USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    APP_PORT=7860

EXPOSE 7860

CMD ["uvicorn", "bebcare.main:app", "--host", "0.0.0.0", "--port", "7860"]
