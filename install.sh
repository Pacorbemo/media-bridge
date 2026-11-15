#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

BIN="$HOME/.local/bin"
SHARE="$HOME/.local/share/media-bridge"
UNITS="$HOME/.config/systemd/user"
CONF_DIR="$HOME/.config/media-bridge"
FIREWALL=no

for arg in "$@"; do
  case "$arg" in
    --firewall) FIREWALL=si ;;
    *) echo "Uso: ./install.sh [--firewall]"; exit 1 ;;
  esac
done

faltan=()
for cmd in ssh sshfs socat minidlnad python3 curl ss fusermount3; do
  command -v "$cmd" >/dev/null || faltan+=("$cmd")
done
if [ ${#faltan[@]} -gt 0 ]; then
  echo "Faltan programas: ${faltan[*]}"
  echo "  Arch:          sudo pacman -S --needed openssh sshfs socat minidlna python curl iproute2 fuse3"
  echo "  Debian/Ubuntu: sudo apt install openssh-client sshfs socat minidlna python3 curl iproute2 fuse3"
  echo "  Fedora:        sudo dnf install openssh-clients fuse-sshfs socat minidlna python3 curl iproute fuse3"
  exit 1
fi

install -Dm755 bin/medios "$BIN/medios"
install -Dm644 lib/buscar.py "$SHARE/buscar.py"
install -Dm644 completions/medios.zsh "$SHARE/medios.zsh"
install -Dm644 completions/medios.bash "$SHARE/medios.bash"
mkdir -p "$UNITS"
install -m644 systemd/* "$UNITS/"
systemctl --user daemon-reload

if [ ! -f "$CONF_DIR/config" ]; then
  install -Dm644 config.example "$CONF_DIR/config"
  nueva_conf=si
else
  nueva_conf=no
fi

case "$(basename "${SHELL:-}")" in
  zsh) rc="$HOME/.zshrc"; linea="source $SHARE/medios.zsh" ;;
  bash) rc="$HOME/.bashrc"; linea="source $SHARE/medios.bash" ;;
  *) rc="" ;;
esac
if [ -n "$rc" ] && ! grep -qF "$linea" "$rc" 2>/dev/null; then
  printf '\n%s\n' "$linea" >> "$rc"
  echo "Autocompletado añadido a $rc (abre una terminal nueva)"
fi

if systemctl is-enabled minidlna.service >/dev/null 2>&1; then
  echo "Aviso: el servicio minidlna del sistema está activado y puede chocar en el puerto 8200."
  echo "  Desactívalo con: sudo systemctl disable --now minidlna.service"
fi

# shellcheck source=/dev/null
source "$CONF_DIR/config"
puertos=()
for p in ${REENVIOS:-}; do puertos+=("$p/tcp"); done
if [ "${DLNA:-si}" = si ]; then puertos+=("${PUERTO_DLNA:-8200}/tcp" "1900/udp"); fi
reglas=()
for p in "${puertos[@]}"; do
  for red in 192.168.0.0/16 10.0.0.0/8 172.16.0.0/12; do
    reglas+=("ufw allow from $red to any port ${p%/*} proto ${p#*/} comment media-bridge")
  done
done
if [ "$FIREWALL" = si ]; then
  # shellcheck disable=SC2086
  for r in "${reglas[@]}"; do sudo $r; done
elif command -v ufw >/dev/null && [ ${#reglas[@]} -gt 0 ]; then
  echo "Si usas ufw, abre los puertos solo a la red local con ./install.sh --firewall o con:"
  for r in "${reglas[@]}"; do echo "  sudo $r"; done
fi

case ":$PATH:" in
  *":$BIN:"*) ;;
  *) echo "Aviso: $BIN no está en tu PATH" ;;
esac

echo
echo "Instalado."
if [ "$nueva_conf" = si ]; then
  echo "Edita $CONF_DIR/config con los datos de tu servidor y luego: medios on"
else
  echo "Se mantiene tu configuración en $CONF_DIR/config. Enciéndelo con: medios on"
fi
