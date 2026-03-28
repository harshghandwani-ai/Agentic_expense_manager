# syntax=docker/dockerfile:1

# ── Base image ────────────────────────────────────────────────────────────────
FROM python:3.11-slim

# ── System dependencies for PaddleOCR / OpenCV ───────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        swig \
        libgl1 \
        libglib2.0-0 \
        libsm6 \
        libxrender1 \
        libxext6 \
        libgomp1 \
        wget \
    && rm -rf /var/lib/apt/lists/*

# ── Working directory ─────────────────────────────────────────────────────────
WORKDIR /app

# ── Python dependencies (cached layer unless requirements.txt changes) ────────
COPY requirements.txt .
# GCC 14 (Debian Trixie) promotes -Wincompatible-pointer-types to an error,
# which breaks PyMuPDF < 1.21.0 (required by paddleocr 2.6.1.3).
ENV CFLAGS="-Wno-error=incompatible-pointer-types"
RUN pip install --no-cache-dir -r requirements.txt

# ── Application code ──────────────────────────────────────────────────────────
COPY . .

# ── Pre-download PaddleOCR model weights at build time ────────────────────────
# This bakes the models into the image so the first request is fast.
# Models are downloaded to ~/.paddleocr/
RUN python -c "\
from paddleocr import PaddleOCR; \
PaddleOCR(use_angle_cls=True, lang='en', use_gpu=False, show_log=False)" \
    || echo "WARNING: PaddleOCR model pre-download failed, will download on first request."

# ── Create uploads directory ──────────────────────────────────────────────────
RUN mkdir -p /app/uploads

# ── Port — Hugging Face Spaces requires 7860 ─────────────────────────────────
EXPOSE 7860

# ── Start server ──────────────────────────────────────────────────────────────
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
