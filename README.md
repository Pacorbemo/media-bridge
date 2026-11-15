# media-bridge

Lleva los vídeos de tu servidor de casa a cualquier red en la que esté tu portátil, para verlos en una televisión o en un móvil que **no tienen Tailscale**.

Este proyecto nace de querer ver mi contenido en una televisión que no es mía. En ella no podía instalar Tailscale, pero sí tenía en la misma red un equipo conectado a mi red de Tailscale. La idea es aprovechar ese equipo como puente: la televisión habla con él como con cualquier aparato de su red, y él trae los vídeos de casa por el túnel.

También sirve para televisiones cuyo sistema no tiene app de Jellyfin pero sí un reproductor de medios en red (DLNA), que es lo habitual: la televisión ve tus carpetas en su reproductor sin instalar nada.

> **Probado únicamente en una televisión Hisense (VIDAA).** Debería funcionar con cualquier televisión que reproduzca contenido DLNA, pero no está comprobado.

```
 Televisión / móvil ──Wi-Fi──► portátil ══Tailscale══► servidor de casa
                               (media-bridge)            (Jellyfin, carpetas)
```

El portátil hace de intermediario:

- **DLNA:** monta las carpetas del servidor por `sshfs` y las publica con `minidlna`. Cualquier televisión con reproductor DLNA (Hisense VIDAA, Samsung, LG, consolas, VLC, Windows) las ve como un servidor más de la red, sin instalar nada.
- **Reenvío de puertos:** reenvía puertos del servidor, como el 8096 de Jellyfin, a la red local con `socat`. Los aparatos de esa red entran por `http://IP-del-portátil:8096`.
- **Comando `medios`:** lo enciende y lo apaga todo, busca películas aunque no aciertes el nombre exacto y te enseña el progreso del indexado.

Todo funciona con servicios de usuario de systemd: no hace falta root para usarlo, solo para instalar paquetes y abrir el firewall.

## Requisitos

