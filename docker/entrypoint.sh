#!/usr/bin/env bash
set -uo pipefail

for v in SERVIDOR USUARIO_SSH RUTA_MEDIOS CARPETAS; do
  if [ -z "${!v:-}" ]; then
    echo "Falta la variable $v en media-bridge.env"
    exit 1
  fi
done
if [ ! -r /ssh/clave ]; then
  echo "No encuentro la clave SSH en /ssh/clave: revisa el volumen en compose.yaml"
  exit 1
fi

{
  printf 'SERVIDOR=%q\n' "$SERVIDOR"
  printf 'USUARIO_SSH=%q\n' "$USUARIO_SSH"
  printf 'RUTA_MEDIOS=%q\n' "$RUTA_MEDIOS"
  printf 'CARPETAS=('
  IFS=',' read -ra lista <<< "$CARPETAS"
  for c in "${lista[@]}"; do
    c="${c#"${c%%[![:space:]]*}"}"
    c="${c%"${c##*[![:space:]]}"}"
    [ -n "$c" ] && printf '%q ' "$c"
  done
  printf ')\n'
  printf 'REENVIOS=%q\n' "${REENVIOS//,/ }"
  printf 'DLNA=%q\n' "${DLNA:-si}"
  printf 'NOMBRE_DLNA=%q\n' "${NOMBRE_DLNA:-media-bridge}"
  printf 'PUERTO_DLNA=%q\n' "${PUERTO_DLNA:-8200}"
  printf 'INTERFAZ=%q\n' "${INTERFAZ:-}"
  printf 'PUNTO_MONTAJE=/media\n'
  printf 'DB_DLNA=/data/dlna\n'
  printf 'EXTENSIONES=%q\n' "${EXTENSIONES:-mkv mp4 avi m4v mov wmv mpg mpeg ts webm}"
  printf 'REESCANEO_SEGUNDOS=%q\n' "${REESCANEO_SEGUNDOS:-3600}"
  printf 'REENVIOS_SOLO_LAN=%q\n' "${REENVIOS_SOLO_LAN:-no}"
  printf 'CLAVE_SSH=\n'
} > "$MEDIA_BRIDGE_CONFIG"

# shellcheck source=/dev/null
source "$MEDIA_BRIDGE_CONFIG"

if ! medios _comprobar; then
  exit 1
fi

pids=()
pid_dlna=""
reiniciar=0

parar() {
  echo "Parando media-bridge"
  [ -n "$pid_dlna" ] && kill "$pid_dlna" 2>/dev/null
  kill "${pids[@]}" 2>/dev/null
  wait
  fusermount3 -u /media 2>/dev/null
  exit 0
}

iniciar_dlna() {
  medios _dlna &
  pid_dlna=$!
}

trap parar TERM INT
trap 'reiniciar=1' USR1

medios _montar &
pid_montaje=$!
pids+=("$pid_montaje")

if ! medios _esperar-montaje; then
  parar
fi
echo "Montado $USUARIO_SSH@$SERVIDOR:$RUTA_MEDIOS"

for p in $REENVIOS; do
  medios _reenviar "$p" &
  pids+=("$!")
  echo "Reenviando el puerto $p"
done

if [ "$DLNA" = si ]; then
  iniciar_dlna
  echo "DLNA \"$NOMBRE_DLNA\" en el puerto $PUERTO_DLNA"
  if [ "$REESCANEO_SEGUNDOS" -gt 0 ]; then
    medios _vigilar &
    pids+=("$!")
  fi
fi

while :; do
  wait -n
  if [ "$reiniciar" = 1 ]; then
    reiniciar=0
    echo "Reescaneando el DLNA"
    kill "$pid_dlna" 2>/dev/null
    wait "$pid_dlna" 2>/dev/null
    iniciar_dlna
    continue
  fi
  for p in "${pids[@]}" ${pid_dlna:+"$pid_dlna"}; do
    if ! kill -0 "$p" 2>/dev/null; then
      echo "Un proceso se ha parado (pid $p); reinicio el contenedor"
      kill "${pids[@]}" ${pid_dlna:+"$pid_dlna"} 2>/dev/null
      fusermount3 -uz /media 2>/dev/null
      exit 1
    fi
  done
done
