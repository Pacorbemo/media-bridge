_medios() {
    local -a acciones=(
        "on:encender el reenvío y el DLNA"
        "off:apagarlo todo"
        "estado:ver qué está encendido"
        "progreso:ver cuántos vídeos lleva indexados el DLNA"
        "reescanear:buscar vídeos nuevos en el DLNA"
        "buscar:buscar una película o serie (sin tener que acertar exacto)"
    )
    if (( CURRENT == 2 )); then
        _describe "acción" acciones
    fi
}
compdef _medios medios
