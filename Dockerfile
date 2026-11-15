FROM alpine:3.20

RUN apk add --no-cache bash openssh-client sshfs fuse3 socat minidlna python3 curl iproute2 iproute2-ss procps-ng

RUN printf 'Host *\n    StrictHostKeyChecking accept-new\n    UserKnownHostsFile /data/known_hosts\n    IdentityFile /ssh/clave\n' >> /etc/ssh/ssh_config

COPY bin/medios /usr/local/bin/medios
COPY lib/buscar.py /usr/local/share/media-bridge/buscar.py
COPY lib/descubrimiento.py /usr/local/share/media-bridge/descubrimiento.py
COPY lib/recientes.py /usr/local/share/media-bridge/recientes.py
COPY VERSION /usr/local/share/media-bridge/VERSION
COPY docker/entrypoint.sh /usr/local/bin/media-bridge-entrypoint

ENV MEDIA_BRIDGE_DOCKER=1 \
    MEDIA_BRIDGE_CONFIG=/run/media-bridge.conf \
    MEDIA_BRIDGE_SHARE=/usr/local/share/media-bridge

VOLUME /data
ENTRYPOINT ["/usr/local/bin/media-bridge-entrypoint"]
