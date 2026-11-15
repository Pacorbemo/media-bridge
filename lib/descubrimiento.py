import argparse
import json
import socket
import sys
import time
import urllib.request

PREGUNTA = "who is jellyfinserver?"
CADUCIDAD = 300


def registrar(texto):
    print(texto, flush=True)


def es_pregunta(datos):
    return PREGUNTA in datos.decode("utf-8", "replace").lower()


def ip_hacia(destino):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect((destino, 9))
        return s.getsockname()[0]


def respuesta(direccion, servidor):
    return json.dumps(
        {"Address": direccion, "Id": servidor["Id"], "Name": servidor["Name"], "EndpointAddress": None},
        separators=(",", ":"),
    ).encode()


def leer_servidor(url):
    with urllib.request.urlopen(url, timeout=5) as r:
        datos = json.load(r)
    ident = datos.get("Id") or datos.get("id")
    nombre = datos.get("ServerName") or datos.get("serverName")
    if not ident or not nombre:
        raise ValueError("la respuesta no trae Id y ServerName")
    return {"Id": ident, "Name": nombre}


class Respondedor:
    def __init__(self, url_info, puerto_jellyfin):
        self.url_info = url_info
        self.puerto_jellyfin = puerto_jellyfin
        self.servidor = None
        self.leido = 0.0

    def servidor_actual(self):
        if self.servidor and time.monotonic() - self.leido < CADUCIDAD:
            return self.servidor
        try:
            servidor = leer_servidor(self.url_info)
        except Exception as e:
            registrar(f"No puedo leer {self.url_info} ({e}); no contesto hasta que responda")
            self.servidor = None
            return None
        if servidor != self.servidor:
            registrar(f"Servidor Jellyfin: {servidor['Name']} ({servidor['Id']})")
        self.servidor = servidor
        self.leido = time.monotonic()
        return servidor

    def atender(self, datos, origen):
        if not es_pregunta(datos):
            return None
        servidor = self.servidor_actual()
        if servidor is None:
            return None
        direccion = f"http://{ip_hacia(origen[0])}:{self.puerto_jellyfin}"
        registrar(f"{origen[0]} busca Jellyfin; le contesto {direccion}")
        return respuesta(direccion, servidor)


def main():
    p = argparse.ArgumentParser(description="Contesta al descubrimiento de las apps de Jellyfin en nombre del servidor")
    p.add_argument("--info", required=True, help="URL de /System/Info/Public del servidor")
    p.add_argument("--puerto-jellyfin", type=int, required=True, help="puerto de Jellyfin en este equipo")
    p.add_argument("--escucha", default="0.0.0.0", help="dirección en la que escuchar")
    p.add_argument("--puerto", type=int, default=7359, help="puerto UDP del descubrimiento")
    a = p.parse_args()

    respondedor = Respondedor(a.info, a.puerto_jellyfin)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.bind((a.escucha, a.puerto))
        except OSError as e:
            sys.exit(f"No puedo escuchar en el puerto {a.puerto}/udp: {e}")
        registrar(f"Contesto a las apps de Jellyfin en el puerto {a.puerto}/udp")
        respondedor.servidor_actual()
        while True:
            datos, origen = s.recvfrom(2048)
            try:
                contestacion = respondedor.atender(datos, origen)
            except OSError as e:
                registrar(f"No pude contestar a {origen[0]}: {e}")
                continue
            if contestacion:
                s.sendto(contestacion, origen)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
