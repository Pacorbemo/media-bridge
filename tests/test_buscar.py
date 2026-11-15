import subprocess
import sys
import unittest
from pathlib import Path

BUSCAR = Path(__file__).resolve().parent.parent / "lib" / "buscar.py"


def buscar(rutas, *texto):
    r = subprocess.run(
        [sys.executable, str(BUSCAR), *texto],
        input="".join(f"{p}\n" for p in rutas),
        capture_output=True,
        text=True,
    )
    return r.returncode, r.stdout, r.stderr


def bloque(salida, titulo):
    lineas = []
    dentro = False
    for linea in salida.splitlines():
        if linea.startswith(titulo):
            dentro = True
            continue
        if dentro:
            if not linea.startswith("  "):
                break
            lineas.append(linea.strip())
    return lineas


class Normalizacion(unittest.TestCase):
    RUTAS = ["Movies/El.Hobbit_Un-viaje inesperado.mkv", "Movies/Camión de bomberos.mp4", "Movies/Speed.mkv"]

    def test_mayusculas(self):
        _, out, _ = buscar(self.RUTAS, "EL HOBBIT")
        self.assertEqual(bloque(out, "Coincidencias"), ["Movies/El.Hobbit_Un-viaje inesperado.mkv"])

    def test_tildes_en_el_fichero(self):
        _, out, _ = buscar(self.RUTAS, "camion")
        self.assertEqual(bloque(out, "Coincidencias"), ["Movies/Camión de bomberos.mp4"])

    def test_tildes_en_lo_buscado(self):
        _, out, _ = buscar(["Movies/Camion.mkv"], "camión")
        self.assertEqual(bloque(out, "Coincidencias"), ["Movies/Camion.mkv"])

    def test_separadores(self):
        _, out, _ = buscar(self.RUTAS, "hobbit-un_viaje")
        self.assertEqual(bloque(out, "Coincidencias"), ["Movies/El.Hobbit_Un-viaje inesperado.mkv"])

    def test_palabras_en_cualquier_orden(self):
        _, out, _ = buscar(self.RUTAS, "viaje", "hobbit")
        self.assertEqual(bloque(out, "Coincidencias"), ["Movies/El.Hobbit_Un-viaje inesperado.mkv"])


class Erratas(unittest.TestCase):
    RUTAS = ["Movies/El hobbit Un viaje inesperado.mkv", "Movies/Speed.mkv", "Movies/Mars.mkv"]

    def test_hobit(self):
        _, out, _ = buscar(self.RUTAS, "hobit")
        self.assertEqual(bloque(out, "Coincidencias"), [])
        self.assertEqual(bloque(out, "Parecidos"), ["Movies/El hobbit Un viaje inesperado.mkv"])

    def test_speeed(self):
        _, out, _ = buscar(self.RUTAS, "speeed")
        self.assertEqual(bloque(out, "Parecidos"), ["Movies/Speed.mkv"])

    def test_sin_falsos_parecidos(self):
        _, out, _ = buscar(self.RUTAS, "matrix")
        self.assertEqual(bloque(out, "Parecidos"), [])
        self.assertIn("No hay nada parecido", out)

    def test_todas_las_palabras_tienen_que_parecerse(self):
        _, out, _ = buscar(self.RUTAS, "hobit", "matrix")
        self.assertIn("No hay nada parecido", out)

    def test_diferencia_de_longitud_limitada(self):
        _, out, _ = buscar(["Movies/Pelicxulazz.mkv"], "pelicula")
        self.assertIn("No hay nada parecido", out)

    def test_misma_errata_dentro_del_margen(self):
        _, out, _ = buscar(["Movies/Pelicxula.mkv"], "pelicula")
        self.assertEqual(bloque(out, "Parecidos"), ["Movies/Pelicxula.mkv"])


class Salida(unittest.TestCase):
    def test_agrupa_por_carpeta(self):
        rutas = [
            "Tv Shows/Breaking Bad/S01/E01.mkv",
            "Tv Shows/Breaking Bad/S01/E02.mkv",
            "Tv Shows/Breaking Bad/S02/E01.mkv",
            "Movies/Breaking News.mkv",
        ]
        _, out, _ = buscar(rutas, "breaking")
        self.assertIn("Coincidencias (2):", out)
        self.assertEqual(
            bloque(out, "Coincidencias"),
            ["Movies/Breaking News.mkv", "Tv Shows/Breaking Bad/  (3 vídeos)"],
        )

    def test_cuenta_los_videos(self):
        _, out, _ = buscar(["Movies/A.mkv", "Movies/B.mkv", ""], "zzz")
        self.assertIn("Buscado en 2 vídeos del servidor", out)

    def test_nada_parecido(self):
        rc, out, _ = buscar(["Movies/Speed.mkv"], "zzzz")
        self.assertEqual(rc, 0)
        self.assertIn("No hay nada parecido", out)
        self.assertNotIn("Coincidencias", out)
        self.assertNotIn("Parecidos", out)

    def test_sin_texto(self):
        rc, _, err = buscar(["Movies/Speed.mkv"], " - ")
        self.assertEqual(rc, 1)
        self.assertIn('Uso: medios buscar "texto"', err)


if __name__ == "__main__":
    unittest.main()
