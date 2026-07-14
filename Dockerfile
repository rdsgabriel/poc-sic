# ---- estágio 1: build do front React ----
FROM node:22-alpine AS front
WORKDIR /front
COPY front-end/package.json front-end/package-lock.json* ./
RUN npm install
COPY front-end/ .
RUN npm run build

# ---- estágio 2: API Python + front buildado ----
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/opt/hf-cache

WORKDIR /srv

# tesseract: OCR de tabelas que são imagem no PDF (layout Solstad)
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr tesseract-ocr-por \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app/ app/
COPY --from=front /front/dist front-end/dist

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
