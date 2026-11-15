# Instrucciones para asistentes

Este repo instala `media-bridge` en un equipo Linux que hace de **puente**: está en la misma red que una televisión (u otro aparato sin Tailscale) y trae los vídeos de un **servidor** de la tailnet del usuario. Lee `README.md` para la visión general. Aquí tienes cómo instalarlo para alguien y las trampas que ya se han encontrado.

Responde en el idioma del usuario. El proyecto, los mensajes del comando y el README están en español.

## Antes de instalar

**Averígualo tú**, sin preguntar:

- Distribución y gestor de paquetes: `cat /etc/os-release`.
- Que Tailscale funciona en el puente: `tailscale status`.
- Interfaz y red local: `ip route show default` y `ip -4 -br addr`.
- Si hay firewall: `systemctl is-active ufw`.
- Si el `minidlna` del sistema está activo: `systemctl is-enabled minidlna.service`.

**Pregúntaselo al usuario**, no lo supongas:

- Qué equipo de su tailnet es el servidor. Puedes enseñarle `tailscale status` para que elija; `SERVIDOR` es su IP 100.x.
- Su usuario SSH en el servidor.
- Dónde están los vídeos y qué subcarpetas quiere publicar. Cuando ya haya acceso SSH, puedes listarlas tú para que elija.
- Qué puertos reenviar (8096 si usa Jellyfin) y si quiere DLNA.
- Con qué nombre quiere ver el servidor en la televisión.

## Comprobaciones previas

1. **SSH sin contraseña:** `ssh -o BatchMode=yes USUARIO@SERVIDOR true`. Si falla, no instales todavía: ayúdale a crear y copiar una clave (`ssh-keygen -t ed25519` y `ssh-copy-id`). No le pidas su contraseña para escribirla tú.
2. **El servicio web escucha en Tailscale:** desde el puente, `curl -s -o /dev/null -w "%{http_code}\n" http://SERVIDOR:8096/health` debe dar 200. Si no responde, el servicio solo escucha en la red de casa y hay que cambiarlo en el servidor.
3. **Choque de rangos:** si la red del puente y la de casa usan la misma numeración (por ejemplo, las dos 192.168.1.x) y el puente acepta rutas de subred de Tailscale, contestará a la televisión por el túnel. Compruébalo con `ip route get <IP de un aparato de la red local>`: si sale por `tailscale0`, hay choque. La solución es `sudo tailscale set --accept-routes=false`, pero antes explícale que el puente dejará de llegar a las subredes anunciadas por Tailscale y pídele confirmación.
4. **Carpetas:** los enlaces simbólicos a montajes en la nube (rclone y similares) funcionan, pero tardan más. Comprueba que los vídeos no son marcadores vacíos: hay librerías con ficheros `.mkv` de 1 byte que solo sirven de índice.

## Instalación

1. **Paquetes:** los comandos del README según la distribución. Necesitan sudo: lánzalos donde el usuario pueda escribir la contraseña él mismo, como un terminal suyo. No se la pidas por el chat.
2. `./install.sh`, sin sudo.
3. Escribe `~/.config/media-bridge/config` con sus datos. Es bash: `CARPETAS` es un array, `CARPETAS=("Movies" "Tv Shows")`.
4. **Firewall:** usa `./install.sh --firewall` solo si el usuario está de acuerdo. Abre los puertos únicamente a rangos privados. Si ya tiene reglas equivalentes, no las dupliques.
5. `medios on` y después `medios estado`.

### Actualizar

`medios actualizar` hace `git pull --ff-only` en el clon desde el que se instaló (`install.sh` guarda su ruta en `~/.local/share/media-bridge/clon`) y vuelve a ejecutar `install.sh`. No toca la configuración ni reinicia lo que esté encendido: avisa de que hay que hacer `medios off` y `medios on` para usar la versión nueva. Si el `pull` falla porque el clon tiene cambios locales, no los descartes: enséñaselos al usuario. `medios version` dice qué versión hay instalada.

### Con Docker

Solo si el usuario lo pide o no quiere instalar paquetes. Explícale antes el aviso del README: el contenedor necesita red `host`, `/dev/fuse`, `SYS_ADMIN` y su clave SSH, así que aísla poco y es más difícil de depurar.

1. `cp media-bridge.env.example media-bridge.env` y rellénalo. `CARPETAS` va separado por comas.
2. Si su clave no es `~/.ssh/id_ed25519`, arranca con `CLAVE_SSH=/ruta`.
3. `docker compose up -d --build` y revisa `docker compose logs`: deben salir "Montado", "Reenviando el puerto" y "DLNA".
4. Los comandos van con `docker compose exec media-bridge medios ...`. `medios on`/`off` no funcionan dentro: se usa `docker compose up -d`/`down`.

## Verificación

