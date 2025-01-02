# syntax = docker/dockerfile:experimental
FROM python:3.12.8-slim-bookworm AS builder

ARG TARGETARCH

RUN sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/' /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends build-essential libssl-dev libffi-dev python3-dev libevent-dev libjpeg-dev \
        libbsd-dev libudev-dev git pkg-config wget curl libmicrohttpd-dev libjansson-dev libssl-dev libsofia-sip-ua-dev \
        libopus-dev libogg-dev libcurl4-openssl-dev liblua5.3-dev libconfig-dev libopus-dev libtool automake autoconf \
        libx264-dev libyuv-dev libasound2-dev  libspeex-dev libspeexdsp-dev libopus-dev libgpiod-dev libsystemd-dev \
        libglib2.0-dev libwebsockets-dev libsrtp2-dev libnice-dev patchelf libxkbcommon0 sudo iproute2 iptables libusb-dev \
    && rm -rf /var/lib/apt/lists/*

COPY build/cargo_config /tmp/config

RUN --security=insecure pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple \
    && if [ ${TARGETARCH} = arm ]; then \
        mkdir -p /root/.cargo \
        && chmod 777 /root/.cargo && mount -t tmpfs none /root/.cargo \
        && export RUSTUP_DIST_SERVER="https://mirrors.tuna.tsinghua.edu.cn/rustup" \
        #&& export RUSTUP_UPDATE_ROOT="https://mirrors.ustc.edu.cn/rust-static/rustup" \
        && wget  https://sh.rustup.rs -O /root/rustup-init.sh \
        && sh /root/rustup-init.sh -y \
        && export PATH=$PATH:/root/.cargo/bin \
        && cp /tmp/config /root/.cargo/config.toml; \
    fi \
    && pip install cryptography

RUN pip install --no-cache-dir --root-user-action=ignore --disable-pip-version-check build nuitka \
    && pip install --no-cache-dir aiofiles aiohttp appdirs asn1crypto async_lru async-timeout bottle cffi chardet click colorama \
        dbus_next gpiod hidapi idna mako marshmallow more-itertools multidict netifaces packaging passlib pillow ply psutil pycparser \
        pyelftools pyghmi pygments pyparsing pyotp qrcode requests semantic-version setproctitle setuptools six spidev  \
        tabulate urllib3 wrapt xlib yarl pyserial pyyaml zstandard supervisor

RUN git clone --depth=1 https://github.com/meetecho/janus-gateway.git /tmp/janus-gateway \
    && cd /tmp/janus-gateway \
    && bash autogen.sh \
    && ./configure --enable-static --enable-websockets  --enable-plugin-audiobridge \
        --disable-data-channels --disable-rabbitmq --disable-mqtt --disable-all-plugins --disable-all-loggers \
        --prefix=/usr \
    && make && make install

RUN sed --in-place --expression 's|^#include "refcount.h"$|#include "../refcount.h"|g' /usr/include/janus/plugins/plugin.h \
    && git clone --depth=1 https://github.com/mofeng-git/ustreamer /tmp/ustreamer \
    && make clean -C /tmp/ustreamer \
    && make WITH_GPIO=1 WITH_JANUS=1 WITH_PYTHON=1 WITH_LIBX264=1 WITH_SETPROCTITLE=0 -C /tmp/ustreamer install 

COPY kvmd /One-KVM/kvmd
COPY kvmd-launcher.py /One-KVM/

RUN bash -c "cd /One-KVM && ls && python3 -m nuitka kvmd-launcher.py --standalone --onefile \
--show-progress --no-deployment-flag=self-execution --include-module=\
kvmd.plugins.auth.htpasswd,kvmd.plugins.auth.http,kvmd.plugins.auth.ldap,\
kvmd.plugins.auth.pam,kvmd.plugins.auth.radius,\
kvmd.plugins.hid.ch9329,kvmd.plugins.hid.bt,kvmd.plugins.hid.otg,\
kvmd.plugins.atx.disabled,kvmd.plugins.atx.gpio,\
kvmd.plugins.msd.disabled,kvmd.plugins.msd.otg,\
kvmd.plugins.ugpio.gpio,kvmd.plugins.ugpio.wol,kvmd.plugins.ugpio.cmd,\
kvmd.plugins.ugpio.ipmi,kvmd.plugins.ugpio.anelpwr,kvmd.plugins.ugpio.cmdret,\
kvmd.plugins.ugpio.extron,kvmd.plugins.ugpio.ezcoo,kvmd.plugins.ugpio.hidrelay,\
kvmd.plugins.ugpio.hue,kvmd.plugins.ugpio.locator,kvmd.plugins.ugpio.noyito,\
kvmd.plugins.ugpio.otgconf,kvmd.plugins.ugpio.pway,kvmd.plugins.ugpio.pwm,\
kvmd.plugins.ugpio.servo,kvmd.plugins.ugpio.tesmart,kvmd.plugins.ugpio.xh_hk4401,\
passlib.handlers.sha1_crypt,pygments.formatters.terminal"

COPY kvmd_data /One-KVM/kvmd_data
RUN cp /usr/local/bin/ustreamer /usr/local/bin/ustreamer-dump /One-KVM/kvmd_data/usr/bin \
    && cd /One-KVM && python3 -m kvmd.apps.kvmd -m -c kvmd_data/etc/kvmd/main.yaml

FROM debian:stable-slim

COPY --from=builder /One-KVM/kvmd_data kvmd_data
COPY --from=builder /One-KVM/kvmd-launcher.bin kvmd-launcher.bin

RUN sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/' /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y libxkbcommon0 sudo iproute2 iptables nano \
    && rm -rf /var/lib/apt/lists/*

ENTRYPOINT [ "/kvmd-launcher.bin" ]
#RUN cd /One-KVM && /One-KVM/kvmd-launcher.bin