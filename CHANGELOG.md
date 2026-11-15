# Cambios

Lo que cambia en cada versión de media-bridge. La versión instalada se ve con `medios version`.

## Sin publicar

Nada todavía.

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
