_medios() {
    local comandos="on off estado progreso reescanear buscar actualizar version ayuda"
    if [ "$COMP_CWORD" -eq 1 ]; then
        COMPREPLY=($(compgen -W "$comandos" -- "${COMP_WORDS[1]}"))
    elif [ "$COMP_CWORD" -eq 2 ] && [ "${COMP_WORDS[1]}" = ayuda ]; then
        COMPREPLY=($(compgen -W "$comandos" -- "${COMP_WORDS[2]}"))
    fi
}
complete -F _medios medios
