import os
import subprocess
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
MEDIOS = RAIZ / "bin" / "medios"
COMANDOS = ["on", "off", "estado", "progreso", "reescanear", "buscar", "logs", "actualizar", "version", "ayuda"]
CONFIG_BUENA = 'SERVIDOR=100.64.0.10\nUSUARIO_SSH=usuario\nRUTA_MEDIOS=/mnt/media\nCARPETAS=("Movies" "Tv Shows")\n'


class Medios(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.conf = self.dir / "config"
        self.share = self.dir / "share"
        self.share.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def medios(self, *args, config=None):
        if config is not None:
            self.conf.write_text(config)
        env = {
            "PATH": os.environ["PATH"],
            "HOME": str(self.dir),
            "LANG": "C.UTF-8",
            "MEDIA_BRIDGE_CONFIG": str(self.conf),
            "MEDIA_BRIDGE_SHARE": str(self.share),
        }
        r = subprocess.run(["bash", str(MEDIOS), *args], capture_output=True, text=True, env=env, timeout=20)
        return r.returncode, r.stdout + r.stderr


class Ayuda(Medios):
    def test_h_sin_configuracion(self):
        for opcion in ("-h", "--help", "ayuda"):
            with self.subTest(opcion=opcion):
                rc, out = self.medios(opcion)
                self.assertEqual(rc, 0)
                self.assertIn("Uso: medios <comando>", out)
                self.assertIn(str(self.conf), out)
                for c in COMANDOS:
                    self.assertRegex(out, rf"(?m)^  {c}\b")

    def test_ayuda_de_cada_comando(self):
        for c in COMANDOS:
            with self.subTest(comando=c):
                rc, out = self.medios("ayuda", c)
                self.assertEqual(rc, 0)
                self.assertTrue(out.startswith(f"medios {c}"), out)

    def test_comando_con_h(self):
        rc, out = self.medios("on", "-h")
        self.assertEqual(rc, 0)
        self.assertTrue(out.startswith("medios on"))
        self.assertIn("--forzar", out)

    def test_ayuda_de_un_comando_desconocido(self):
        rc, out = self.medios("ayuda", "volar")
        self.assertEqual(rc, 1)
        self.assertIn('No conozco el comando "volar"', out)
        self.assertIn("Uso: medios <comando>", out)


class Version(Medios):
    def test_version_sin_configuracion(self):
        (self.share / "VERSION").write_text("9.8.7\n")
        rc, out = self.medios("version")
        self.assertEqual(rc, 0)
        self.assertEqual(out, "9.8.7\n")

    def test_version_sin_fichero(self):
        rc, out = self.medios("version")
        self.assertEqual(rc, 0)
        self.assertEqual(out, "desconocida\n")

    def test_version_del_repo(self):
        self.assertRegex((RAIZ / "VERSION").read_text(), r"^\d+\.\d+\.\d+\n$")


class Configuracion(Medios):
    def test_falta_la_configuracion(self):
        rc, out = self.medios("estado")
        self.assertEqual(rc, 1)
        self.assertIn(f"Falta la configuración: {self.conf}", out)

    def test_faltan_variables_obligatorias(self):
        for var in ("SERVIDOR", "USUARIO_SSH", "RUTA_MEDIOS"):
            with self.subTest(var=var):
                config = "\n".join(l for l in CONFIG_BUENA.splitlines() if not l.startswith(var + "="))
                rc, out = self.medios("estado", config=config)
                self.assertNotEqual(rc, 0)
                self.assertIn(f"Falta {var} en {self.conf}", out)

    def test_falta_carpetas(self):
        config = "\n".join(l for l in CONFIG_BUENA.splitlines() if not l.startswith("CARPETAS="))
        rc, out = self.medios("estado", config=config)
        self.assertEqual(rc, 1)
        self.assertIn(f"Falta CARPETAS en {self.conf}", out)

    def test_reescaneo_no_numerico(self):
        for valor in ("una-hora", "-5", "1.5"):
            with self.subTest(valor=valor):
                rc, out = self.medios("estado", config=CONFIG_BUENA + f"REESCANEO_SEGUNDOS={valor}\n")
                self.assertEqual(rc, 1)
                self.assertIn("REESCANEO_SEGUNDOS tiene que ser un número de segundos", out)

    def test_opcion_desconocida(self):
        for args in (("volar",), ("-x",), ("--lo-que-sea",)):
            with self.subTest(args=args):
                rc, out = self.medios(*args, config=CONFIG_BUENA)
                self.assertEqual(rc, 1)
                self.assertTrue(out.startswith("Uso: medios on | off"), out)
                self.assertIn("medios -h", out)

    def test_buscar_sin_texto(self):
        rc, out = self.medios("buscar", config=CONFIG_BUENA)
        self.assertEqual(rc, 1)
        self.assertIn("Uso: medios", out)


if __name__ == "__main__":
    unittest.main()


class Opciones(Medios):
    def test_opcion_desconocida_en_estado(self):
        rc, out = self.medios("estado", "--forzar", config=CONFIG_BUENA)
        self.assertEqual(rc, 1)
        self.assertIn('No conozco la opción "--forzar"', out)
        self.assertTrue(out.splitlines()[2].startswith("medios estado"), out)

    def test_ayuda_de_on_explica_jellyfin(self):
        rc, out = self.medios("ayuda", "on")
        self.assertEqual(rc, 0)
        self.assertIn("-j o --jellyfin", out)
        self.assertIn("qrencode", out)

    def test_logs_con_parte_desconocida(self):
        rc, out = self.medios("logs", "tostadora", config=CONFIG_BUENA)
        self.assertEqual(rc, 1)
        self.assertIn('No conozco "tostadora"', out)
        self.assertIn("medios logs [montaje|dlna|reenvios|reescaneo] [-f]", out)

    def test_logs_en_docker(self):
        self.conf.write_text(CONFIG_BUENA)
        env = {
            "PATH": os.environ["PATH"],
            "HOME": str(self.dir),
            "LANG": "C.UTF-8",
            "MEDIA_BRIDGE_CONFIG": str(self.conf),
            "MEDIA_BRIDGE_SHARE": str(self.share),
            "MEDIA_BRIDGE_DOCKER": "1",
        }
        r = subprocess.run(["bash", str(MEDIOS), "logs"], capture_output=True, text=True, env=env, timeout=20)
        self.assertEqual(r.returncode, 1)
        self.assertIn("docker compose logs -f", r.stdout)
