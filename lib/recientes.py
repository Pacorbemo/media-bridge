import argparse
import os
import sys
import time
from pathlib import Path


def leer_entrada(lineas):
    fechas = {}
    for linea in lineas:
        linea = linea.rstrip("\n")
        if "\t" not in linea:
            continue
        fecha, ruta = linea.split("\t", 1)
        try:
            fechas[ruta] = float(fecha)
        except ValueError:
            continue
    return fechas


def leer_llegadas(fichero):
    llegadas = {}
    with open(fichero, encoding="utf-8", errors="surrogateescape") as f:
        for linea in f:
            linea = linea.rstrip("\n")
            if "\t" not in linea:
                continue
            fecha, ruta = linea.split("\t", 1)
            try:
                llegadas[ruta] = float(fecha)
            except ValueError:
                continue
    return llegadas


def guardar_llegadas(fichero, llegadas):
    tmp = f"{fichero}.tmp"
    with open(tmp, "w", encoding="utf-8", errors="surrogateescape") as f:
        for ruta, fecha in sorted(llegadas.items()):
            f.write(f"{fecha:.0f}\t{ruta}\n")
    os.replace(tmp, fichero)


def calcular_llegadas(fechas, anteriores, ahora):
    if anteriores is None:
        return dict(fechas)
    return {ruta: anteriores.get(ruta, ahora) for ruta in fechas}


def nombre_visible(ruta):
    partes = ruta.split("/")
    extension = Path(partes[-1]).suffix
    if len(partes) >= 3:
        return partes[-2], extension
    return Path(partes[-1]).stem, extension


def elegir(llegadas, cantidad):
    orden = sorted(llegadas.items(), key=lambda par: (-par[1], par[0]))
    elegidos = {}
    ancho = max(2, len(str(cantidad)))
    for i, (ruta, _) in enumerate(orden[:cantidad], 1):
        base, extension = nombre_visible(ruta)
        nombre = f"{i:0{ancho}d} · {base}{extension}"
        elegidos[nombre] = ruta
    return elegidos


def aplicar(destino, montaje, elegidos):
    destino.mkdir(parents=True, exist_ok=True)
    deseados = {nombre: str(montaje / ruta) for nombre, ruta in elegidos.items()}
    for actual in destino.iterdir():
        if not actual.is_symlink():
            continue
        if deseados.get(actual.name) != os.readlink(actual):
            actual.unlink()
    for nombre, objetivo in deseados.items():
        enlace = destino / nombre
        if not enlace.is_symlink():
            enlace.symlink_to(objetivo)


def main():
    p = argparse.ArgumentParser(description="Rehace los enlaces de Añadidos recientemente")
    p.add_argument("--llegadas", required=True)
    p.add_argument("--destino", required=True)
    p.add_argument("--montaje", required=True)
    p.add_argument("--cantidad", type=int, required=True)
    p.add_argument("--ahora", type=float, default=None)
    a = p.parse_args()

    entrada = sys.stdin.buffer.read().decode("utf-8", errors="surrogateescape")
    fechas = leer_entrada(entrada.splitlines())
    if not fechas:
        print("El servidor no ha devuelto ningún vídeo; dejo Añadidos recientemente como estaba")
        return 0

    anteriores = leer_llegadas(a.llegadas) if os.path.exists(a.llegadas) else None
    ahora = a.ahora if a.ahora is not None else time.time()
    llegadas = calcular_llegadas(fechas, anteriores, ahora)
    guardar_llegadas(a.llegadas, llegadas)

    elegidos = elegir(llegadas, a.cantidad)
    aplicar(Path(a.destino), Path(a.montaje), elegidos)
    print(f"Añadidos recientemente: {len(elegidos)} vídeos")
    for nombre in sorted(elegidos):
        print(f"  {nombre}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
