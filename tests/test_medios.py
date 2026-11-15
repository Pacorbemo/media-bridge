import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
MEDIOS = RAIZ / "bin" / "medios"
COMANDOS = ["on", "off", "estado", "progreso", "reescanear", "buscar", "comprobar", "web", "logs", "actualizar", "version", "ayuda"]
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

    def test_ayuda_menciona_los_temas(self):
        rc, out = self.medios("-h")
        self.assertIn("medios ayuda config", out)
        self.assertIn("medios ayuda problemas", out)
        self.assertIn("man medios", out)

    def test_ayuda_problemas(self):
        rc, out = self.medios("ayuda", "problemas")
        self.assertEqual(rc, 0)
        self.assertTrue(out.startswith("medios ayuda problemas"), out)
        self.assertIn("medios comprobar", out)
        self.assertIn("La televisión no encuentra el DLNA", out)


class AyudaConfig(Medios):
    def variables_del_script(self):
        texto = MEDIOS.read_text()
        variables = set(re.findall(r'^: "\$\{([A-Z_]+)(?::=|:\?)', texto, re.M))
        return variables | {"CARPETAS", "RECIENTES_CARPETAS"}

    def test_explica_todas_las_variables(self):
        rc, out = self.medios("ayuda", "config")
        self.assertEqual(rc, 0)
        nombres = set(re.findall(r"(?m)^([A-Z_]+) = ", out))
        self.assertEqual(nombres, self.variables_del_script())

    def test_explica_las_variables_de_config_example(self):
        rc, out = self.medios("ayuda", "config")
        ejemplo = set(re.findall(r"(?m)^([A-Z_]+)=", (RAIZ / "config.example").read_text()))
        nombres = set(re.findall(r"(?m)^([A-Z_]+) = ", out))
        self.assertEqual(nombres, ejemplo)

    def test_sin_configuracion_da_los_valores_por_defecto(self):
        rc, out = self.medios("ayuda", "config")
        self.assertEqual(rc, 0)
        self.assertIn(f"Todavía no hay configuración en {self.conf}", out)
        self.assertIn("SERVIDOR = ¡falta!", out)
        self.assertIn("PUERTO_DLNA = 8200\n", out)
        self.assertIn(f"PUNTO_MONTAJE = {self.dir}/media-bridge\n", out)

    def test_con_configuracion_da_sus_valores(self):
        config = CONFIG_BUENA + "NOMBRE_DLNA=GMK\nPUERTO_DLNA=8200\n"
        rc, out = self.medios("ayuda", "config", config=config)
        self.assertEqual(rc, 0)
        self.assertIn(f"Tu configuración está en {self.conf}", out)
        self.assertIn("SERVIDOR = 100.64.0.10\n", out)
        self.assertIn('CARPETAS = ("Movies" "Tv Shows")\n', out)
        self.assertIn("NOMBRE_DLNA = GMK  (por defecto: media-bridge)", out)
        self.assertIn("PUERTO_DLNA = 8200\n", out)
        self.assertIn("DLNA = si  (por defecto)", out)
        self.assertIn('INTERFAZ = ""  (por defecto)', out)

    def test_funciona_con_configuracion_no_valida(self):
        rc, out = self.medios("ayuda", "config", config="REESCANEO_SEGUNDOS=una-hora\n")
        self.assertEqual(rc, 0)
        self.assertIn("SERVIDOR = ¡falta!", out)
        self.assertIn("REESCANEO_SEGUNDOS = una-hora  (por defecto: 3600)", out)


