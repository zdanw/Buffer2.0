# Hugging Face Spaces (Docker SDK)
# https://huggingface.co/docs/hub/spaces-sdks-docker
#
# 将本目录（hf-space/）作为 Space 仓库根目录推送即可。
# 运行端口必须为 7860（或与 README 中 app_port 一致）。

FROM python:3.10-slim

RUN useradd -m -u 1000 user

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --chown=user:user requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY --chown=user:user bebcare/ ./bebcare/
COPY --chown=user:user scripts/ ./scripts/
COPY --chown=user:user migrations/ ./migrations/
COPY --chown=user:user alembic.ini ./
COPY --chown=user:user app.py ./
COPY --chown=user:user .env.example ./

# CLIP 扩展（默认 ENABLE_CLIP=false，不装 torch）：
# 1) 在上方 pip 后再: pip install -r requirements-clip.txt
# 2) COPY Long-CLIP/ ./Long-CLIP/ 并放入 checkpoints/longclip-B.pt
# 3) Space Secrets 设置 ENABLE_CLIP=true

RUN mkdir -p /app/chroma_data && chown -R user:user /app/chroma_data

USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    APP_PORT=7860

EXPOSE 7860

CMD ["uvicorn", "bebcare.main:app", "--host", "0.0.0.0", "--port", "7860"]
