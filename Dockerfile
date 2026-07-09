FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY backend/bebcare/ ./bebcare/
COPY backend/Long-CLIP/ ./Long-CLIP/
COPY backend/scripts/ ./scripts/
COPY backend/.env.example ./

RUN mkdir -p /app/chroma_data /app/Long-CLIP/checkpoints

RUN if [ ! -f /app/Long-CLIP/checkpoints/longclip-B.pt ]; then \
    echo "Downloading Long-CLIP model checkpoint..."; \
    curl -L -o /app/Long-CLIP/checkpoints/longclip-B.pt \
    "https://huggingface.co/bebcare/longclip/resolve/main/longclip-B.pt" || \
    (echo "Failed to download Long-CLIP, will use fallback CLIP"; exit 0); \
    fi

EXPOSE 7860

CMD ["uvicorn", "bebcare.main:app", "--host", "0.0.0.0", "--port", "7860"]