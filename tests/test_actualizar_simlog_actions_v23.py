"""Regresión del importador de GitHub Actions SIMLOG v2.3 (sin red)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from laboratorio.actualizar_simlog_actions_v23 import (
    ARTIFACTS, CARPETA_FUENTE, ErrorImportacion,
    RUN_ID, importar_run, validar_trazas,
)


def construir_trazas(folder: Path, jugadores: int) -> None:
    """Fixture de 350 partidas mínimas, una por semilla oficial."""
    for seed in range(2001, 2351):
        game = folder / f"n{jugadores}_s{seed}"
        game.mkdir(parents=True, exist_ok=True)
        checks = {}
        for filename in ("turnos.csv", "eventos.csv", "estados_jugadores.csv"):
            data = f"Ronda,Jugador\n1,{seed}\n".encode("utf-8")
            (game / filename).write_bytes(data)
            checks[filename] = hashlib.sha256(data).hexdigest()
        (game / "manifest.json").write_text(
            json.dumps({
                "schema": "SIMLOG-2.3",
                "ruleset": "especificacion-integral-2026-11-10",
                "seed": seed,
                "player_count": jugadores,
                "file_sha256": checks,
            }), encoding="utf-8"
        )


class ImportadorActionsV23Tests(unittest.TestCase):
    def test_valida_identidad_cobertura_e_integridad(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "trazas"
            construir_trazas(root, 6)
            result = validar_trazas(root, 6)
            self.assertEqual(result["partidas"], 350)
            self.assertEqual(result["archivos_auditados"], 1050)
            (root / "n6_s2001" / "turnos.csv").write_text("alterado")
            with self.assertRaisesRegex(ErrorImportacion, "SHA256"):
                validar_trazas(root, 6)

    def test_descarga_y_reutiliza_fuente_sin_tocar_anteriores(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            legacy = root / "otra_simulacion" / "partida.txt"
            legacy.parent.mkdir()
            legacy.write_text("histórico", encoding="utf-8")
            commands = []

            def faux_run(args, **kwargs):
                commands.append(args)
                if args[1:3] == ["auth", "status"]:
                    return subprocess.CompletedProcess(args, 0, "", "")
                if args[1:3] == ["run", "download"]:
                    self.assertEqual(args[3], str(RUN_ID))
                    self.assertEqual(args[args.index("-n") + 1], ARTIFACTS[6])
                    construir_trazas(Path(args[args.index("-D") + 1]), 6)
                    return subprocess.CompletedProcess(args, 0, "", "")
                self.fail(f"Comando inesperado: {args}")

            with patch("laboratorio.actualizar_simlog_actions_v23.shutil.which",
                       return_value="/usr/local/bin/gh"), patch(
                "laboratorio.actualizar_simlog_actions_v23.subprocess.run",
                side_effect=faux_run,
            ):
                result = importar_run(root, mesas=(6,))
            self.assertEqual(result[0]["estado"], "incorporada")
            self.assertEqual(result[0]["partidas"], 350)
            self.assertTrue(legacy.is_file())
            final = root / CARPETA_FUENTE / "6_jugadores"
            self.assertTrue((final / "n6_s2350" / "manifest.json").is_file())
            self.assertEqual(len(commands), 2)

            with patch("laboratorio.actualizar_simlog_actions_v23.verificar_github_cli",
                       side_effect=AssertionError("No debería necesitar gh")):
                again = importar_run(root, mesas=(6,))
            self.assertEqual(again[0]["estado"], "reutilizada")
            self.assertEqual(again[0]["partidas"], 350)

    def test_descarga_incompleta_no_se_publica(self):
        with tempfile.TemporaryDirectory() as temp:
            def faux_run(args, **kwargs):
                if args[1:3] == ["auth", "status"]:
                    return subprocess.CompletedProcess(args, 0, "", "")
                stage = Path(args[args.index("-D") + 1])
                (stage / "n6_s2001").mkdir()
                (stage / "n6_s2001" / "manifest.json").write_text("{}")
                return subprocess.CompletedProcess(args, 0, "", "")

            with patch("laboratorio.actualizar_simlog_actions_v23.shutil.which",
                       return_value="/usr/local/bin/gh"), patch(
                "laboratorio.actualizar_simlog_actions_v23.subprocess.run",
                side_effect=faux_run,
            ):
                with self.assertRaisesRegex(ErrorImportacion, "350 trazas"):
                    importar_run(Path(temp), mesas=(6,))
            self.assertFalse((Path(temp) / CARPETA_FUENTE /
                              "6_jugadores").exists())

    def test_sin_github_cli_muestra_una_instruccion_concreta(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch("laboratorio.actualizar_simlog_actions_v23.shutil.which",
                       return_value=None):
                with self.assertRaisesRegex(ErrorImportacion, "brew install gh"):
                    importar_run(Path(temp), mesas=(10,))


if __name__ == "__main__":
    unittest.main()
