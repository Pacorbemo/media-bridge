import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "lib" / "recientes.py"


class Recientes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.llegadas = self.dir / "llegadas"
        self.destino = self.dir / "Añadidos recientemente"
        self.montaje = self.dir / "montaje"

    def tearDown(self):
        self.tmp.cleanup()

    def ejecutar(self, videos, cantidad=10, ahora=5000):
        entrada = "".join(f"{fecha}\t{ruta}\n" for ruta, fecha in videos.items())
        r = subprocess.run(
            [sys.executable, str(SCRIPT), "--llegadas", str(self.llegadas), "--destino", str(self.destino),
             "--montaje", str(self.montaje), "--cantidad", str(cantidad), "--ahora", str(ahora)],
            input=entrada, capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def enlaces(self):
        return {e.name: os.readlink(e) for e in sorted(self.destino.iterdir())}

    def test_primera_vez_ordena_por_fecha_del_fichero(self):
        self.ejecutar({
            "Movies/Vieja (1990)/vieja.mkv": 100,
            "Movies/Nueva (2026)/Nueva.2026.1080p.mkv": 300,
            "Movies/Media (2010)/media.mp4": 200,
        })
        self.assertEqual(self.enlaces(), {
            "01 · Nueva (2026).mkv": str(self.montaje / "Movies/Nueva (2026)/Nueva.2026.1080p.mkv"),
            "02 · Media (2010).mp4": str(self.montaje / "Movies/Media (2010)/media.mp4"),
            "03 · Vieja (1990).mkv": str(self.montaje / "Movies/Vieja (1990)/vieja.mkv"),
        })

    def test_fichero_suelto_usa_su_nombre(self):
        self.ejecutar({"Movies/Suelta (2001).mkv": 100})
        self.assertEqual(list(self.enlaces()), ["01 · Suelta (2001).mkv"])

    def test_cantidad(self):
        self.ejecutar({f"Movies/P{i}/p.mkv": i for i in range(15)}, cantidad=3)
        self.assertEqual(list(self.enlaces()), ["01 · P14.mkv", "02 · P13.mkv", "03 · P12.mkv"])

    def test_lo_nuevo_entra_primero_aunque_el_fichero_sea_antiguo(self):
        self.ejecutar({"Movies/A/a.mkv": 200, "Movies/B/b.mkv": 300}, ahora=1000)
        self.ejecutar({"Movies/A/a.mkv": 200, "Movies/B/b.mkv": 300, "Movies/C/c.mkv": 50}, ahora=2000)
        self.assertEqual(list(self.enlaces()), ["01 · C.mkv", "02 · B.mkv", "03 · A.mkv"])

    def test_lo_borrado_sale(self):
        self.ejecutar({"Movies/A/a.mkv": 200, "Movies/B/b.mkv": 300})
        self.ejecutar({"Movies/A/a.mkv": 200})
        self.assertEqual(list(self.enlaces()), ["01 · A.mkv"])
        self.assertNotIn("Movies/B/b.mkv", self.llegadas.read_text())

    def test_conserva_la_fecha_de_llegada(self):
        self.ejecutar({"Movies/A/a.mkv": 200}, ahora=1000)
        self.ejecutar({"Movies/A/a.mkv": 200, "Movies/B/b.mkv": 100}, ahora=2000)
        self.ejecutar({"Movies/A/a.mkv": 200, "Movies/B/b.mkv": 100}, ahora=3000)
        self.assertEqual(self.llegadas.read_text(), "200\tMovies/A/a.mkv\n2000\tMovies/B/b.mkv\n")

    def test_sin_videos_no_toca_nada(self):
        self.ejecutar({"Movies/A/a.mkv": 200})
        antes = self.llegadas.read_text()
        out = self.ejecutar({})
        self.assertIn("dejo Añadidos recientemente como estaba", out)
        self.assertEqual(self.llegadas.read_text(), antes)
        self.assertEqual(list(self.enlaces()), ["01 · A.mkv"])

    def test_no_borra_lo_que_no_es_un_enlace(self):
        self.destino.mkdir()
        (self.destino / "nota.txt").write_text("mía")
        self.ejecutar({"Movies/A/a.mkv": 200})
        self.assertTrue((self.destino / "nota.txt").exists())


if __name__ == "__main__":
    unittest.main()