class Sugerencias(Medios):
    def test_comando_con_errata(self):
        for config in (None, CONFIG_BUENA):
            with self.subTest(config=config is not None):
                rc, out = self.medios("estdo", config=config)
                self.assertEqual(rc, 1)
                self.assertIn('No conozco el comando "estdo". ¿Querías decir "estado"?', out)

    def test_ayuda_con_errata(self):
        for errata, buena in (("reescanar", "reescanear"), ("confg", "config"), ("problema", "problemas")):
            with self.subTest(errata=errata):
                rc, out = self.medios("ayuda", errata)
                self.assertEqual(rc, 1)
                self.assertIn(f'¿Querías decir "{buena}"?', out)

    def test_opcion_con_errata(self):
        rc, out = self.medios("on", "--forzr", config=CONFIG_BUENA)
        self.assertEqual(rc, 1)
        self.assertIn('No conozco la opción "--forzr". ¿Querías decir "--forzar"?', out)
        self.assertTrue(out.splitlines()[2].startswith("medios on"), out)

    def test_forzar_solo_en_on(self):
        rc, out = self.medios("estado", "--forzr", config=CONFIG_BUENA)
        self.assertEqual(rc, 1)
        self.assertNotIn("¿Querías decir", out)

    def test_parte_de_logs_con_errata(self):
        rc, out = self.medios("logs", "dlan", config=CONFIG_BUENA)
        self.assertEqual(rc, 1)
        self.assertIn('No conozco la parte "dlan". ¿Querías decir "dlna"?', out)


