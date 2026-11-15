import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SCRIPT = RAIZ / "lib" / "config.py"
spec = importlib.util.spec_from_file_location("config", SCRIPT)
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)

CONFIG = """SERVIDOR=100.64.0.1
USUARIO_SSH=yo
RUTA_MEDIOS=/srv/media
# las carpetas
CARPETAS=("Movies"
  "Tv Shows")
NOMBRE_DLNA=Casa  # nombre
REENVIOS="8096"
"""


class Variables(unittest.TestCase):
    def test_variables_de_la_ayuda(self):
        texto = subprocess.run(
            ["bash", "-c", f'source <(sed -n "/^variables_config() {{/,/^}}/p" {RAIZ}/bin/medios); variables_config'],
            capture_output=True,
            text=True,
        ).stdout
        variables = {v["nombre"]: v for v in config.leer_variables(texto)}
        for nombre in config.EDITABLES:
            self.assertIn(nombre, variables)
        self.assertIsNone(variables["SERVIDOR"]["defecto"])
        self.assertEqual(variables["DLNA"]["defecto"], "si")
        self.assertEqual(variables["REENVIOS"]["defecto"], "")

    def test_lo_que_rompe_la_conexion_no_se_edita(self):
        for nombre in ("SERVIDOR", "USUARIO_SSH", "RUTA_MEDIOS", "CLAVE_SSH", "PUNTO_MONTAJE", "DB_DLNA", "PUERTO_WEB"):
            self.assertNotIn(nombre, config.EDITABLES)

    def test_leer_valores(self):
        datos = "\0".join(["CARPETAS", "a", "2", "Movies", "Tv Shows", "DLNA", "s", "no", "VACIA", "a", "0", "NADA", "s", ""]) + "\0"
        self.assertEqual(
            config.leer_valores(datos),
            {"CARPETAS": ["Movies", "Tv Shows"], "DLNA": "no", "VACIA": [], "NADA": ""},
        )


class Validar(unittest.TestCase):
    def test_valores_buenos(self):
        casos = [
            ("DLNA", "no", "no"),
            ("PUERTO_DLNA", " 8200 ", "8200"),
            ("REESCANEO_SEGUNDOS", "0", "0"),
            ("RECIENTES_CANTIDAD", "25", "25"),
            ("REENVIOS", "8096, 8920 8096", "8096 8920"),
            ("REENVIOS", "", ""),
            ("NOMBRE_DLNA", ' Casa de "Ana" $HOME ', 'Casa de "Ana" $HOME'),
            ("INTERFAZ", "", ""),
            ("INTERFAZ", "wlan0", "wlan0"),
            ("EXTENSIONES", "mkv  mp4", "mkv mp4"),
            ("CARPETAS", ["Movies", "Tv Shows", "Movies"], ["Movies", "Tv Shows"]),
            ("RECIENTES_CARPETAS", [], []),
        ]
        for nombre, valor, esperado in casos:
            with self.subTest(nombre=nombre, valor=valor):
                self.assertEqual(config.validar(nombre, valor), esperado)

    def test_valores_malos(self):
        casos = [
            ("SERVIDOR", "1.2.3.4"),
            ("PUNTO_MONTAJE", "/"),
            ("INVENTADA", "x"),
            ("DLNA", "$(touch /tmp/x)"),
            ("DLNA", True),
            ("PUERTO_DLNA", "0"),
            ("PUERTO_DLNA", "65536"),
            ("PUERTO_DLNA", "80; rm -rf ~"),
            ("RECIENTES_CANTIDAD", "0"),
            ("REENVIOS", "8096 abc"),
            ("NOMBRE_DLNA", ""),
            ("NOMBRE_DLNA", "dos\nlíneas"),
            ("NOMBRE_DLNA", "x" * 65),
            ("INTERFAZ", "wlan0; reboot"),
            ("EXTENSIONES", "mkv *"),
            ("CARPETAS", []),
            ("CARPETAS", "Movies"),
            ("CARPETAS", ["../etc"]),
            ("CARPETAS", ["a/b"]),
            ("CARPETAS", [".."]),
            ("CARPETAS", ["con\nsalto"]),
        ]
        for nombre, valor in casos:
            with self.subTest(nombre=nombre, valor=valor):
                with self.assertRaises(config.Invalido):
                    config.validar(nombre, valor)


