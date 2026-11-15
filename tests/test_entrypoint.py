import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ENTRYPOINT = RAIZ / "docker" / "entrypoint.sh"
VARIABLES = ["SERVIDOR", "USUARIO_SSH", "RUTA_MEDIOS", "REENVIOS", "DLNA", "NOMBRE_DLNA", "PUERTO_DLNA",
             "INTERFAZ", "PUNTO_MONTAJE", "DB_DLNA", "EXTENSIONES", "REESCANEO_SEGUNDOS", "DESCUBRIMIENTO_JELLYFIN"]


@unittest.skipUnless(os.access("/ssh/clave", os.R_OK), "el entrypoint exige /ssh/clave; el CI la crea")
class Entrypoint(unittest.TestCase):
    def generar(self, **entorno):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            falso = tmp / "bin" / "medios"
            falso.parent.mkdir()
            llamado = tmp / "llamado"
            falso.write_text(f"#!/bin/sh\necho \"$*\" > '{llamado}'\nexit 1\n")
            falso.chmod(falso.stat().st_mode | stat.S_IXUSR)
            conf = tmp / "media-bridge.conf"
            env = {"PATH": f"{falso.parent}:{os.environ['PATH']}", "MEDIA_BRIDGE_CONFIG": str(conf), **entorno}
            r = subprocess.run(["bash", str(ENTRYPOINT)], capture_output=True, text=True, env=env, timeout=20)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertEqual(r.stderr, "")
            self.assertEqual(llamado.read_text(), "_comprobar\n")
            vuelta = subprocess.run(
                ["bash", "-c", 'source "$1"; for v in "${@:2}"; do printf "%s=%s\\n" "$v" "${!v}"; done;'
                 ' printf "CARPETAS=%s\\n" "${#CARPETAS[@]}"; printf "%s\\n" "${CARPETAS[@]}"',
                 "_", str(conf), *VARIABLES],
                capture_output=True, text=True, check=True,
            ).stdout.splitlines()
            n = len(VARIABLES)
            valores = dict(l.split("=", 1) for l in vuelta[:n + 1])
            carpetas = vuelta[n + 1:]
            self.assertEqual(int(valores.pop("CARPETAS")), len(carpetas))
            return valores, carpetas

    def test_carpetas_con_comas_y_espacios(self):
        valores, carpetas = self.generar(
            SERVIDOR="100.64.0.10", USUARIO_SSH="usuario", RUTA_MEDIOS="/mnt/mis medios",
            CARPETAS=" Movies ,Tv Shows,, Películas de 'culto' ,",
        )
        self.assertEqual(carpetas, ["Movies", "Tv Shows", "Películas de 'culto'"])
        self.assertEqual(valores["RUTA_MEDIOS"], "/mnt/mis medios")

    def test_reenvios_con_comas(self):
        valores, _ = self.generar(SERVIDOR="s", USUARIO_SSH="u", RUTA_MEDIOS="/m", CARPETAS="A", REENVIOS="8096,8920")
        self.assertEqual(valores["REENVIOS"], "8096 8920")

    def test_valores_por_defecto(self):
        valores, _ = self.generar(SERVIDOR="s", USUARIO_SSH="u", RUTA_MEDIOS="/m", CARPETAS="A")
        self.assertEqual(valores["REENVIOS"], "")
        self.assertEqual(valores["DLNA"], "si")
        self.assertEqual(valores["NOMBRE_DLNA"], "media-bridge")
        self.assertEqual(valores["PUERTO_DLNA"], "8200")
        self.assertEqual(valores["PUNTO_MONTAJE"], "/media")
        self.assertEqual(valores["DB_DLNA"], "/data/dlna")
        self.assertEqual(valores["REESCANEO_SEGUNDOS"], "3600")
        self.assertEqual(valores["DESCUBRIMIENTO_JELLYFIN"], "si")



class Validacion(unittest.TestCase):
    def test_falta_una_variable(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {"PATH": os.environ["PATH"], "MEDIA_BRIDGE_CONFIG": f"{tmp}/conf",
                   "SERVIDOR": "s", "USUARIO_SSH": "u", "CARPETAS": "A"}
            r = subprocess.run(["bash", str(ENTRYPOINT)], capture_output=True, text=True, env=env, timeout=20)
            self.assertEqual(r.returncode, 1)
            self.assertIn("Falta la variable RUTA_MEDIOS en media-bridge.env", r.stdout)
            self.assertFalse(Path(f"{tmp}/conf").exists())



if __name__ == "__main__":
    unittest.main()
