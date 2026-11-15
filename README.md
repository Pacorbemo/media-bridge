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

`qrencode` no hace falta instalarlo: si usas `medios on -j` y no lo tienes, lo descarga e instala la primera vez, avisándote y pidiéndote la contraseña de sudo. En Docker se descarga dentro del contenedor.

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

Si usas Claude Code, Codex, Gemini/Antigravity, Cursor u otro asistente, abre el repo con él y pídele que lo instale. [`AGENTS.md`](AGENTS.md) le explica qué comprobar, qué preguntarte y qué errores evitar (Claude Code lo carga solo a través de `CLAUDE.md`, y Gemini a través de `GEMINI.md`).

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
| `REENVIOS_SOLO_LAN` | `si` para que los reenvíos escuchen solo en la IP de la red local (ver [Seguridad](#seguridad)) | `no` |
| `CLAVE_SSH` | Clave SSH concreta para entrar al servidor; vacío usa las de siempre. En Docker se elige al arrancar, con `CLAVE_SSH=/ruta docker compose up -d` | `~/.ssh/media-bridge` |
| `PUERTO_JELLYFIN` | Cuál de los `REENVIOS` es Jellyfin, para el QR de `-j` y el descubrimiento | `8096` |
| `DESCUBRIMIENTO_JELLYFIN` | Contestar a las apps de Jellyfin para que encuentren el servidor solas (`si`/`no`); solo funciona si `PUERTO_JELLYFIN` está en `REENVIOS` | `si` |
| `EXTENSIONES` | Extensiones que cuentan como vídeo | `"mkv mp4 avi"` |
| `RECIENTES` | Añadir al DLNA la carpeta «Añadidos recientemente» (`si`/`no`; ver [abajo](#añadidos-recientemente)) | `no` |
| `RECIENTES_CANTIDAD` | Cuántos vídeos enseña esa carpeta | `10` |
| `RECIENTES_CARPETAS` | De qué `CARPETAS` salen; vacío para todas | `("Movies")` |
| `PUERTO_WEB` | Puerto de la página de `medios web`, solo en `127.0.0.1` | `8787` |

## Uso

| Comando | Qué hace |
| --- | --- |
| `medios on` | Monta las carpetas, arranca el DLNA y los reenvíos, y te dice las direcciones. Con `-j` (`--jellyfin`) enseña también un QR con la dirección de Jellyfin para abrirla en el móvil |
| `medios off` | Lo apaga todo menos la página de `medios web` |
| `medios estado` | Qué está encendido, qué aparatos (televisiones, móviles) han encontrado el DLNA, marcando los conectados ahora, y quién tiene Jellyfin abierto por el reenvío. Con `-j` también el QR de Jellyfin |
| `medios progreso` | Cuántos vídeos lleva indexados el DLNA, en directo, con ritmo y tiempo restante |
| `medios reescanear` | Busca vídeos nuevos ya, sin esperar al reescaneo automático |
| `medios buscar "texto"` | Busca en el servidor sin tener que acertar el nombre exacto |
| `medios web [off]` | Abre en el navegador una página para usarlo sin terminal (ver [abajo](#página-web)); `off` la apaga |
| `medios logs [montaje\|dlna\|reenvios\|reescaneo\|descubrimiento\|web] [-f]` | Las últimas líneas de los registros, de todo o de una parte; con `-f`, en directo |
| `medios actualizar` | Baja la última versión del repo y la vuelve a instalar, conservando tu configuración |
| `medios version` | Qué versión tienes instalada |
| `medios -h` | Qué hace cada comando; `medios ayuda on` (o `medios on -h`) da el detalle de uno |

`medios buscar` no distingue mayúsculas, tildes ni separadores, acepta las palabras en cualquier orden y tolera erratas:

```
$ medios buscar "hobit"
Buscado en 2503 vídeos del servidor

Parecidos (1):
  Movies/El hobbit Un viaje inesperado.mkv
```

No necesita que el DLNA esté encendido: busca directamente en el servidor por SSH.

### Comprobaciones al encender

Antes de arrancar nada, `medios on` comprueba que hay red local, que la red local no sale por Tailscale, que entra al servidor por SSH, que existen las carpetas y que los puertos están libres. Si algo falla lo marca con ✘ y no enciende nada; con `medios on --forzar` se salta las comprobaciones. También avisa, sin pararse, si ufw no tiene abiertos los puertos o si has cambiado `CARPETAS` y el DLNA va a indexar todo de nuevo. En Docker se hacen las mismas comprobaciones al arrancar el contenedor.

### Reescaneo automático

Cada `REESCANEO_SEGUNDOS` (una hora por defecto) compara la lista de vídeos del servidor con la que había en el último indexado. Si no ha cambiado nada, no hace nada. Si hay vídeos nuevos o borrados, reinicia el DLNA para que los añada, salvo que alguien esté viendo algo: entonces espera a la siguiente vuelta. Comparar la lista es barato (un `find` por SSH), así que puedes bajar el intervalo a unos minutos sin problema.

### Añadidos recientemente

Con `RECIENTES=si`, el DLNA enseña una carpeta más, «Añadidos recientemente», con los últimos `RECIENTES_CANTIDAD` vídeos (10 por defecto) que han llegado al servidor, numerados del más nuevo al más antiguo:

```
01 · Toy Story 5 (2026)
02 · Ali G: Kién es yo? (2026)
03 · Weapons (2025)
```

- No copia nada: son enlaces en `DB_DLNA` que apuntan a los vídeos montados.
- Cada vídeo sale con el nombre de su carpeta (`Toy Story 5 (2026)`), no con el del fichero (`Toy.Story.5.2026.UHD.BluRay...`). Si está suelto, con el del fichero.
- Cuenta la fecha en que media-bridge vio el vídeo por primera vez, no la del fichero, que en los montajes de rclone suele ser la del original. La primera vez no tiene historial y usa la del fichero. Las fechas se guardan en `DB_DLNA/llegadas`.
- Se rehace cada vez que arranca el DLNA, es decir, al encender y cada vez que el [reescaneo automático](#reescaneo-automático) encuentra cambios.
- `RECIENTES_CARPETAS` elige de qué carpetas salen. Por ejemplo, `("Movies")` para dejar fuera las series y que la carpeta no se llene de episodios sueltos.

Activarla o desactivarla cambia la lista de carpetas del DLNA, así que **la primera vez indexa todo de nuevo** (como al cambiar `CARPETAS`). `medios on` lo avisa.

Algunos `.mp4` llevan un título interno y la televisión enseña ese título en lugar del nombre, sin el número; siguen en la carpeta, pero puede que no salgan en su sitio.

### Descubrimiento de Jellyfin

Las apps de Jellyfin (Android TV, móvil, Fire TV y otras) buscan servidores en la red local con un mensaje de broadcast al puerto 7359/udp. Ese mensaje no cruza Tailscale, así que el servidor de casa nunca lo ve. Si `PUERTO_JELLYFIN` está en `REENVIOS`, el portátil contesta en su nombre: da su propia dirección en la red local (`http://IP-del-portátil:8096`, la del reenvío) con el nombre y el identificador reales del servidor, que lee de `/System/Info/Public` sin contraseña. Así el servidor aparece solo en la app, sin escribir la dirección. Si no puede leer esos datos (servidor apagado, Jellyfin parado), no contesta y lo deja en `medios logs descubrimiento`.

Se enciende con `medios on` y se apaga con `medios off`. Para desactivarlo, `DESCUBRIMIENTO_JELLYFIN=no`. Si usas ufw, el 7359/udp tiene que estar abierto: `./install.sh --firewall` lo incluye y `medios on` avisa si falta.

### Página web

`medios web` abre en el navegador una página para usar media-bridge sin terminal:

- Si está encendido, cada servicio y las direcciones de los reenvíos.
- Quién está conectado: los aparatos del DLNA, marcando los que lo usan ahora, y las IPs con Jellyfin abierto por el reenvío.
- El avance del indexado (cuántos de cuántos, ritmo y lo que falta), igual que `medios progreso`.
- «Añadidos recientemente», si `RECIENTES=si`.
- El QR de Jellyfin, si `qrencode` está instalado. Si no, solo la dirección: la página no instala nada.
- Un buscador que hace lo mismo que `medios buscar`.
- Los botones **Encender** (enseña las comprobaciones de `medios on`, con sus ✘ y avisos), **Apagar** y **Reescanear**. Los dos últimos piden confirmación y avisan si hay alguien conectado, porque cortan lo que se esté viendo.

Se refresca sola cada 5 segundos y funciona sin internet. Escucha solo en `127.0.0.1:PUERTO_WEB` (8787 por defecto): nadie de la red local la ve, ni siquiera la televisión. Para abrirla desde otro equipo de tu tailnet, haz un túnel SSH y abre `http://127.0.0.1:8787` en él:

```
ssh -L 8787:127.0.0.1:8787 usuario@portátil
```

`medios off` no la apaga, para que el botón Apagar no se lleve la propia página por delante; se apaga con `medios web off`. Como los demás servicios, no se enciende sola al arrancar el equipo. En Docker no está disponible.

En la televisión, el servidor aparece en la lista de fuentes o en la app de medios con el nombre de `NOMBRE_DLNA`.

## Cosas a tener en cuenta

- **Sin conversión.** El DLNA entrega los ficheros tal cual: si la televisión no sabe reproducir un formato (algunos AVI antiguos, ciertos audios), ese vídeo no se verá. Para esos, usa Jellyfin con el reenvío o VLC.
- **La primera vez indexa todo**, y vuelve a hacerlo desde cero si cambias `CARPETAS`: minidlna no sabe añadir una sola carpeta. Mientras dura, la televisión puede dar "no compatible" en lo que tenías abierto; vuelve a entrar en el servidor. Usa `medios progreso` para ver cuánto falta.
- **Mismo rango de red en casa y fuera.** Si la red del portátil y la de casa usan la misma numeración (por ejemplo, las dos 192.168.1.x) y aceptas rutas de subred de Tailscale, el portátil contestará a la televisión por el túnel y nada funcionará. Desactívalo con `sudo tailscale set --accept-routes=false`.
- **Plex no sirve.** Aunque reenvíes el 32400, la app de Plex pide Plex Pass o Remote Watch Pass, porque plex.tv ve que la televisión y el servidor tienen distinta IP pública. Eso no se arregla desde la red.
- **Enlaces simbólicos.** Se siguen en el servidor, así que valen carpetas con enlaces a montajes en la nube (rclone y similares). Esos vídeos tardan más en arrancar.
- **Los servicios web ven la IP de Tailscale del portátil**, no la de la televisión. Si Jellyfin limita la calidad por considerarlo remoto, añade `100.64.0.0/10` a sus redes LAN.

## Seguridad

Lee esto antes de usarlo fuera de casa. Lo que está activado por defecto:

- **El DLNA no tiene contraseña.** El protocolo no tiene usuarios: cualquiera conectado a la red del portátil (la Wi-Fi de un hotel, de un piso compartido o de la oficina) ve y reproduce toda la biblioteca de `CARPETAS`. Publica solo las carpetas que no te importe que vean, y apágalo con `medios off` cuando no lo uses.
- **Los reenvíos exponen el servicio tal cual.** Quien llegue a `http://IP-del-portátil:8096` entra al Jellyfin de tu servidor, que tiene su propio usuario y contraseña. Un servicio sin login quedaría abierto para toda la red. Por defecto los reenvíos escuchan en todas las interfaces del portátil, no solo en la red local. El descubrimiento de Jellyfin, si está activo, anuncia a toda la red el nombre del servidor y la dirección del reenvío. Nunca añadas la IP del portátil a las redes "sin autenticación" de Jellyfin, Plex u otro servicio: daría acceso de administrador sin contraseña a toda la red del portátil.
- **La clave SSH del portátil entra en el servidor como `USUARIO_SSH`.** Es una clave sin contraseña (los servicios la usan sin preguntar), así que quien se haga con el portátil o con esa clave puede hacer en el servidor todo lo que puede ese usuario. Si es tu usuario normal, eso es mucho.

Hay dos refuerzos opcionales, desactivados por defecto. Con la configuración de siempre todo funciona igual.

### Reenvíos solo en la red local

Con `REENVIOS_SOLO_LAN=si`, `socat` escucha solo en la IP del portátil en la red local (la de `INTERFAZ`, o la de la ruta por defecto), y no en Tailscale, en `127.0.0.1` ni en otras redes. Cada 10 segundos mira si esa IP ha cambiado (por ejemplo, al cambiar de Wi-Fi) y, si es así, vuelve a escuchar en la nueva. Sin red local, espera a tenerla.

Consecuencia: desde el propio portátil tampoco funciona `http://127.0.0.1:8096`. Usa su IP local, la que enseña `medios estado`.

### Usuario SSH restringido

En vez de tu usuario, el portátil puede entrar al servidor con uno creado solo para esto, que únicamente pueda leer los vídeos. En el **servidor**:

```bash
sudo useradd --create-home --shell /bin/bash media-bridge
```

Si los vídeos son legibles por todos (permisos habituales `755`/`644`), no hace falta más. Si no, dale lectura con ACL, también para lo que se añada después (cambia las rutas por las tuyas):

```bash
sudo setfacl -m u:media-bridge:rx /mnt/media
sudo setfacl -R -m u:media-bridge:rX /mnt/media/Movies "/mnt/media/Tv Shows"
sudo setfacl -R -d -m u:media-bridge:rX /mnt/media/Movies "/mnt/media/Tv Shows"
```

Si las carpetas tienen enlaces a montajes FUSE (rclone y similares), el usuario nuevo no podrá leerlos salvo que el montaje use `--allow-other` (y `/etc/fuse.conf` tenga `user_allow_other`).

En el **portátil**, crea una clave solo para él:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/media-bridge -N ""
```

Copia `~/.ssh/media-bridge.pub` al servidor, en `/home/media-bridge/.ssh/authorized_keys` (dueño `media-bridge`, permisos `600`), con estas opciones delante de la clave:

```
restrict,from="100.64.0.0/10" ssh-ed25519 AAAA... media-bridge
```

`restrict` quita el reenvío de puertos, el del agente, X11 y la terminal; `from` solo la acepta si llega por Tailscale. Después, en `~/.config/media-bridge/config`:

```bash
USUARIO_SSH=media-bridge
CLAVE_SSH=~/.ssh/media-bridge
```

y `medios on` comprobará que entra y ve las carpetas.

Qué sigue funcionando y qué no:

- **Funciona todo:** el montaje (sshfs usa SFTP), `medios buscar`, `medios progreso`, el reescaneo automático y las comprobaciones de `medios on`. Estos cuatro ejecutan órdenes por SSH (`find`, `true` y `[ -d ]`), y `restrict` las permite.
- **Lo que no protege:** el usuario puede ejecutar órdenes y leer cualquier fichero del servidor legible por todos. Lo que gana es que ya no es tu usuario: no puede escribir en tus cosas, usar `sudo` ni leer tus ficheros privados.
- **Solo SFTP no sirve.** Un usuario limitado a SFTP (`ForceCommand internal-sftp` o `ChrootDirectory`) dejaría montar las carpetas, pero rompería `buscar`, `progreso`, el reescaneo automático y las comprobaciones, que necesitan ejecutar `find` y `[ -d ]`.

## Actualizar

```bash
medios actualizar
```

Hace `git pull` en el clon desde el que instalaste y vuelve a ejecutar `./install.sh`. Tu configuración no se toca, y lo que esté encendido no se reinicia: sigue con la versión anterior hasta que hagas `medios off` y `medios on`. Si borraste el clon, te explica cómo volver a clonarlo. Qué trae cada versión: [`CHANGELOG.md`](CHANGELOG.md).

## Desinstalar

```bash
./uninstall.sh
```

Con `--purge` borra también la configuración y el índice del DLNA. Con `--firewall` quita las reglas de `ufw` que puso `./install.sh --firewall` (las que llevan el comentario `media-bridge`); pide la contraseña de sudo. Se pueden juntar: `./uninstall.sh --purge --firewall`.

## Desarrollo

Los tests usan solo Python 3 y bash, sin instalar nada:

```bash
python3 -m unittest discover -s tests -v
```

Prueban la búsqueda de `lib/buscar.py`, los enlaces de `lib/recientes.py`, la ayuda y los errores de `bin/medios` (sin SSH ni systemd: no encienden nada) y la configuración que genera el entrypoint de Docker. Los del entrypoint se saltan si no existe `/ssh/clave`; en GitHub Actions se crea una falsa para que se ejecuten.

GitHub ejecuta los tests y `shellcheck` en cada push y pull request. Para pasar `shellcheck` en local:

```bash
shellcheck bin/medios install.sh uninstall.sh docker/entrypoint.sh
```

Lo que cambia en cada versión está en [`CHANGELOG.md`](CHANGELOG.md).

## Licencia

[MIT](LICENSE)
