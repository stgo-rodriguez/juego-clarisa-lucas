"""Compatibilidad del visualizador e importador SIMLOG v2.1/v2.2."""
from __future__ import annotations

import csv
import hashlib
from io import BytesIO, StringIO
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from laboratorio.importar_simlog_v22 import import_archive, validate_simlog
from laboratorio.simlog_viewer_v21 import discover_games, load_game, audit


def _csv(rows):
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8-sig")


def sample(schema="SIMLOG-2.2", ruleset="especificacion-integral-2026-11-09",
           player_count=6):
    manifest = {
        "schema": schema, "ruleset": ruleset, "run_id": "simlog_v22_6p_seed701",
        "player_count": player_count, "seed": 701, "status": "marriage",
        "roles": {str(n): "Clarisa" if n <= 3 else "Lucas"
                  for n in range(1, player_count + 1)},
        "summary": {"winning_pair": [3, 4], "won": True, "rounds": 20, "size": player_count},
    }
    files = {
        "turnos.csv": _csv([
            {"Partida": "simlog_v22_6p_seed701", "Ronda": 1, "Turno_global": 1,
             "Jugador": 1, "Etapa_antes": "Infancia", "Etapa_despues": "Infancia",
             "Etapa_situacion": "Infancia", "Carta_ID": "INF-C-01",
             "Desenlace_elegido": "A"},
        ]),
        "eventos.csv": _csv([
            {"Partida": "simlog_v22_6p_seed701", "Secuencia": 1, "Ronda": 1,
             "Turno_global": 1, "Jugador_activo": 1, "Fuente": "motor",
             "Accion": "situation_resolved",
             "Detalle_JSON": '{"player":1,"choice":"A","card":"INF-C-01"}'},
        ]),
    }
    manifest["file_sha256"] = {
        name: hashlib.sha256(content).hexdigest()
        for name, content in files.items()
    }
    files["manifest.json"] = json.dumps(manifest).encode()
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        for name, content in files.items():
            z.writestr("trazas/n6_s701/" + name, content)
    return buffer.getvalue()


class VisualizadorV22Tests(unittest.TestCase):
    def test_detects_and_loads_v22_zip(self):
        blob = sample()
        games = discover_games(".", blob)
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0]["schema"], "SIMLOG-2.2")
        self.assertTrue(games[0]["won"])
        data = load_game(".", games[0]["directory"], blob)
        self.assertEqual(len(data["turnos.csv"]), 1)
        self.assertEqual(audit(data, ".", blob), [])
        count, digest = validate_simlog(blob)
        self.assertEqual(count, 1)
        self.assertEqual(digest, hashlib.sha256(blob).hexdigest())

    def test_accepts_historical_v21(self):
        old = sample("SIMLOG-2.1", "especificacion-integral-2026-11-08")
        self.assertEqual(len(discover_games(".", old)), 1)
        self.assertEqual(discover_games(".", old)[0]["schema"], "SIMLOG-2.1")

    def test_rejects_crossed_or_unknown_rulesets(self):
        invalid = sample("SIMLOG-2.2", "especificacion-integral-2026-11-08")
        self.assertEqual(discover_games(".", invalid), [])
        with self.assertRaisesRegex(ValueError, "incompatibles"):
            validate_simlog(invalid)
        invalid = sample("SIMLOG-2.0", "especificacion-integral-2026-11-09")
        self.assertEqual(discover_games(".", invalid), [])

    def test_imports_from_github_artifact_zip_with_nested_zip(self):
        inner = sample()
        outer = BytesIO()
        with zipfile.ZipFile(outer, "w") as z:
            z.writestr("SIMLOG_v22_6j_max700_s701.zip", inner)
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "artifact.zip"
            source.write_bytes(outer.getvalue())
            dest = Path(tmp) / "resultados"
            target = import_archive(source, dest)
            self.assertEqual(target.read_bytes(), inner)
            self.assertEqual(len(discover_games(target)), 1)  # La UI indexa ZIP locales por separado.
            self.assertEqual(import_archive(source, dest), target)
            self.assertEqual(len(list(dest.glob("SIMLOG*.zip"))), 1)

    def test_import_refuses_invalid_sha_or_wrong_party_size(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "wrong.zip"
            archive.write_bytes(sample(player_count=10))
            with self.assertRaisesRegex(ValueError, "seis"):
                import_archive(archive, Path(tmp) / "resultados")
            self.assertFalse((Path(tmp) / "resultados").exists())


if __name__ == "__main__":
    unittest.main()
