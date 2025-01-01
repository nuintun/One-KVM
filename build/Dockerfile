FROM silentwind0/kvmd-stage-0 AS builder

FROM python:3.12.0rc2-slim-bookworm

LABEL maintainer="mofeng654321@hotmail.com"

COPY --from=builder /tmp/lib/* /tmp/lib/
COPY --from=builder /tmp/ustreamer/ustreamer /tmp/ustreamer/ustreamer-dump /usr/bin/janus /usr/bin/
COPY --from=builder /tmp/wheel/*.whl /tmp/wheel/
COPY --from=builder /tmp/ustreamer/libjanus_ustreamer.so /usr/lib/ustreamer/janus/
COPY --from=builder /usr/lib/janus/transports/* /usr/lib/janus/transports/

ARG TARGETARCH

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV TZ=Asia/Shanghai

RUN cp /tmp/lib/* /lib/*-linux-*/ \
    && pip install --no-cache-dir --root-user-action=ignore --disable-pip-version-check /tmp/wheel/*.whl \
    && pip install --no-cache-dir --root-user-action=ignore --disable-pip-version-check pyfatfs \
    && rm -rf /tmp/lib /tmp/wheel

RUN sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/' /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends libxkbcommon-x11-0 nginx tesseract-ocr tesseract-ocr-eng tesseract-ocr-chi-sim iptables sudo  curl kmod \
        libmicrohttpd12 libjansson4 libssl3 libsofia-sip-ua0 libglib2.0-0 libopus0 libogg0 libcurl4 libconfig9 libusrsctp2 libwebsockets17 libnss3 libasound2 nano \
    && rm -rf /var/lib/apt/lists/*

RUN if [ ${TARGETARCH} = arm ]; then ARCH=armhf; elif [ ${TARGETARCH} = arm64 ]; then ARCH=aarch64; elif [ ${TARGETARCH} = amd64 ]; then ARCH=x86_64; fi \
    && curl https://github.com/tsl0922/ttyd/releases/download/1.7.7/ttyd.$ARCH -L -o /usr/local/bin/ttyd \
    && chmod +x /usr/local/bin/ttyd \
    && ln -sf /usr/share/tesseract-ocr/*/tessdata /usr/share/tessdata


COPY . /One-KVM

ENTRYPOINT ["bash"]