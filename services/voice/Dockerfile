# VieNeu runs separately from the API because its Python dependencies differ.
FROM python:3.11-slim-bookworm
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 HF_HUB_CACHE=/data/huggingface/hub VOICE_HOST=0.0.0.0
RUN apt-get update && apt-get install -y --no-install-recommends libsndfile1 espeak-ng && rm -rf /var/lib/apt/lists/*
WORKDIR /app/services/voice
COPY services/voice/requirements.txt services/voice/constraints.txt ./
RUN pip install -c constraints.txt -r requirements.txt && pip check
COPY services/voice/server.py ./
RUN useradd --system --create-home --uid 10001 cavat && mkdir -p /data/huggingface && chown cavat:cavat /data/huggingface
USER cavat
EXPOSE 8010
CMD ["python", "server.py"]
