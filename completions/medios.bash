_medios() {
    if [ "$COMP_CWORD" -eq 1 ]; then
        COMPREPLY=($(compgen -W "on off estado progreso reescanear buscar" -- "${COMP_WORDS[1]}"))
    fi
}
complete -F _medios medios
