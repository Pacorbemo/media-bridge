#!/usr/bin/env bash
set -uo pipefail

PURGAR=no
FIREWALL=no
for arg in "$@"; do
  case "$arg" in
    --purge) PURGAR=si ;;
    --firewall) FIREWALL=si ;;
    *) echo "Uso: ./uninstall.sh [--purge] [--firewall]"; exit 1 ;;
  esac
done

numeros_reglas() {
  sed -nE 's/^\[ *([0-9]+)\].*# media-bridge( .*)?$/\1/p' | sort -rn
}

systemctl --user stop 'media-bridge-*' 2>/dev/null
rm -f "$HOME/.config/systemd/user/media-bridge-"*
systemctl --user daemon-reload
rm -f "$HOME/.local/bin/medios"
rm -rf "$HOME/.local/share/media-bridge"

for rc in "$HOME/.zshrc" "$HOME/.bashrc"; do
  [ -f "$rc" ] && sed -i '\|/.local/share/media-bridge/medios\.|d' "$rc"
done

if [ "$PURGAR" = si ]; then
  rm -rf "$HOME/.config/media-bridge" "$HOME/.cache/media-bridge"
  echo "Desinstalado, con configuración e índice del DLNA."
else
  echo "Desinstalado. Se mantienen ~/.config/media-bridge y el índice del DLNA (usa --purge para borrarlos)."
fi

if [ "$FIREWALL" = si ]; then
  if ! command -v ufw >/dev/null; then
    echo "No hay ufw instalado: no hay reglas que quitar."
    exit 0
  fi
  echo "Quitando las reglas de ufw con el comentario media-bridge (pide la contraseña de sudo):"
  numeros=$(sudo ufw status numbered | numeros_reglas)
  if [ -z "$numeros" ]; then
    echo "No había ninguna."
  else
    for n in $numeros; do
      sudo ufw --force delete "$n" >/dev/null && echo "  Regla $n quitada"
    done
  fi
else
  echo "Las reglas de ufw con el comentario media-bridge se quitan con: ./uninstall.sh --firewall"
fi
