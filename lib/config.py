import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

EDITABLES = {
    "CARPETAS": "carpetas",
    "REENVIOS": "puertos",
    "DLNA": "si_no",
    "NOMBRE_DLNA": "texto",
    "PUERTO_DLNA": "puerto",
    "PUERTO_JELLYFIN": "puerto",
    "DESCUBRIMIENTO_JELLYFIN": "si_no",
    "INTERFAZ": "interfaz",
    "EXTENSIONES": "extensiones",
    "REESCANEO_SEGUNDOS": "segundos",
    "REENVIOS_SOLO_LAN": "si_no",
    "RECIENTES": "si_no",
    "RECIENTES_CANTIDAD": "cantidad",
    "RECIENTES_CARPETAS": "carpetas",
}
REINDEXAN = ["CARPETAS", "RECIENTES"]


class Invalido(Exception):
    pass


def leer_variables(texto):
    variables = []
    for linea in texto.splitlines():
        if not linea.strip():
            continue
        nombre, defecto, descripcion = linea.split("|", 2)
        variables.append({"nombre": nombre, "defecto": None if defecto == "-" else defecto, "texto": descripcion})
    return variables


def leer_valores(datos):
    campos = datos.split("\0")
    valores = {}
    i = 0
    while i + 1 < len(campos):
        nombre, clase = campos[i], campos[i + 1]
        if clase == "a":
            n = int(campos[i + 2])
            valores[nombre] = campos[i + 3 : i + 3 + n]
            i += 3 + n
        elif clase == "s":
            valores[nombre] = campos[i + 2]
            i += 3
        else:
            i += 2
    return valores


def describir(variables, valores, conf):
    lista = []
    for v in variables:
        nombre = v["nombre"]
        lista.append({
            **v,
            "tipo": EDITABLES.get(nombre),
            "fijada": nombre in valores,
            "valor": valores.get(nombre),
        })
    return {"fichero": str(conf), "existe": Path(conf).is_file(), "variables": lista, "reindexan": REINDEXAN}


def sin_control(texto):
    return all(c.isprintable() for c in texto)


def numero(valor, minimo, maximo, que):
    if not isinstance(valor, str) or not re.fullmatch(r"[0-9]{1,8}", valor.strip()):
        raise Invalido(f"{que} tiene que ser un número")
    n = int(valor.strip())
    if not minimo <= n <= maximo:
        raise Invalido(f"{que} tiene que estar entre {minimo} y {maximo}")
    return str(n)


def validar(nombre, valor):
    tipo = EDITABLES.get(nombre)
    if tipo is None:
        raise Invalido(f"{nombre} no se puede cambiar desde la página")
    if tipo == "si_no":
        if valor not in ("si", "no"):
            raise Invalido(f"{nombre} tiene que ser si o no")
        return valor
    if tipo == "puerto":
        return numero(valor, 1, 65535, nombre)
    if tipo == "segundos":
        return numero(valor, 0, 10_000_000, nombre)
    if tipo == "cantidad":
        return numero(valor, 1, 1000, nombre)
    if tipo == "puertos":
        if not isinstance(valor, str):
            raise Invalido(f"{nombre} tiene que ser una lista de puertos")
        puertos = []
        for p in valor.replace(",", " ").split():
            p = numero(p, 1, 65535, f"El puerto {p} de {nombre}")
            if p not in puertos:
                puertos.append(p)
        return " ".join(puertos)
    if tipo == "texto":
        if not isinstance(valor, str) or not valor.strip() or len(valor) > 64 or not sin_control(valor):
            raise Invalido(f"{nombre} tiene que ser un texto de 1 a 64 letras")
        return valor.strip()
    if tipo == "interfaz":
        if not isinstance(valor, str) or not re.fullmatch(r"[A-Za-z0-9_.:@-]{0,15}", valor.strip()):
            raise Invalido(f"{nombre} tiene que ser el nombre de una interfaz, como wlan0, o vacío")
        return valor.strip()
    if tipo == "extensiones":
        if not isinstance(valor, str) or not re.fullmatch(r"[A-Za-z0-9]{1,10}( +[A-Za-z0-9]{1,10})*", valor.strip()):
            raise Invalido(f"{nombre} tiene que ser una lista de extensiones separadas por espacios, como mkv mp4")
        return " ".join(valor.split())
    if tipo == "carpetas":
        if not isinstance(valor, list) or len(valor) > 100:
            raise Invalido(f"{nombre} tiene que ser una lista de carpetas")
        carpetas = []
        for c in valor:
            if (not isinstance(c, str) or not c or c in (".", "..") or "/" in c
                    or len(c) > 255 or not sin_control(c)):
                raise Invalido(f"{nombre} tiene una carpeta que no vale: {c!r}")
            if c not in carpetas:
                carpetas.append(c)
        if nombre == "CARPETAS" and not carpetas:
            raise Invalido("Marca al menos una carpeta en CARPETAS")
        return carpetas
    raise Invalido(f"{nombre} no se puede cambiar desde la página")


