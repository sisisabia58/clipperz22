FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DATA_DIR=/app/data

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
      ca-certificates \
      ffmpeg \
      libglib2.0-0 \
      libgl1 \
      libgomp1 \
      fontconfig \
      fonts-dejavu-core \
      fonts-dejavu \
      fonts-liberation \
      fonts-noto-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

COPY . .
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh \
    && mkdir -p /app/data/outputs /app/data/uploads

EXPOSE 8010

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["python", "-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8010"]
