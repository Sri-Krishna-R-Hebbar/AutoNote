# --- Stage 1: build the React frontend ---
FROM node:20-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- Stage 2: Python app serving the API + built frontend ---
FROM python:3.11-slim
WORKDIR /app

# libgomp1 is required by faster-whisper's CTranslate2 backend on Debian slim images.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

RUN mkdir -p uploads processed_notes

# Pre-download the local Whisper model at build time so the first real
# request doesn't have to wait on a Hugging Face download.
ARG WHISPER_MODEL_SIZE=base
ENV WHISPER_MODEL_SIZE=${WHISPER_MODEL_SIZE}
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('${WHISPER_MODEL_SIZE}', device='cpu', compute_type='int8')"

EXPOSE 5000
CMD ["gunicorn", "app:app", "--workers", "1", "--threads", "8", "--timeout", "120", "--bind", "0.0.0.0:5000"]