def citar(texto):
    if re.fullmatch(r"[A-Za-z0-9_./:@-]+", texto):
        return texto
    if not re.search(r'[\\"$`]', texto):
        return f'"{texto}"'
    return shlex.quote(texto)


def asignacion(nombre, valor):
    if isinstance(valor, list):
        return f"{nombre}=(" + " ".join(f'"{c}"' if not re.search(r'[\\"$`]', c) else shlex.quote(c) for c in valor) + ")"
    return f"{nombre}={citar(valor)}" if valor else f"{nombre}="


def bloques(lineas, nombre):
    patron = re.compile(rf"^\s*(?:export\s+|declare(?:\s+-\w+)*\s+)?{re.escape(nombre)}=(.*)$")
    cierre = re.compile(r"\)\s*(#.*)?$")
    encontrados = []
    i = 0
    while i < len(lineas):
        m = patron.match(lineas[i])
        if m:
            fin = i
            if m.group(1).lstrip().startswith("(") and not cierre.search(m.group(1)):
                while fin + 1 < len(lineas) and not cierre.search(lineas[fin]):
                    fin += 1
            encontrados.append((i, fin))
            i = fin + 1
        else:
            i += 1
    return encontrados


def aplicar(texto, cambios):
    lineas = texto.splitlines()
    for nombre, valor in cambios.items():
        nueva = asignacion(nombre, valor)
        sitios = bloques(lineas, nombre)
        if sitios:
            inicio, fin = sitios[-1]
            lineas[inicio : fin + 1] = [nueva]
        else:
            lineas.append(nueva)
    return "\n".join(lineas) + "\n"


def guardar(conf, medios, peticion):
    conf = Path(conf)
    if not conf.is_file():
        raise Invalido(f"Falta la configuración: {conf}. Créala primero con medios on o desde config.example")
    cambios = peticion.get("cambios") if isinstance(peticion, dict) else None
    if not isinstance(cambios, dict) or not cambios:
        raise Invalido("No has cambiado nada")
    limpios = {nombre: validar(nombre, valor) for nombre, valor in cambios.items()}
    nueva = conf.with_name(conf.name + ".nueva")
    nueva.write_text(aplicar(conf.read_text(), limpios))
    shutil.copymode(conf, nueva)
    r = subprocess.run(
        [medios, "_validar-config"],
        env={**os.environ, "MEDIA_BRIDGE_CONFIG": str(nueva)},
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        text=True,
        timeout=30,
    )
    if r.returncode != 0:
        nueva.unlink(missing_ok=True)
        raise Invalido("No lo guardo: " + r.stdout.strip().replace(str(nueva), str(conf)))
    copia = conf.with_name(conf.name + ".bak")
    shutil.copy2(conf, copia)
    os.replace(nueva, conf)
    return limpios, copia


def main():
    a = argparse.ArgumentParser(description="Configuración de media-bridge para la página web")
    a.add_argument("accion", choices=["json", "guardar"])
    a.add_argument("--conf", required=True)
    a.add_argument("--variables", default="")
    a.add_argument("--medios")
    a = a.parse_args()
    if a.accion == "json":
        datos = describir(leer_variables(a.variables), leer_valores(sys.stdin.read()), a.conf)
        print(json.dumps(datos, ensure_ascii=False))
        return
    try:
        peticion = json.loads(sys.stdin.read() or "{}")
        limpios, copia = guardar(a.conf, a.medios, peticion)
    except ValueError:
        sys.exit("Petición no válida")
    except Invalido as e:
        sys.exit(str(e))
    print("Guardado: " + ", ".join(limpios))
    print(f"La configuración anterior queda en {copia}")
    if any(n in limpios for n in REINDEXAN):
        cuales = " y ".join(n for n in REINDEXAN if n in limpios)
        print(f"Has cambiado {cuales}: al aplicarlo, el DLNA indexará todo de nuevo")


if __name__ == "__main__":
    main()
