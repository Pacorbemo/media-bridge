import http.client
import importlib.util
import json
import re
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parent.parent / "lib" / "web.py"
spec = importlib.util.spec_from_file_location("web", SCRIPT)
web = importlib.util.module_from_spec(spec)
spec.loader.exec_module(web)

ESTADO = {
    "version": "1.2.3",
    "docker": False,
    "encendido": True,
    "ip": "192.168.1.12",
    "servicios": [{"nombre": "media-bridge-dlna.service", "estado": "active"}],
    "reenvios": [{"puerto": 8096, "activo": True, "url": "http://192.168.1.12:8096"}],
    "jellyfin": {"puerto": 8096, "previsto": True, "activo": True, "url": "http://192.168.1.12:8096",
                 "conexiones": ["192.168.1.50"], "descubrimiento": True},
    "dlna": {"previsto": True, "activo": True, "nombre": "Casa", "reescaneo": "Reescaneo: cada 3600 s",
             "viendo": False, "indexando": False, "videos": 120, "aparatos": []},
    "recientes": {"activo": False, "cantidad": 10, "carpetas": ["Movies"], "lista": []},
}

MEDIOS_FALSO = """#!/usr/bin/env bash
d=$(dirname "$0")
printf '%s\\n' "$*" >> "$d/llamadas"
[ -f "$d/salida-$1" ] && cat "$d/salida-$1"
exit "$(cat "$d/codigo-$1" 2>/dev/null || echo 0)"
"""


