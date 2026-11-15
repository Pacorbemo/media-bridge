import importlib.util
import json
import os
import select
import socket
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "lib" / "descubrimiento.py"
spec = importlib.util.spec_from_file_location("descubrimiento", SCRIPT)
descubrimiento = importlib.util.module_from_spec(spec)
spec.loader.exec_module(descubrimiento)

INFO = {"LocalAddress": "http://100.64.0.10:8096", "ServerName": "Servidor de casa", "Version": "10.10.7",
        "ProductName": "Jellyfin Server", "Id": "0123456789abcdef0123456789abcdef", "StartupWizardCompleted": True}


def puerto_libre(tipo):
    with socket.socket(socket.AF_INET, tipo) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class JellyfinFalso:
    def __init__(self, cuerpo):
        self.peticiones = []
        falso = self

        class Manejador(BaseHTTPRequestHandler):
            def do_GET(self):
                falso.peticiones.append(self.path)
                datos = json.dumps(cuerpo).encode() if self.path == "/System/Info/Public" else b""
                self.send_response(200 if datos else 404)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(datos)

            def log_message(self, *args):
                pass

        self.servidor = ThreadingHTTPServer(("127.0.0.1", 0), Manejador)
        self.url = f"http://127.0.0.1:{self.servidor.server_address[1]}/System/Info/Public"
        threading.Thread(target=self.servidor.serve_forever, daemon=True).start()

    def cerrar(self):
        self.servidor.shutdown()
        self.servidor.server_close()


class Funciones(unittest.TestCase):
    def test_reconoce_la_pregunta(self):
        for datos in (b"who is JellyfinServer?", b"WHO IS JELLYFINSERVER?", b"hola, who is JellyfinServer? adios"):
            with self.subTest(datos=datos):
                self.assertTrue(descubrimiento.es_pregunta(datos))

    def test_ignora_otras_preguntas(self):
        for datos in (b"who is EmbyServer?", b"who is JellyfinServer", b"", b"\xff\xfe\x00"):
            with self.subTest(datos=datos):
                self.assertFalse(descubrimiento.es_pregunta(datos))

    def test_json_de_la_respuesta(self):
        datos = descubrimiento.respuesta("http://192.168.1.50:8096", {"Id": "abc", "Name": "Casa"})
        self.assertEqual(
            datos,
            b'{"Address":"http://192.168.1.50:8096","Id":"abc","Name":"Casa","EndpointAddress":null}',
        )

    def test_lee_id_y_nombre_del_servidor(self):
        falso = JellyfinFalso(INFO)
        try:
            self.assertEqual(
                descubrimiento.leer_servidor(falso.url),
                {"Id": INFO["Id"], "Name": INFO["ServerName"]},
            )
        finally:
            falso.cerrar()

    def test_no_inventa_si_faltan_datos(self):
        falso = JellyfinFalso({"Version": "10.10.7"})
        try:
            with self.assertRaises(ValueError):
                descubrimiento.leer_servidor(falso.url)
        finally:
            falso.cerrar()


class Respondedor(unittest.TestCase):
    def arrancar(self, url_info):
        self.puerto = puerto_libre(socket.SOCK_DGRAM)
        self.proceso = subprocess.Popen(
            [sys.executable, "-u", str(SCRIPT), "--info", url_info, "--puerto-jellyfin", "8096",
             "--escucha", "127.0.0.1", "--puerto", str(self.puerto)],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        self.addCleanup(self.parar)
        self.salida = [self.leer_linea()]
        self.assertIn(f"Contesto a las apps de Jellyfin en el puerto {self.puerto}/udp", self.salida[0])
        self.salida.append(self.leer_linea())
        self.cliente = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.cliente.bind(("127.0.0.1", 0))
        self.addCleanup(self.cliente.close)

    def leer_linea(self, espera=5):
        listo, _, _ = select.select([self.proceso.stdout], [], [], espera)
        self.assertTrue(listo, "el respondedor no ha escrito nada")
        return self.proceso.stdout.readline()

    def parar(self):
        self.proceso.terminate()
        self.proceso.wait(5)
        self.proceso.stdout.close()

    def preguntar(self, datos, espera=3):
        self.cliente.settimeout(espera)
        self.cliente.sendto(datos, ("127.0.0.1", self.puerto))
        try:
            return self.cliente.recvfrom(2048)
        except socket.timeout:
            return None

    def test_contesta_a_la_pregunta(self):
        falso = JellyfinFalso(INFO)
        self.addCleanup(falso.cerrar)
        self.arrancar(falso.url)
        self.assertIn("Servidor Jellyfin: Servidor de casa", self.salida[1])
        vuelta = self.preguntar(b"who is JellyfinServer?")
        self.assertIsNotNone(vuelta)
        datos, origen = vuelta
        self.assertEqual(origen, ("127.0.0.1", self.puerto))
        self.assertEqual(json.loads(datos), {
            "Address": "http://127.0.0.1:8096",
            "Id": INFO["Id"],
            "Name": "Servidor de casa",
            "EndpointAddress": None,
        })
        self.assertIn("/System/Info/Public", falso.peticiones)

    def test_ignora_otras_preguntas(self):
        falso = JellyfinFalso(INFO)
        self.addCleanup(falso.cerrar)
        self.arrancar(falso.url)
        self.assertIsNone(self.preguntar(b"who is EmbyServer?", espera=0.5))
        self.assertIsNone(self.preguntar(b"hola", espera=0.5))
        self.assertIsNotNone(self.preguntar(b"who is JellyfinServer?"))

    def test_no_contesta_sin_servidor(self):
        self.arrancar(f"http://127.0.0.1:{puerto_libre(socket.SOCK_STREAM)}/System/Info/Public")
        self.assertIn("No puedo leer", self.salida[1])
        self.assertIsNone(self.preguntar(b"who is JellyfinServer?", espera=1))
        self.assertIn("No puedo leer", self.leer_linea())

    def test_puerto_ocupado(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as ocupado:
            ocupado.bind(("127.0.0.1", 0))
            puerto = ocupado.getsockname()[1]
            r = subprocess.run(
                [sys.executable, str(SCRIPT), "--info", "http://127.0.0.1:1/", "--puerto-jellyfin", "8096",
                 "--escucha", "127.0.0.1", "--puerto", str(puerto)],
                capture_output=True, text=True, timeout=10, env={**os.environ},
            )
        self.assertEqual(r.returncode, 1)
        self.assertIn(f"No puedo escuchar en el puerto {puerto}/udp", r.stderr)


if __name__ == "__main__":
    unittest.main()
