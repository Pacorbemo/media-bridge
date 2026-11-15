_medios() {
    local -a acciones=(
        "on:encender el reenvío y el DLNA"
        "off:apagarlo todo"
        "estado:ver qué está encendido"
        "progreso:ver cuántos vídeos lleva indexados el DLNA"
        "reescanear:buscar vídeos nuevos en el DLNA"
        "buscar:buscar una película o serie (sin tener que acertar exacto)"
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
        "-f:seguir en directo"
    )
    local -a opciones_estado=(
        "--jellyfin:enseñar el QR de Jellyfin"
        "-j:enseñar el QR de Jellyfin"
    )
    if (( CURRENT == 2 )) || { (( CURRENT == 3 )) && [[ $words[2] == ayuda ]]; }; then
        _describe "acción" acciones
    elif (( CURRENT >= 3 )) && [[ $words[2] == on ]]; then
        _describe "opción" opciones_on
    elif (( CURRENT >= 3 )) && [[ $words[2] == estado ]]; then
        _describe "opción" opciones_estado
    elif (( CURRENT >= 3 )) && [[ $words[2] == logs ]]; then
        _describe "parte" opciones_logs
    fi
}
compdef _medios medios
