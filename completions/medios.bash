_medios() {
    local comandos="on off estado progreso reescanear buscar comprobar logs actualizar version ayuda"
    if [ "$COMP_CWORD" -eq 1 ]; then
        COMPREPLY=($(compgen -W "$comandos" -- "${COMP_WORDS[1]}"))
    elif [ "$COMP_CWORD" -eq 2 ] && [ "${COMP_WORDS[1]}" = ayuda ]; then
        COMPREPLY=($(compgen -W "$comandos config problemas" -- "${COMP_WORDS[2]}"))
    elif [ "$COMP_CWORD" -ge 2 ] && [ "${COMP_WORDS[1]}" = on ]; then
        COMPREPLY=($(compgen -W "--jellyfin -j --forzar" -- "${COMP_WORDS[COMP_CWORD]}"))
    elif [ "$COMP_CWORD" -ge 2 ] && [ "${COMP_WORDS[1]}" = logs ]; then
        COMPREPLY=($(compgen -W "montaje dlna reenvios reescaneo descubrimiento -f" -- "${COMP_WORDS[COMP_CWORD]}"))
    elif [ "$COMP_CWORD" -ge 2 ] && [ "${COMP_WORDS[1]}" = estado ]; then
        COMPREPLY=($(compgen -W "--jellyfin -j" -- "${COMP_WORDS[COMP_CWORD]}"))
    fi
}
complete -F _medios medios