class Manual(Medios):
    def manual(self):
        (self.share / "VERSION").write_text("9.8.7\n")
        rc, out = self.medios("_manual")
        self.assertEqual(rc, 0)
        return out

    def test_cabecera_y_secciones(self):
        out = self.manual()
        self.assertTrue(out.startswith('.TH MEDIOS 1 "" "media-bridge 9.8.7"'), out[:80])
        for seccion in ("NOMBRE", "SINOPSIS", "DESCRIPCIÓN", "COMANDOS", "CONFIGURACIÓN", "PROBLEMAS", "ARCHIVOS"):
            self.assertIn(f"\n.SH {seccion}\n", out)

    def test_incluye_cada_comando_y_variable(self):
        out = self.manual()
        for c in COMANDOS:
            self.assertRegex(out, rf"(?m)^\.SS medios {c}\b")
        for v in ("SERVIDOR", "RECIENTES_CARPETAS"):
            self.assertIn(f"\n.SS {v}\n", out)
        self.assertIn("Por defecto: 8200.", out)

    def test_no_depende_de_la_configuracion(self):
        sin = self.manual()
        self.conf.write_text(CONFIG_BUENA + "NOMBRE_DLNA=GMK\n")
        self.assertEqual(self.manual(), sin)

    def test_solo_usa_macros_conocidas(self):
        for linea in self.manual().splitlines():
            if linea.startswith((".", "'")):
                self.assertRegex(linea, r"^\.(TH|SH|SS|B|BR|RI|IP|PP|TP)( |$)")

    @unittest.skipUnless(shutil.which("groff"), "sin groff")
    def test_groff_sin_avisos(self):
        fichero = self.dir / "medios.1"
        fichero.write_text(self.manual())
        r = subprocess.run(["groff", "-k", "-man", "-Tutf8", "-ww", "-z", str(fichero)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stderr, "")


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
        sin_carpetas = "\n".join(l for l in CONFIG_BUENA.splitlines() if not l.startswith("CARPETAS="))
        for extra in ("", "CARPETAS=()\n", 'CARPETAS=("")\n'):
            with self.subTest(extra=extra):
                rc, out = self.medios("estado", config=sin_carpetas + "\n" + extra)
                self.assertEqual(rc, 1)
                self.assertIn(f"Falta CARPETAS en {self.conf}", out)

    def test_reescaneo_no_numerico(self):
        for valor in ("una-hora", "-5", "1.5"):
            with self.subTest(valor=valor):
                rc, out = self.medios("estado", config=CONFIG_BUENA + f"REESCANEO_SEGUNDOS={valor}\n")
                self.assertEqual(rc, 1)
                self.assertIn("REESCANEO_SEGUNDOS tiene que ser un número de segundos", out)

    def test_si_o_no(self):
        for var in ("DLNA", "REENVIOS_SOLO_LAN", "DESCUBRIMIENTO_JELLYFIN", "RECIENTES"):
            with self.subTest(var=var):
                rc, out = self.medios("estado", config=CONFIG_BUENA + f"{var}=quizas\n")
                self.assertEqual(rc, 1)
                self.assertIn(f"{var} tiene que ser si o no", out)

    def test_recientes_cantidad_no_valida(self):
        for valor in ("0", "diez", "-3", "1.5"):
            with self.subTest(valor=valor):
                rc, out = self.medios("estado", config=CONFIG_BUENA + f"RECIENTES_CANTIDAD={valor}\n")
                self.assertEqual(rc, 1)
                self.assertIn("RECIENTES_CANTIDAD tiene que ser un número mayor que 0", out)

    def test_recientes_carpeta_que_no_esta_en_carpetas(self):
        rc, out = self.medios("estado", config=CONFIG_BUENA + 'RECIENTES_CARPETAS=("Movies" "Documentales")\n')
        self.assertEqual(rc, 1)
        self.assertIn('RECIENTES_CARPETAS incluye "Documentales", que no está en CARPETAS', out)

    def test_puerto_no_valido(self):
        for linea in ("PUERTO_DLNA=abc", "PUERTO_DLNA=0", "PUERTO_JELLYFIN=70000", "PUERTO_WEB=puerto", 'REENVIOS="8096,8920"'):
            with self.subTest(linea=linea):
                rc, out = self.medios("estado", config=CONFIG_BUENA + linea + "\n")
                self.assertEqual(rc, 1)
                self.assertIn(f"Puerto no válido en {self.conf}:", out)

    def test_opcion_desconocida(self):
        for args in (("volar",), ("-x",), ("--lo-que-sea",)):
            with self.subTest(args=args):
                rc, out = self.medios(*args, config=CONFIG_BUENA)
                self.assertEqual(rc, 1)
                self.assertTrue(out.startswith(f'No conozco el comando "{args[0]}".'), out)
                self.assertIn("Uso: medios on | off", out)
                self.assertIn("medios -h", out)
                self.assertNotIn("¿Querías decir", out)

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
        self.assertIn('No conozco la parte "tostadora".', out)
        self.assertIn("medios logs [montaje|dlna|reenvios|reescaneo|descubrimiento|web] [-f]", out)

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

    def test_estado_sin_j_devuelve_cero(self):
        self.conf.write_text(CONFIG_BUENA + "DLNA=no\n")
        env = {
            "PATH": os.environ["PATH"],
            "HOME": str(self.dir),
            "LANG": "C.UTF-8",
            "MEDIA_BRIDGE_CONFIG": str(self.conf),
            "MEDIA_BRIDGE_SHARE": str(self.share),
            "MEDIA_BRIDGE_DOCKER": "1",
        }
        r = subprocess.run(["bash", str(MEDIOS), "estado"], capture_output=True, text=True, env=env, timeout=20)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class Web(Medios):
    def test_web_en_docker(self):
        self.conf.write_text(CONFIG_BUENA)
        env = {
            "PATH": os.environ["PATH"],
            "HOME": str(self.dir),
            "LANG": "C.UTF-8",
            "MEDIA_BRIDGE_CONFIG": str(self.conf),
            "MEDIA_BRIDGE_SHARE": str(self.share),
            "MEDIA_BRIDGE_DOCKER": "1",
        }
        r = subprocess.run(["bash", str(MEDIOS), "web"], capture_output=True, text=True, env=env, timeout=20)
        self.assertEqual(r.returncode, 1)
        self.assertIn("no está disponible en Docker", r.stdout)

    def test_web_con_opcion_desconocida(self):
        rc, out = self.medios("web", "volar", config=CONFIG_BUENA)
        self.assertEqual(rc, 1)
        self.assertIn('No conozco la opción "volar"', out)
        self.assertIn("medios web [off]", out)

    def test_ayuda_de_web(self):
        rc, out = self.medios("web", "-h")
        self.assertEqual(rc, 0)
        self.assertIn("127.0.0.1", out)
        self.assertIn("medios web off", out)


ESTADO_FALSO = {
    "ip": """#!/bin/sh
case "$*" in
  "route show default") echo "default via 192.168.1.1 dev wlan0 proto dhcp" ;;
  *"addr show wlan0"*) echo "wlan0            UP             192.168.1.12/24" ;;
esac
""",
    "ss": """#!/bin/sh
case "$*" in
  *":8096 )"*)
    echo "0      0      192.168.1.12:8096      192.168.1.50:51000"
    echo "0      0      192.168.1.12:8096      192.168.1.50:51001"
    echo "0      0      [::ffff:192.168.1.12]:8096 [::ffff:192.168.1.7]:40000"
    echo "0      0      192.168.1.12:8096      192.168.1.12:40100"
    echo "0      0      127.0.0.1:8096         127.0.0.1:40200"
    ;;
esac
""",
    "pgrep": """#!/bin/sh
case "$*" in
  *"socat TCP-LISTEN:8096,"*) exit 0 ;;
esac
exit 1
""",
}


class EstadoJson(Medios):
    def setUp(self):
        super().setUp()
        self.bin = self.dir / "bin"
        self.bin.mkdir()
        for nombre, contenido in ESTADO_FALSO.items():
            f = self.bin / nombre
            f.write_text(contenido)
            f.chmod(0o755)
        self.db = self.dir / "db"
        recientes = self.db / "Añadidos recientemente"
        recientes.mkdir(parents=True)
        for nombre in ('02 · Otra\\cosa.mp4', '01 · Película "rara" (2024).mkv'):
            (recientes / nombre).symlink_to("/no/existe")
        (self.share / "VERSION").write_text("9.8.7\n")
        self.conf.write_text(
            CONFIG_BUENA
            + 'REENVIOS="8096 8920"\nNOMBRE_DLNA="Casa \\"de\\" todos\\\\"\n'
            + f'DB_DLNA="{self.db}"\nRECIENTES=si\nRECIENTES_CARPETAS=("Movies")\n'
        )

    def ejecutar(self, *args):
        env = {
            "PATH": f"{self.bin}:{os.environ['PATH']}",
            "HOME": str(self.dir),
            "LANG": "C.UTF-8",
            "MEDIA_BRIDGE_CONFIG": str(self.conf),
            "MEDIA_BRIDGE_SHARE": str(self.share),
            "MEDIA_BRIDGE_DOCKER": "1",
        }
        r = subprocess.run(["bash", str(MEDIOS), *args], capture_output=True, text=True, env=env, timeout=20)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout

    def test_json_valido_y_escapado(self):
        datos = json.loads(self.ejecutar("_estado-json"))
        self.assertEqual(datos["version"], "9.8.7")
        self.assertEqual(datos["ip"], "192.168.1.12")
        self.assertEqual(datos["dlna"]["nombre"], 'Casa "de" todos\\')
        self.assertFalse(datos["dlna"]["activo"])
        self.assertEqual(datos["recientes"]["lista"], ['01 · Película "rara" (2024)', "02 · Otra\\cosa"])
        self.assertEqual(datos["recientes"]["carpetas"], ["Movies"])
        self.assertEqual(
            [(r["puerto"], r["activo"]) for r in datos["reenvios"]],
            [(8096, True), (8920, False)],
        )
        self.assertEqual(datos["reenvios"][0]["url"], "http://192.168.1.12:8096")

    def test_conexiones_a_jellyfin(self):
        datos = json.loads(self.ejecutar("_estado-json"))
        self.assertTrue(datos["jellyfin"]["activo"])
        self.assertEqual(datos["jellyfin"]["conexiones"], ["192.168.1.7", "192.168.1.50"])

    def test_estado_dice_lo_mismo(self):
        out = self.ejecutar("estado")
        self.assertIn("Conectados a Jellyfin: 192.168.1.7, 192.168.1.50\n", out)
