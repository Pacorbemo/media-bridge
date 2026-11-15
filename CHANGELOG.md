# Cambios

Lo que cambia en cada versión de media-bridge. La versión instalada se ve con `medios version`.

## Sin publicar

### Añadido

- **Carpeta «Añadidos recientemente» en el DLNA**, opcional (`RECIENTES=si`). Enseña los últimos `RECIENTES_CANTIDAD` vídeos (10 por defecto) que han llegado al servidor, numerados del más nuevo al más antiguo y con el nombre de su carpeta. `RECIENTES_CARPETAS` elige de qué carpetas salen, por ejemplo solo las de películas. Se rehace al encender y cada vez que el reescaneo encuentra cambios, y `medios estado` la menciona.
- `medios comprobar`: las comprobaciones de `medios on` (red, Tailscale, SSH, carpetas, puertos y ufw) sin encender nada. Devuelve `1` si algo impediría encender.
- `medios ayuda config`: cada variable de la configuración explicada, con el valor que tiene y el de por defecto.
- `medios ayuda problemas`: lo que suele fallar y cómo arreglarlo, de la televisión que no ve el DLNA al montaje colgado.
- Página de manual: `man medios` lo junta todo. `install.sh` la genera a partir de la ayuda.
- Sugerencias al equivocarse: `medios estdo` contesta `¿Querías decir "estado"?`, y lo mismo con las opciones, las partes de `medios logs` y los temas de `medios ayuda`.
- **Página web local** con `medios web`, para usarlo sin terminal: estado, quién está conectado, avance del indexado, «Añadidos recientemente», QR de Jellyfin, buscador y botones para encender, apagar y reescanear. También sirve de **panel de control**: edita la configuración con casillas para las carpetas del servidor y las opciones, la valida antes de guardar, guarda una copia en `config.bak` y ofrece aplicarla, avisando si hay alguien viendo algo o si el DLNA va a indexar todo de nuevo. Escucha solo en `127.0.0.1` (`PUERTO_WEB`, 8787 por defecto), no necesita internet ni dependencias y sigue encendida tras `medios off`; se apaga con `medios web off`.
- `medios estado` dice qué IPs tienen Jellyfin abierto por el reenvío.

### Corregido

- Un comando desconocido ya no pide la configuración antes de decir que no existe.

## 0.4.0

Publicada el 2026-11-15.

### Añadido

- **Descubrimiento de Jellyfin a través del puente.** Las apps de Jellyfin de la red local encuentran el servidor solas, sin escribir la dirección. El portátil contesta en 7359/udp en nombre del servidor, con su IP local y el nombre e identificador reales del servidor. Se enciende con `medios on` si `PUERTO_JELLYFIN` está en `REENVIOS`, y `DESCUBRIMIENTO_JELLYFIN=no` lo desactiva.
  - Está incluido en las comprobaciones de `medios on` (puerto ocupado), el aviso de ufw, `./install.sh --firewall`, `medios estado`, `medios logs descubrimiento` y Docker.
- `GEMINI.md`, para que los asistentes de Google (Gemini CLI y Antigravity) carguen solos las instrucciones de `AGENTS.md`, igual que Claude Code con `CLAUDE.md`.
- `medios on` avisa si algún puerto de `REENVIOS` no responde en el servidor.

### Corregido

- `medios estado` y `medios on` ya no devuelven código de salida `1` cuando se ejecutan sin `-j`.
- Se valida que `DLNA` sea `si` o `no`, que `CARPETAS` no esté vacío y que los puertos de la configuración sean números válidos.
- La comprobación de `ufw` al encender verifica que las reglas sean de paso (`ACCEPT`) y no solo para la interfaz de Tailscale.

## 0.3.0

Publicada el 2026-11-15.

### Añadido

- **Refuerzos de seguridad opcionales**, desactivados por defecto:
  - `REENVIOS_SOLO_LAN=si` hace que los reenvíos escuchen solo en la IP de la red local. Si esa IP cambia, pasan a escuchar en la nueva.
  - `CLAVE_SSH` elige una clave SSH concreta para entrar al servidor.
  - El README explica cómo crear en el servidor un usuario SSH que solo pueda leer los vídeos.
- Apartado de **seguridad** en el README: el DLNA no tiene contraseña, los reenvíos exponen el servicio tal cual y la clave SSH entra en el servidor como `USUARIO_SSH`.
- `medios on -j` y `medios estado -j` enseñan un **código QR** para abrir Jellyfin desde el móvil (puerto `PUERTO_JELLYFIN`, 8096 por defecto). `qrencode` se instala la primera vez que se usa: con sudo en el equipo y con `apk` en Docker.
- `medios estado` muestra qué televisiones se han conectado al DLNA.
- `medios logs` para ver los registros.
- `uninstall.sh --firewall` quita las reglas de ufw con el comentario `media-bridge`.
- Las versiones se publican solas en GitHub al subir una etiqueta `vX.Y.Z`, con el texto de su apartado en este fichero.
- **Tests automáticos** de `lib/buscar.py`, de `bin/medios` y de la configuración que genera el entrypoint de Docker, ejecutados en GitHub Actions en cada push y pull request.
- Este `CHANGELOG.md`.

### Corregido

- Docker: el contenedor ya no se para al arrancar si `REENVIOS` no aparece en `media-bridge.env`.

## 0.2.0

Publicada el 2026-11-15.

### Añadido

- **Ayuda** con `medios -h`, `medios --help` y `medios ayuda`, y el detalle de cada comando con `medios ayuda <comando>` o `medios <comando> -h`. Funciona aunque no haya configuración.
- **Comprobaciones antes de encender** en `medios on`. Revisa la red local, que no salga por Tailscale, el SSH al servidor, que existan las carpetas y que los puertos estén libres; si algo falla, no enciende nada. También avisa si ufw no abre los puertos o si cambiar `CARPETAS` va a obligar a reindexar. `medios on --forzar` se las salta. En Docker se hacen al arrancar el contenedor.

## 0.1.0

Publicada el 2026-11-15. Primera versión.

### Añadido

- **Reenvío de puertos** del servidor a la red local con `socat`, por ejemplo el 8096 de Jellyfin.
- **DLNA**: monta las carpetas del servidor por `sshfs` y las publica con `minidlna`.
- Comando **`medios`** con `on`, `off`, `estado`, `progreso`, `reescanear` y `buscar` (búsqueda aproximada que no distingue mayúsculas ni tildes y tolera erratas), con autocompletado para zsh y bash.
- **Reescaneo automático solo cuando hay cambios**: cada `REESCANEO_SEGUNDOS` (una hora por defecto) compara la lista de vídeos del servidor y reinicia el DLNA únicamente si hay vídeos nuevos o borrados y nadie está viendo nada.
- **Variante en Docker** (`Dockerfile`, `compose.yaml`, `media-bridge.env`).
- `AGENTS.md` con instrucciones para instalarlo con un asistente de IA.
- `shellcheck` en GitHub Actions.
- `medios version` y `medios actualizar`, que hace `git pull` en el clon desde el que se instaló y vuelve a instalar sin tocar la configuración.
