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
| `EXTENSIONES` | Extensiones que cuentan como vídeo | `"mkv mp4 avi"` |

## Uso

| Comando | Qué hace |
| --- | --- |
| `medios on` | Monta las carpetas, arranca el DLNA y los reenvíos, y te dice las direcciones |
| `medios off` | Lo apaga todo |
| `medios estado` | Qué está encendido |
| `medios progreso` | Cuántos vídeos lleva indexados el DLNA, en directo, con ritmo y tiempo restante |
| `medios reescanear` | Busca vídeos nuevos ya (si no, lo hace solo cada hora cuando nadie está viendo nada) |
| `medios buscar "texto"` | Busca en el servidor sin tener que acertar el nombre exacto |

`medios buscar` no distingue mayúsculas, tildes ni separadores, acepta las palabras en cualquier orden y tolera erratas:

```
$ medios buscar "hobit"
Buscado en 2503 vídeos del servidor

Parecidos (1):
  Movies/El hobbit Un viaje inesperado.mkv
```

No necesita que el DLNA esté encendido: busca directamente en el servidor por SSH.

En la televisión, el servidor aparece en la lista de fuentes o en la app de medios con el nombre de `NOMBRE_DLNA`.

## Cosas a tener en cuenta

- **Sin conversión.** El DLNA entrega los ficheros tal cual: si la televisión no sabe reproducir un formato (algunos AVI antiguos, ciertos audios), ese vídeo no se verá. Para esos, usa Jellyfin con el reenvío o VLC.
- **La primera vez indexa todo**, y vuelve a hacerlo desde cero si cambias `CARPETAS`: minidlna no sabe añadir una sola carpeta. Mientras dura, la televisión puede dar "no compatible" en lo que tenías abierto; vuelve a entrar en el servidor. Usa `medios progreso` para ver cuánto falta.
- **Mismo rango de red en casa y fuera.** Si la red del portátil y la de casa usan la misma numeración (por ejemplo, las dos 192.168.1.x) y aceptas rutas de subred de Tailscale, el portátil contestará a la televisión por el túnel y nada funcionará. Desactívalo con `sudo tailscale set --accept-routes=false`.
- **Plex no sirve.** Aunque reenvíes el 32400, la app de Plex pide Plex Pass o Remote Watch Pass, porque plex.tv ve que la televisión y el servidor tienen distinta IP pública. Eso no se arregla desde la red.
- **Enlaces simbólicos.** Se siguen en el servidor, así que valen carpetas con enlaces a montajes en la nube (rclone y similares). Esos vídeos tardan más en arrancar.
- **Los servicios web ven la IP de Tailscale del portátil**, no la de la televisión. Si Jellyfin limita la calidad por considerarlo remoto, añade `100.64.0.0/10` a sus redes LAN.

## Desinstalar

```bash
./uninstall.sh
```

Con `--purge` borra también la configuración y el índice del DLNA. Las reglas de `ufw` se quitan a mano (`sudo ufw status numbered`).

## Licencia

[MIT](LICENSE)