`medios on` ya hace las comprobaciones previas (red local, choque con Tailscale, SSH, carpetas, puertos, ufw e índice) y no enciende nada si alguna falla. Para verlas sin encender nada: `medios _comprobar`. No uses `--forzar` para saltarte un ✘ sin entender antes qué lo causa.

Para abrir Jellyfin en el móvil, `medios on -j` o `medios estado -j` enseñan un código QR con su dirección (si falta `qrencode`, lo instala la primera vez con el gestor de paquetes y sudo, avisando antes; en Docker con `apk` dentro del contenedor; `PUERTO_JELLYFIN` dice cuál de los `REENVIOS` es Jellyfin). Sin `-j` no se enseña.

- **Cada reenvío:** `curl` a `http://IP-local-del-puente:PUERTO` desde el propio puente.
- **DLNA:** `medios progreso` hasta que diga "terminado". La primera indexación tarda: en el caso probado, unos 180 vídeos por minuto sobre sshfs.
- **Descubrimiento de Jellyfin:** si `PUERTO_JELLYFIN` está en `REENVIOS` y `DESCUBRIMIENTO_JELLYFIN` no es `no`, `medios on` arranca `media-bridge-descubrimiento`, que contesta en 7359/udp con la IP local del puente y el `Id` y `ServerName` reales del servidor. Compruébalo con la app de Jellyfin del usuario: el servidor debería aparecer solo al añadir uno. Si no aparece, mira `medios logs descubrimiento`: ahí sale cada pregunta recibida, o que no puede leer `/System/Info/Public`. Si no llega ninguna pregunta, suele ser ufw: descarta los broadcasts a puertos cerrados sin dejar rastro en `journalctl -k`.
- **Descubrimiento del DLNA:** la página `http://IP-local-del-puente:8200/` lista los clientes que se han conectado. Si aparece la IP de la televisión, ya ha encontrado el servidor.
- **Si la televisión no conecta:** busca bloqueos con `journalctl -k | grep "UFW BLOCK"`.

## Seguridad

Explícale siempre al usuario lo que dice el apartado de seguridad del README: el DLNA no tiene contraseña y cualquiera en la red del puente ve toda la biblioteca de `CARPETAS`, los reenvíos exponen el servicio tal cual y la clave SSH del puente entra en el servidor como `USUARIO_SSH`.

Los dos refuerzos son opcionales y están desactivados por defecto. Propónselos, pero no los actives si no te lo pide:

- **`REENVIOS_SOLO_LAN=si`:** `medios _reenviar` deja de hacer `exec socat` y se queda vigilando la IP local cada 10 s, relanzando `socat ...,bind=IP` si cambia. Para verificarlo, el `curl` tiene que ir a la IP local del puente: a `127.0.0.1` o a la IP de Tailscale ya no responde, y eso es lo esperado.
- **Usuario SSH restringido:** sigue los pasos del README en el servidor, con el usuario mirando, porque necesitan sudo allí. `CLAVE_SSH` apunta a la clave nueva; vacía, `ssh` usa las de siempre. No propongas un usuario solo-SFTP ni `ChrootDirectory`: `buscar`, `progreso`, `_vigilar` y `_comprobar` ejecutan `find`, `true` y `[ -d ]` por SSH. Si los vídeos tienen enlaces a montajes FUSE (rclone), el usuario nuevo no los lee salvo con `--allow-other`; compruébalo con `sudo -u media-bridge ls` en el servidor antes de cambiar la configuración. Después, `medios _comprobar` en el puente.

En Docker, `CLAVE_SSH` es la variable de `compose.yaml` que elige qué clave se monta en `/ssh/clave`; el entrypoint la deja vacía en la configuración interna.

## No hagas esto

- **No reinicies `media-bridge-dlna` mientras alguien está viendo algo.** Mira antes `ss -tn "( sport = :8200 )"`, pero no te fíes del todo: la televisión no mantiene la conexión abierta todo el rato. Pregúntale al usuario.
- **No cambies `CARPETAS` sin avisar.** Añadir, quitar o reordenar carpetas hace que minidlna borre el índice y lo rehaga entero. Mientras tanto, la televisión da "no compatible" en lo que tenía abierto. Avisa y estima el tiempo.
- **No borres `DB_DLNA`:** obliga a indexar todo de nuevo.
- **No pongas un reescaneo a ciegas.** `medios _vigilar` solo reinicia el DLNA si cambia la lista de vídeos (la huella está en `DB_DLNA/huella-lista`); si alguien pide que se reescanee más a menudo, baja `REESCANEO_SEGUNDOS` en vez de añadir timers o cron.
- **No actives el `minidlna.service` del sistema:** choca en el puerto 8200.
- **No habilites los servicios para el arranque.** El diseño es manual, con `medios on` y `medios off`.
- **No intentes que Plex funcione por el puente.** La app de Plex pide Remote Watch Pass porque plex.tv compara la IP pública de la televisión con la del servidor, y eso no se arregla desde la red. Nunca metas la IP del puente en la lista de redes "sin autenticación" de Plex ni de otro servicio: daría acceso de administrador sin contraseña a toda la red del puente.
- **No abras puertos a todo internet** (`0.0.0.0/0`).

