#!/usr/bin/env bash
set -uo pipefail

PURGAR=no
[ "${1:-}" = "--purge" ] && PURGAR=si

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
echo "Las reglas de ufw con el comentario media-bridge se quitan a mano: sudo ufw status numbered"
