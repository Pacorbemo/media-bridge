import subprocess
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
NOTAS = RAIZ / ".github" / "notas-version.sh"
CHANGELOG = """# Cambios

## Sin publicar

- Algo nuevo

## 0.2.0

Publicada el 2026-11-15.

### Añadido

- Ayuda

## 0.1.0

- Primera
"""


class NotasVersion(unittest.TestCase):
    def notas(self, version, texto=CHANGELOG):
        with tempfile.TemporaryDirectory() as d:
            cl = Path(d) / "CHANGELOG.md"
            if texto is not None:
                cl.write_text(texto)
            r = subprocess.run(["bash", str(NOTAS), version, str(cl)], capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def test_saca_solo_su_apartado(self):
        out = self.notas("0.2.0")
        self.assertTrue(out.startswith("Publicada el 2026-11-15."), out)
        self.assertIn("- Ayuda", out)
        self.assertNotIn("Algo nuevo", out)
        self.assertNotIn("Primera", out)

    def test_ultima_version_del_fichero(self):
        self.assertEqual(self.notas("0.1.0"), "- Primera\n")

    def test_version_que_no_esta(self):
        self.assertIn("No hay notas para 9.9.9", self.notas("9.9.9"))

    def test_sin_changelog(self):
        self.assertIn("No hay notas para 0.2.0", self.notas("0.2.0", texto=None))

    def test_changelog_del_repo_tiene_las_versiones(self):
        for v in ("0.1.0", "0.2.0"):
            with self.subTest(version=v):
                out = subprocess.run(["bash", str(NOTAS), v, str(RAIZ / "CHANGELOG.md")], capture_output=True, text=True).stdout
                self.assertNotIn("No hay notas", out)


if __name__ == "__main__":
    unittest.main()