## Diagnóstico rápido

Primero `medios estado` (dice qué aparatos han encontrado el DLNA y cuáles están conectados) y `medios logs [montaje|dlna|reenvios|reescaneo]`.

| Síntoma | Causa probable | Qué mirar |
| --- | --- | --- |
| "No compatible" en algo que antes funcionaba | El índice se rehízo y cambiaron los identificadores | `journalctl --user -u media-bridge-dlna` muestra `New media_dir detected` o peticiones con 404. Volver a entrar en el servidor desde la televisión |
| Un vídeo concreto no se reproduce | El DLNA no convierte formatos (algunos AVI antiguos) | Usar Jellyfin con el reenvío, o VLC |
| La televisión no ve el servidor DLNA | ufw bloquea 1900/udp o 8200/tcp, o la interfaz es incorrecta | `journalctl -k`, `INTERFAZ` en la config, `medios estado` |
| Un reenvío funciona desde el puente pero no desde la red | ufw, o choque de rangos | `journalctl -k`, `ip route get <IP del aparato>` |
| No hay vídeos | El montaje está caído | `journalctl --user -u media-bridge-mount`: se reintenta solo cada 10 s si el servidor está apagado o sin conexión |

## Estructura

- `bin/medios`: el comando. Lee la configuración y también hace de punto de entrada de los servicios, con los subcomandos internos que empiezan por `_`. `version`, `actualizar` y la ayuda (`-h`, `--help`, `ayuda [comando]` y `<comando> -h`) se resuelven antes de leer la configuración, así que funcionan aunque no exista. Si añades o cambias un comando, actualiza también su texto en `ayuda` y `ayuda_comando`, el autocompletado y la tabla de uso del README.
- `systemd/`: servicios de usuario `media-bridge-*` (montaje, DLNA, reenvíos, descubrimiento de Jellyfin y el vigilante de cambios `media-bridge-rescan`, que ejecuta `medios _vigilar`).
- `lib/buscar.py`: la búsqueda aproximada de `medios buscar`.
- `lib/descubrimiento.py`: contesta al descubrimiento de las apps de Jellyfin (`who is JellyfinServer?` en 7359/udp) en nombre del servidor, con el mismo JSON que Jellyfin (`Address`, `Id`, `Name`, `EndpointAddress`). Lo arranca `medios _descubrimiento`, desde el servicio `media-bridge-descubrimiento` o desde el entrypoint de Docker. No contesta si no puede leer `/System/Info/Public`.
- `completions/`: autocompletado para zsh y bash.
- `install.sh` / `uninstall.sh`.
- `VERSION`: la versión actual. Al publicar una nueva, súbela aquí, pasa lo de «Sin publicar» de `CHANGELOG.md` a un apartado `## X.Y.Z` (exactamente así, con la fecha en la línea siguiente: de ahí sale el texto de la versión en GitHub), y crea la etiqueta `vX.Y.Z` sobre ese commit. Al subir la etiqueta, `.github/workflows/version.yml` comprueba que `VERSION` coincide y crea la versión en GitHub con el texto de ese apartado (lo saca `.github/notas-version.sh`).
- `CHANGELOG.md`: cada cambio que note el usuario (comando, variable, comportamiento o arreglo) se añade en «Sin publicar», en el mismo commit que el cambio.
- `tests/`: tests con `unittest`, sin dependencias. Ejecútalos con `python3 -m unittest discover -s tests -v` antes de subir. `test_medios.py` ejecuta `bin/medios` desde fuera con `MEDIA_BRIDGE_CONFIG` y `MEDIA_BRIDGE_SHARE` en un directorio temporal; no añadas tests que enciendan servicios, usen SSH o toquen systemd. Si cambias la ayuda, los mensajes de error, `buscar.py` o el entrypoint, ajusta o amplía su test.
- `.github/workflows/tests.yml`: los tests en cada push y pull request. Crea una `/ssh/clave` falsa para que se ejecuten los del entrypoint, que en local se saltan.
- `.github/workflows/shellcheck.yml`: pasa `shellcheck` a `bin/medios`, `install.sh`, `uninstall.sh`, `docker/entrypoint.sh` y `.github/notas-version.sh` en cada push y pull request. Si cambias un script, que siga pasando; si un aviso es intencionado, desactívalo solo en esa línea con `# shellcheck disable=SCxxxx`.
- `Dockerfile`, `compose.yaml`, `docker/entrypoint.sh` y `media-bridge.env.example`: la variante en Docker. El entrypoint genera la configuración a partir de las variables de entorno y vigila los procesos. `medios` detecta que está dentro por `MEDIA_BRIDGE_DOCKER=1`, y en ese caso `reescanear` reinicia el DLNA enviando `USR1` al proceso 1.
