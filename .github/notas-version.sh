#!/usr/bin/env bash
set -euo pipefail

version=${1:?Uso: notas-version.sh X.Y.Z}
changelog="${2:-CHANGELOG.md}"

notas=""
if [ -f "$changelog" ]; then
  notas=$(awk -v v="$version" '
    $0 == "## " v { dentro = 1; next }
    /^## / && dentro { exit }
    dentro { print }
  ' "$changelog" | sed '/./,$!d')
fi

if [ -n "$notas" ]; then
  printf '%s\n' "$notas"
else
  echo "No hay notas para $version en CHANGELOG.md."
fi
