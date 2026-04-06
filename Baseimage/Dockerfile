FROM debian:bookworm-slim

LABEL org.opencontainers.image.title="rtl-sdr base" \
      org.opencontainers.image.description="RTL-SDR built from source (optional base for custom images)"

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      libusb-1.0-0-dev pkg-config ca-certificates git cmake build-essential && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /tmp

RUN echo 'blacklist dvb_usb_rtl28xxu' > /etc/modprobe.d/raspi-blacklist.conf && \
    git clone --depth 1 https://github.com/osmocom/rtl-sdr.git && \
    mkdir rtl-sdr/build && \
    cd rtl-sdr/build && \
    cmake ../ -DINSTALL_UDEV_RULES=ON -DDETACH_KERNEL_DRIVER=ON && \
    make && \
    make install && \
    ldconfig && \
    rm -rf /tmp/rtl-sdr

WORKDIR /
