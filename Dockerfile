FROM python:3.14-slim-trixie

LABEL org.opencontainers.image.title="AtlantaWaterMeter" \
      org.opencontainers.image.description="RTL-SDR water meter reader for Neptune R900"

RUN apt-get update && apt-get install -y --no-install-recommends \
      curl \
      git \
      rtl-sdr \
      golang-go \
      ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ENV GOBIN=/usr/local/bin
RUN go install github.com/bemasher/rtlamr@v0.9.4

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY meter/ ./meter/

ENV PYTHONUNBUFFERED=1

HEALTHCHECK --interval=2m --timeout=15s --start-period=5m --retries=3 \
  CMD python3 -m meter.healthcheck

CMD ["python3", "-m", "meter.daemon"]