class Escribir(unittest.TestCase):
    def bash(self, texto, nombre):
        r = subprocess.run(
            ["bash", "-c", 'source /dev/stdin; declare -p "$1"', "_", nombre],
            input=texto,
            capture_output=True,
            text=True,
        )
        return r.stdout

    def test_comillas_seguras_para_bash(self):
        for valor in ['Casa de "Ana"', "$(touch /tmp/x)", "`id`", "a\\b", "it's", "Salón · 2"]:
            with self.subTest(valor=valor):
                texto = config.aplicar("", {"NOMBRE_DLNA": valor})
                r = subprocess.run(
                    ["bash", "-c", 'source /dev/stdin; printf %s "$NOMBRE_DLNA"'],
                    input=texto,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(r.stdout, valor)
                lista = config.aplicar("", {"CARPETAS": [valor, "Movies"]})
                r = subprocess.run(
                    ["bash", "-c", 'source /dev/stdin; printf "%s|" "${CARPETAS[@]}"'],
                    input=lista,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(r.stdout, f"{valor}|Movies|")

    def test_cambia_solo_lo_pedido(self):
        nuevo = config.aplicar(CONFIG, {"CARPETAS": ["Movies"], "NOMBRE_DLNA": "Salón", "RECIENTES": "si"})
        self.assertEqual(
            nuevo,
            'SERVIDOR=100.64.0.1\nUSUARIO_SSH=yo\nRUTA_MEDIOS=/srv/media\n# las carpetas\nCARPETAS=("Movies")\n'
            'NOMBRE_DLNA="Salón"\nREENVIOS="8096"\nRECIENTES=si\n',
        )

    def test_cambia_la_ultima_asignacion(self):
        texto = "DLNA=si\nDLNA=no\n"
        self.assertEqual(config.aplicar(texto, {"DLNA": "si"}), "DLNA=si\nDLNA=si\n")

    def test_vacios(self):
        self.assertEqual(config.aplicar("", {"REENVIOS": "", "RECIENTES_CARPETAS": []}), "REENVIOS=\nRECIENTES_CARPETAS=()\n")


class Guardar(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.conf = self.dir / "config"
        self.conf.write_text(CONFIG)
        self.conf.chmod(0o600)
        self.medios = self.dir / "medios"
        self.medios.write_text(
            '#!/usr/bin/env bash\n'
            'echo "$MEDIA_BRIDGE_CONFIG" > "$(dirname "$0")/validada"\n'
            'grep -q PUERTO_DLNA=1234 "$MEDIA_BRIDGE_CONFIG" && { echo "Puerto no válido en $MEDIA_BRIDGE_CONFIG: 1234"; exit 1; }\n'
            'exit 0\n'
        )
        self.medios.chmod(0o755)

    def guardar(self, cambios):
        return subprocess.run(
            ["python3", str(SCRIPT), "guardar", "--conf", str(self.conf), "--medios", str(self.medios)],
            input=json.dumps({"cambios": cambios}),
            capture_output=True,
            text=True,
        )

    def test_guarda_con_copia(self):
        r = self.guardar({"NOMBRE_DLNA": "Salón", "CARPETAS": ["Movies"]})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Guardado: NOMBRE_DLNA, CARPETAS", r.stdout)
        self.assertIn("indexará todo de nuevo", r.stdout)
        self.assertIn('NOMBRE_DLNA="Salón"', self.conf.read_text())
        self.assertEqual((self.dir / "config.bak").read_text(), CONFIG)
        self.assertEqual(self.conf.stat().st_mode & 0o777, 0o600)
        self.assertEqual((self.dir / "validada").read_text().strip(), str(self.dir / "config.nueva"))
        self.assertFalse((self.dir / "config.nueva").exists())

    def test_no_guarda_si_medios_la_rechaza(self):
        r = self.guardar({"PUERTO_DLNA": "1234"})
        self.assertEqual(r.returncode, 1)
        self.assertIn(f"No lo guardo: Puerto no válido en {self.conf}: 1234", r.stderr)
        self.assertEqual(self.conf.read_text(), CONFIG)
        self.assertFalse((self.dir / "config.bak").exists())
        self.assertFalse((self.dir / "config.nueva").exists())

    def test_no_guarda_valores_malos(self):
        for cambios in ({"SERVIDOR": "1.2.3.4"}, {"DLNA": "quizá"}, {}):
            with self.subTest(cambios=cambios):
                r = self.guardar(cambios)
                self.assertEqual(r.returncode, 1)
                self.assertEqual(self.conf.read_text(), CONFIG)
                self.assertFalse((self.dir / "validada").exists())

    def test_sin_configuracion(self):
        self.conf.unlink()
        r = self.guardar({"DLNA": "no"})
        self.assertEqual(r.returncode, 1)
        self.assertIn("Falta la configuración", r.stderr)


class ConMedios(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.share = self.dir / "share"
        self.share.mkdir()
        (self.share / "config.py").write_text(SCRIPT.read_text())
        self.conf = self.dir / "config"
        self.conf.write_text(CONFIG + f"DB_DLNA={self.dir}/db\n")
        self.env = {**os.environ, "MEDIA_BRIDGE_CONFIG": str(self.conf), "MEDIA_BRIDGE_SHARE": str(self.share)}

    def medios(self, *argumentos, entrada=""):
        return subprocess.run(
            ["bash", str(RAIZ / "bin" / "medios"), *argumentos],
            input=entrada,
            capture_output=True,
            text=True,
            env=self.env,
        )

    def test_config_json(self):
        r = self.medios("_config-json")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        datos = json.loads(r.stdout)
        variables = {v["nombre"]: v for v in datos["variables"]}
        self.assertEqual(datos["fichero"], str(self.conf))
        self.assertEqual(variables["CARPETAS"]["valor"], ["Movies", "Tv Shows"])
        self.assertEqual(variables["CARPETAS"]["tipo"], "carpetas")
        self.assertTrue(variables["NOMBRE_DLNA"]["fijada"])
        self.assertFalse(variables["DLNA"]["fijada"])
        self.assertIsNone(variables["DLNA"]["valor"])
        self.assertIsNone(variables["SERVIDOR"]["tipo"])
        self.assertEqual(datos["reindexan"], ["CARPETAS", "RECIENTES"])

    def test_guardar_valida_con_medios(self):
        r = self.medios("_config-guardar", entrada=json.dumps({"cambios": {"RECIENTES_CARPETAS": ["Otra"]}}))
        self.assertEqual(r.returncode, 1)
        self.assertIn('RECIENTES_CARPETAS incluye "Otra", que no está en CARPETAS', r.stdout + r.stderr)
        r = self.medios("_config-guardar", entrada=json.dumps({"cambios": {"RECIENTES": "si", "RECIENTES_CARPETAS": ["Movies"]}}))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = self.medios("_config-json")
        variables = {v["nombre"]: v for v in json.loads(r.stdout)["variables"]}
        self.assertEqual(variables["RECIENTES"]["valor"], "si")
        self.assertEqual(variables["RECIENTES_CARPETAS"]["valor"], ["Movies"])


if __name__ == "__main__":
    unittest.main()
