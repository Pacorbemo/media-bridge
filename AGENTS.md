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

## Verificación

- **Cada reenvío:** `curl` a `http://IP-local-del-puente:PUERTO` desde el propio puente.
- **DLNA:** `medios progreso` hasta que diga "terminado". La primera indexación tarda: en el caso probado, unos 180 vídeos por minuto sobre sshfs.
- **Descubrimiento:** la página `http://IP-local-del-puente:8200/` lista los clientes que se han conectado. Si aparece la IP de la televisión, ya ha encontrado el servidor.
- **Si la televisión no conecta:** busca bloqueos con `journalctl -k | grep "UFW BLOCK"`.

## No hagas esto

- **No reinicies `media-bridge-dlna` mientras alguien está viendo algo.** Mira antes `ss -tn "( sport = :8200 )"`, pero no te fíes del todo: la televisión no mantiene la conexión abierta todo el rato. Pregúntale al usuario.
- **No cambies `CARPETAS` sin avisar.** Añadir, quitar o reordenar carpetas hace que minidlna borre el índice y lo rehaga entero. Mientras tanto, la televisión da "no compatible" en lo que tenía abierto. Avisa y estima el tiempo.
- **No borres `DB_DLNA`:** obliga a indexar todo de nuevo.
- **No actives el `minidlna.service` del sistema:** choca en el puerto 8200.
- **No habilites los servicios para el arranque.** El diseño es manual, con `medios on` y `medios off`.
- **No intentes que Plex funcione por el puente.** La app de Plex pide Remote Watch Pass porque plex.tv compara la IP pública de la televisión con la del servidor, y eso no se arregla desde la red. Nunca metas la IP del puente en la lista de redes "sin autenticación" de Plex ni de otro servicio: daría acceso de administrador sin contraseña a toda la red del puente.
- **No abras puertos a todo internet** (`0.0.0.0/0`).

## Diagnóstico rápido

| Síntoma | Causa probable | Qué mirar |
| --- | --- | --- |
| "No compatible" en algo que antes funcionaba | El índice se rehízo y cambiaron los identificadores | `journalctl --user -u media-bridge-dlna` muestra `New media_dir detected` o peticiones con 404. Volver a entrar en el servidor desde la televisión |
| Un vídeo concreto no se reproduce | El DLNA no convierte formatos (algunos AVI antiguos) | Usar Jellyfin con el reenvío, o VLC |
| La televisión no ve el servidor DLNA | ufw bloquea 1900/udp o 8200/tcp, o la interfaz es incorrecta | `journalctl -k`, `INTERFAZ` en la config, `medios estado` |
| Un reenvío funciona desde el puente pero no desde la red | ufw, o choque de rangos | `journalctl -k`, `ip route get <IP del aparato>` |
| No hay vídeos | El montaje está caído | `journalctl --user -u media-bridge-mount`: se reintenta solo cada 10 s si el servidor está apagado o sin conexión |

## Estructura

- `bin/medios`: el comando. Lee la configuración y también hace de punto de entrada de los servicios, con los subcomandos internos que empiezan por `_`.
- `systemd/`: servicios de usuario `media-bridge-*` (montaje, DLNA, reenvíos y reescaneo horario).
- `lib/buscar.py`: la búsqueda aproximada de `medios buscar`.
- `completions/`: autocompletado para zsh y bash.
- `install.sh` / `uninstall.sh`.
