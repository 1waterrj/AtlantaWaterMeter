FROM python:3.14-slim-trixie

LABEL org.opencontainers.image.title="AtlantaWaterMeter" \
      org.opencontainers.image.description="RTL-SDR water meter reader for Neptune R900"

RUN apt-get update && apt-get install -y --no-install-recommends \
      curl \
      git \
      mosquitto-clients \
      rtl-sdr \
      golang-go \
      ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ENV GOBIN=/usr/local/bin
RUN go install github.com/bemasher/rtlamr@latest

WORKDIR /app

COPY meter/ ./meter/
COPY scripts/ ./scripts/
RUN chmod +x scripts/*.sh

ENV PYTHONUNBUFFERED=1

CMD ["./scripts/daemon.sh"]
