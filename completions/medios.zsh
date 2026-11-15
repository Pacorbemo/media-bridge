_medios() {
    local -a acciones=(
        "on:encender el reenvío y el DLNA"
        "off:apagarlo todo"
        "estado:ver qué está encendido"
        "progreso:ver cuántos vídeos lleva indexados el DLNA"
        "reescanear:buscar vídeos nuevos en el DLNA"
        "buscar:buscar una película o serie (sin tener que acertar exacto)"
        "comprobar:revisar la red, el servidor y los puertos sin encender nada"
        "web:abrir la página para usarlo sin terminal"
        "logs:ver los registros"
        "actualizar:bajar e instalar la última versión"
        "version:ver la versión instalada"
        "ayuda:ver qué hace cada comando"
    )
    local -a opciones_on=(
        "--jellyfin:enseñar el QR de Jellyfin"
        "-j:enseñar el QR de Jellyfin"
        "--forzar:encender sin las comprobaciones"
    )
    local -a opciones_logs=(
        "montaje:las carpetas montadas por sshfs"
        "dlna:el servidor DLNA"
        "reenvios:los reenvíos de puertos"
        "reescaneo:el vigilante de vídeos nuevos"
        "descubrimiento:la respuesta a las apps de Jellyfin"
        "web:la página de medios web"
        "-f:seguir en directo"
    )
    local -a opciones_estado=(
        "--jellyfin:enseñar el QR de Jellyfin"
        "-j:enseñar el QR de Jellyfin"
    )
    local -a temas=(
        "config:qué es cada opción de la configuración y qué valor tiene"
        "problemas:lo que suele fallar y cómo arreglarlo"
    )
    local -a opciones_web=(
        "off:apagar la página"
    )
    if (( CURRENT == 2 )); then
        _describe "acción" acciones
    elif (( CURRENT == 3 )) && [[ $words[2] == ayuda ]]; then
        _describe "acción" acciones -- temas
    elif (( CURRENT >= 3 )) && [[ $words[2] == on ]]; then
        _describe "opción" opciones_on
    elif (( CURRENT >= 3 )) && [[ $words[2] == estado ]]; then
        _describe "opción" opciones_estado
    elif (( CURRENT == 3 )) && [[ $words[2] == web ]]; then
        _describe "opción" opciones_web
    elif (( CURRENT >= 3 )) && [[ $words[2] == logs ]]; then
        _describe "parte" opciones_logs
    fi
}
compdef _medios medios
