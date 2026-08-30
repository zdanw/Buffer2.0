# Hugging Face Spaces (Docker SDK)
# 文档: https://huggingface.co/docs/hub/spaces-sdks-docker
#
# Space 只识别仓库【根目录】的 Dockerfile 与 README.md（sdk: docker）。
# 生产应用代码从 canonical backend/ 复制进镜像（不再从 hf-space/ 部署业务代码）。
# hf-space/ 保留为历史部署副本；回滚使用此前已部署的 HF 镜像。

FROM python:3.10-slim

RUN useradd -m -u 1000 user

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY --chown=user:user backend/bebcare/ ./bebcare/
COPY --chown=user:user backend/scripts/ ./scripts/
COPY --chown=user:user backend/migrations/ ./migrations/
COPY --chown=user:user backend/alembic.ini ./
COPY --chown=user:user backend/app.py ./
COPY --chown=user:user backend/.env.example ./

RUN mkdir -p /app/chroma_data && chown -R user:user /app/chroma_data

USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    APP_PORT=7860

EXPOSE 7860

CMD ["uvicorn", "bebcare.main:app", "--host", "0.0.0.0", "--port", "7860"]