- **Servidor:** cualquier Linux con los vídeos en una carpeta, accesible por SSH con clave (sin contraseña) a través de [Tailscale](https://tailscale.com). Si usas Jellyfin u otro servicio web, tiene que escuchar en la IP de Tailscale.
- **Portátil:** Linux con systemd, Tailscale y estos paquetes:

| Distribución | Comando |
| --- | --- |
| Arch | `sudo pacman -S --needed openssh sshfs socat minidlna python curl iproute2 fuse3` |
| Debian / Ubuntu | `sudo apt install openssh-client sshfs socat minidlna python3 curl iproute2 fuse3` |
| Fedora | `sudo dnf install openssh-clients fuse-sshfs socat minidlna python3 curl iproute fuse3` |

Comprueba antes que el portátil entra al servidor sin contraseña:

```bash
ssh usuario@IP-tailscale-del-servidor true
```

## Instalación

```bash
git clone https://github.com/Pacorbemo/media-bridge.git
cd media-bridge
./install.sh
```

Después edita `~/.config/media-bridge/config` con los datos de tu servidor y enciéndelo con `medios on`.

Si usas `ufw`, `./install.sh --firewall` abre los puertos necesarios, **solo para redes privadas** (192.168.x, 10.x y 172.16-31.x).

El servicio `minidlna` del sistema no hace falta: si lo tienes activado, desactívalo para que no choque en el puerto 8200.

### Con Docker

Si prefieres no instalar paquetes en el equipo, hay una imagen con todo dentro:

```bash
git clone https://github.com/Pacorbemo/media-bridge.git
cd media-bridge
cp media-bridge.env.example media-bridge.env
```

Edita `media-bridge.env` con los datos de tu servidor. Aquí `CARPETAS` va separado por comas (`Movies,Tv Shows`). Por defecto se usa tu clave `~/.ssh/id_ed25519`; si es otra, arranca con `CLAVE_SSH=/ruta/a/tu/clave`.

| Acción | Comando |
| --- | --- |
| Encender | `docker compose up -d --build` |
| Apagar | `docker compose down` |
| Estado | `docker compose exec media-bridge medios estado` |
| Buscar | `docker compose exec media-bridge medios buscar "texto"` |
| Progreso del indexado | `docker compose exec media-bridge medios progreso` |
| Reescanear | `docker compose exec media-bridge medios reescanear` |
| Ver qué está pasando | `docker compose logs -f` |
| Actualizar | `git pull && docker compose up -d --build` |

El índice del DLNA se guarda en un volumen de Docker, así que sobrevive a `docker compose down`.

**Ten en cuenta que Docker aquí añade complejidad y aísla poco.** El contenedor necesita:

- **La red del equipo** (`network_mode: host`): el DLNA se anuncia por multicast en la red local y los puertos tienen que verse desde la televisión.
- **Permisos para montar** (`/dev/fuse`, `SYS_ADMIN` y sin perfil de AppArmor): sshfs monta las carpetas dentro del contenedor, y eso es casi como ejecutarlo como root.
- **Tu clave SSH**, montada en solo lectura.
- **El Tailscale del equipo**: el contenedor no trae el suyo, usa el del equipo a través de su red.

Si algo falla, hay más capas donde mirar (la red de Docker, los permisos de FUSE, la clave dentro del contenedor). Si no tienes un motivo para usar Docker, la instalación normal es más sencilla de depurar.

### Con un asistente de IA

Si usas Claude Code, Codex, Cursor u otro asistente, abre el repo con él y pídele que lo instale. [`AGENTS.md`](AGENTS.md) le explica qué comprobar, qué preguntarte y qué errores evitar (Claude Code lo carga solo a través de `CLAUDE.md`).

## Configuración

`~/.config/media-bridge/config`:

| Variable | Qué es | Ejemplo |
| --- | --- | --- |
| `SERVIDOR` | IP de Tailscale del servidor (`tailscale ip -4` en él) | `100.64.0.10` |
| `USUARIO_SSH` | Usuario SSH del servidor | `usuario` |
| `RUTA_MEDIOS` | Carpeta del servidor con los vídeos | `/mnt/media` |
| `CARPETAS` | Subcarpetas que se publican y en las que se busca | `("Movies" "Tv Shows")` |
| `REENVIOS` | Puertos que se reenvían; vacío para ninguno | `"8096"` |
| `DLNA` | Publicar las carpetas por DLNA (`si`/`no`) | `si` |
| `NOMBRE_DLNA` | Nombre que aparece en la televisión | `media-bridge` |
| `PUERTO_DLNA` | Puerto del DLNA | `8200` |
| `INTERFAZ` | Interfaz de la red local; vacío para detectarla | `wlan0` |
| `PUNTO_MONTAJE` | Dónde se montan las carpetas | `$HOME/media-bridge` |
| `DB_DLNA` | Dónde guarda el DLNA su índice | `$HOME/.cache/media-bridge` |
| `REESCANEO_SEGUNDOS` | Cada cuánto mira si hay vídeos nuevos o borrados; `0` lo desactiva | `3600` |
| `EXTENSIONES` | Extensiones que cuentan como vídeo | `"mkv mp4 avi"` |

## Uso

| Comando | Qué hace |
| --- | --- |
| `medios on` | Monta las carpetas, arranca el DLNA y los reenvíos, y te dice las direcciones |
| `medios off` | Lo apaga todo |
| `medios estado` | Qué está encendido |
| `medios progreso` | Cuántos vídeos lleva indexados el DLNA, en directo, con ritmo y tiempo restante |
| `medios reescanear` | Busca vídeos nuevos ya, sin esperar al reescaneo automático |
| `medios buscar "texto"` | Busca en el servidor sin tener que acertar el nombre exacto |
| `medios actualizar` | Baja la última versión del repo y la vuelve a instalar, conservando tu configuración |
| `medios version` | Qué versión tienes instalada |

`medios buscar` no distingue mayúsculas, tildes ni separadores, acepta las palabras en cualquier orden y tolera erratas:

```
$ medios buscar "hobit"
Buscado en 2503 vídeos del servidor

Parecidos (1):
  Movies/El hobbit Un viaje inesperado.mkv
```

No necesita que el DLNA esté encendido: busca directamente en el servidor por SSH.

### Reescaneo automático

Cada `REESCANEO_SEGUNDOS` (una hora por defecto) compara la lista de vídeos del servidor con la que había en el último indexado. Si no ha cambiado nada, no hace nada. Si hay vídeos nuevos o borrados, reinicia el DLNA para que los añada, salvo que alguien esté viendo algo: entonces espera a la siguiente vuelta. Comparar la lista es barato (un `find` por SSH), así que puedes bajar el intervalo a unos minutos sin problema.

En la televisión, el servidor aparece en la lista de fuentes o en la app de medios con el nombre de `NOMBRE_DLNA`.

## Cosas a tener en cuenta

- **Sin conversión.** El DLNA entrega los ficheros tal cual: si la televisión no sabe reproducir un formato (algunos AVI antiguos, ciertos audios), ese vídeo no se verá. Para esos, usa Jellyfin con el reenvío o VLC.
- **La primera vez indexa todo**, y vuelve a hacerlo desde cero si cambias `CARPETAS`: minidlna no sabe añadir una sola carpeta. Mientras dura, la televisión puede dar "no compatible" en lo que tenías abierto; vuelve a entrar en el servidor. Usa `medios progreso` para ver cuánto falta.
- **Mismo rango de red en casa y fuera.** Si la red del portátil y la de casa usan la misma numeración (por ejemplo, las dos 192.168.1.x) y aceptas rutas de subred de Tailscale, el portátil contestará a la televisión por el túnel y nada funcionará. Desactívalo con `sudo tailscale set --accept-routes=false`.
- **Plex no sirve.** Aunque reenvíes el 32400, la app de Plex pide Plex Pass o Remote Watch Pass, porque plex.tv ve que la televisión y el servidor tienen distinta IP pública. Eso no se arregla desde la red.
- **Enlaces simbólicos.** Se siguen en el servidor, así que valen carpetas con enlaces a montajes en la nube (rclone y similares). Esos vídeos tardan más en arrancar.
- **Los servicios web ven la IP de Tailscale del portátil**, no la de la televisión. Si Jellyfin limita la calidad por considerarlo remoto, añade `100.64.0.0/10` a sus redes LAN.

## Actualizar

```bash
medios actualizar
```

Hace `git pull` en el clon desde el que instalaste y vuelve a ejecutar `./install.sh`. Tu configuración no se toca, y lo que esté encendido no se reinicia: sigue con la versión anterior hasta que hagas `medios off` y `medios on`. Si borraste el clon, te explica cómo volver a clonarlo.

## Desinstalar

```bash
./uninstall.sh
```

Con `--purge` borra también la configuración y el índice del DLNA. Las reglas de `ufw` se quitan a mano (`sudo ufw status numbered`).

## Licencia

[MIT](LICENSE)