class Pagina(unittest.TestCase):
    def setUp(self):
        silencio = mock.patch.object(web, "registrar")
        silencio.start()
        self.addCleanup(silencio.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.medios = self.dir / "medios"
        self.medios.write_text(MEDIOS_FALSO)
        self.medios.chmod(0o755)
        self.responder("_estado-json", json.dumps(ESTADO))
        self.servidor = web.Servidor(0, str(self.medios))
        self.puerto = self.servidor.server_address[1]
        self.hilo = threading.Thread(target=self.servidor.serve_forever, daemon=True)
        self.hilo.start()

    def tearDown(self):
        self.servidor.shutdown()
        self.servidor.server_close()
        self.tmp.cleanup()

    def responder(self, comando, salida, codigo=0):
        (self.dir / f"salida-{comando}").write_text(salida)
        (self.dir / f"codigo-{comando}").write_text(str(codigo))

    def llamadas(self):
        f = self.dir / "llamadas"
        return f.read_text().splitlines() if f.exists() else []

    def peticion(self, metodo, ruta, cuerpo=None, host=None, origen="propio", token="propio"):
        host = host or f"127.0.0.1:{self.puerto}"
        cabeceras = {"Host": host}
        if origen == "propio":
            origen = f"http://{host}"
        if origen:
            cabeceras["Origin"] = origen
        if token == "propio":
            token = self.servidor.token
        if token:
            cabeceras["X-Token"] = token
        datos = None
        if cuerpo is not None:
            datos = json.dumps(cuerpo).encode()
            cabeceras["Content-Type"] = "application/json"
        c = http.client.HTTPConnection("127.0.0.1", self.puerto, timeout=20)
        try:
            c.request(metodo, ruta, body=datos, headers=cabeceras)
            r = c.getresponse()
            texto = r.read().decode()
            return r.status, dict(r.getheaders()), texto
        finally:
            c.close()

    def json(self, *args, **kwargs):
        estado, _, texto = self.peticion(*args, **kwargs)
        return estado, json.loads(texto)


class Seguridad(Pagina):
    def test_solo_escucha_en_local(self):
        self.assertEqual(self.servidor.server_address[0], "127.0.0.1")

    def test_pagina_con_token_y_sin_recursos_externos(self):
        estado, cabeceras, html = self.peticion("GET", "/", token=None, origen=None)
        self.assertEqual(estado, 200)
        self.assertIn(f'<meta name="token" content="{self.servidor.token}">', html)
        self.assertNotRegex(html, r"https?://")
        self.assertNotIn("__NONCE__", html)
        self.assertIn(f"'nonce-{self.servidor.nonce}'", cabeceras["Content-Security-Policy"])
        self.assertIn("frame-ancestors 'none'", cabeceras["Content-Security-Policy"])
        self.assertNotIn("tele ", html.lower())

    def test_token_distinto_en_cada_arranque(self):
        otro = web.Servidor(0, str(self.medios))
        try:
            self.assertNotEqual(otro.token, self.servidor.token)
        finally:
            otro.server_close()

    def test_rechaza_otro_host(self):
        for host in ("ejemplo.com", "192.168.1.12:8787", "127.0.0.1.ejemplo.com"):
            with self.subTest(host=host):
                estado, _, _ = self.peticion("GET", "/", host=host)
                self.assertEqual(estado, 403)
                estado, _, _ = self.peticion("POST", "/api/apagar", {}, host=host)
                self.assertEqual(estado, 403)
        self.assertEqual(self.llamadas(), [])

    def test_acepta_localhost(self):
        estado, _, _ = self.peticion("GET", "/", host=f"localhost:{self.puerto}")
        self.assertEqual(estado, 200)

    def test_estado_sin_token(self):
        for token in (None, "falso"):
            with self.subTest(token=token):
                estado, datos = self.json("GET", "/api/estado", token=token)
                self.assertEqual(estado, 403)
                self.assertIn("recárgala", datos["error"])
        self.assertEqual(self.llamadas(), [])

    def test_acciones_desde_otra_web(self):
        casos = [
            {"origen": None},
            {"origen": "http://malvado.ejemplo"},
            {"origen": "null"},
            {"token": None},
            {"token": "falso"},
        ]
        for caso in casos:
            with self.subTest(**caso):
                estado, _ = self.json("POST", "/api/apagar", {}, **caso)
                self.assertEqual(estado, 403)
        self.assertEqual(self.llamadas(), [])

    def test_acciones_solo_por_post(self):
        for accion in ("encender", "apagar", "reescanear"):
            with self.subTest(accion=accion):
                estado, _ = self.json("GET", f"/api/{accion}")
                self.assertEqual(estado, 404)
        self.assertEqual(self.llamadas(), [])

    def test_cuerpo_demasiado_grande(self):
        estado, _ = self.json("POST", "/api/buscar", {"texto": "x" * 5000})
        self.assertEqual(estado, 400)


class Estado(Pagina):
    def test_devuelve_el_estado_de_medios(self):
        with mock.patch.object(web, "generar_qr", return_value="<svg>qr</svg>"):
            estado, datos = self.json("GET", "/api/estado")
        self.assertEqual(estado, 200)
        self.assertEqual(datos["version"], "1.2.3")
        self.assertEqual(datos["jellyfin"]["conexiones"], ["192.168.1.50"])
        self.assertEqual(datos["qr"], "<svg>qr</svg>")
        self.assertIsNone(datos["progreso"])
        self.assertIsNone(datos["accion"])
        self.assertEqual(self.llamadas(), ["_estado-json"])

    def test_sin_qrencode_no_hay_qr(self):
        with mock.patch.object(web.shutil, "which", return_value=None):
            _, datos = self.json("GET", "/api/estado")
        self.assertIsNone(datos["qr"])
        self.assertFalse(datos["qrencode"])

    def test_error_de_medios(self):
        self.responder("_estado-json", "Falta la configuración: /x/config\n", 1)
        estado, datos = self.json("GET", "/api/estado")
        self.assertEqual(estado, 200)
        self.assertEqual(datos, {"error": "Falta la configuración: /x/config"})

    def test_respuesta_que_no_es_json(self):
        self.responder("_estado-json", "basura")
        _, datos = self.json("GET", "/api/estado")
        self.assertIn("No entiendo", datos["error"])


class Acciones(Pagina):
    def test_cada_accion_llama_a_medios(self):
        for accion, comando in (("encender", "on"), ("apagar", "off"), ("reescanear", "reescanear")):
            with self.subTest(accion=accion):
                self.responder(comando, f"salida de {comando}\n")
                estado, datos = self.json("POST", f"/api/{accion}", {})
                self.assertEqual(estado, 200)
                self.assertEqual(datos, {"codigo": 0, "salida": f"salida de {comando}\n"})
                self.assertEqual(self.llamadas()[-1], comando)

    def test_encender_con_fallos(self):
        self.responder("on", "Comprobando antes de encender:\n  ✘ No puedo entrar por SSH\n", 1)
        _, datos = self.json("POST", "/api/encender", {})
        self.assertEqual(datos["codigo"], 1)
        self.assertIn("✘ No puedo entrar por SSH", datos["salida"])

    def test_una_accion_a_la_vez(self):
        self.servidor.cerrojo_accion.acquire()
        self.servidor.accion = "encender"
        try:
            estado, datos = self.json("POST", "/api/apagar", {})
        finally:
            self.servidor.cerrojo_accion.release()
        self.assertEqual(estado, 409)
        self.assertIn("encender", datos["error"])
        self.assertEqual(self.llamadas(), [])

    def test_accion_desconocida(self):
        estado, _ = self.json("POST", "/api/borrar", {})
        self.assertEqual(estado, 404)

    def test_buscar(self):
        self.responder("buscar", "Buscado en 3 vídeos del servidor\n")
        estado, datos = self.json("POST", "/api/buscar", {"texto": "  el hobbit  "})
        self.assertEqual(estado, 200)
        self.assertEqual(datos["salida"], "Buscado en 3 vídeos del servidor\n")
        self.assertEqual(self.llamadas(), ["buscar el hobbit"])

    def test_buscar_sin_texto(self):
        for cuerpo in ({}, {"texto": "   "}, {"texto": 5}):
            with self.subTest(cuerpo=cuerpo):
                estado, _ = self.json("POST", "/api/buscar", cuerpo)
                self.assertEqual(estado, 400)
        self.assertEqual(self.llamadas(), [])


class Progreso(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        medios = Path(self.tmp.name) / "medios"
        medios.write_text("#!/bin/sh\n[ \"$1\" = _total-videos ] && echo 1000\n")
        medios.chmod(0o755)
        self.ahora = 0.0
        self.progreso = web.Progreso(str(medios), reloj=lambda: self.ahora)

    def tearDown(self):
        self.tmp.cleanup()

    def esperar_total(self):
        for _ in range(100):
            if self.progreso.total is not None:
                return
            time.sleep(0.05)
        self.fail("no llegó el total")

    def test_sin_indexar(self):
        self.assertIsNone(self.progreso.calcular({"indexando": False, "videos": 10}))

    def test_ritmo_y_tiempo_restante(self):
        primero = self.progreso.calcular({"indexando": True, "videos": 100})
        self.assertEqual(primero["videos"], 100)
        self.assertIsNone(primero["ritmo"])
        self.esperar_total()
        self.ahora = 30
        p = self.progreso.calcular({"indexando": True, "videos": 160})
        self.assertEqual(p, {"videos": 160, "total": 1000, "porcentaje": 16, "ritmo": 120, "minutos": 7})

    def test_vuelve_a_empezar_al_terminar(self):
        self.progreso.calcular({"indexando": True, "videos": 100})
        self.esperar_total()
        self.assertIsNone(self.progreso.calcular({"indexando": False}))
        self.assertIsNone(self.progreso.total)
        self.assertIsNone(self.progreso.inicio)


class Qr(unittest.TestCase):
    def test_svg_sin_cabecera_xml(self):
        if not web.shutil.which("qrencode"):
            self.skipTest("qrencode no está instalado")
        svg = web.generar_qr("http://192.168.1.12:8096")
        self.assertTrue(svg.startswith("<svg"), svg[:40])
        self.assertTrue(re.search(r"</svg>\s*$", svg))


if __name__ == "__main__":
    unittest.main()
