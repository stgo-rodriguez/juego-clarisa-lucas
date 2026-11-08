"""Pruebas del visualizador SIMLOG v2.1, sin alterar el simulador."""
from __future__ import annotations

import csv
import hashlib
from io import BytesIO, StringIO
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from laboratorio.simlog_viewer_v21 import (
    SCHEMA, audit, build_events, discover_games, load_game,
    pair_from_manifest, stage_intervals, visible_events,
)


def to_csv(rows):
    text = StringIO()
    writer = csv.DictWriter(text, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return text.getvalue().encode("utf-8-sig")


def fixture(status="marriage", pair=(1,4), schema=SCHEMA):
    manifest = {
        "schema": schema, "run_id": "test_v21_6p", "seed": 17,
        "player_count": 6, "roles": {"1": "Clarisa", "4": "Lucas"},
        "status": status,
        "summary": {"winning_pair": json.dumps(pair) if pair else "null",
                    "won": bool(pair), "rounds": 3, "size": 6},
        "file_sha256": {},
    }
    turns = [
        dict(Partida="test_v21_6p", Ronda=1, Turno_global=1, Jugador=1,
             Etapa_antes="Infancia", Etapa_despues="Infancia",
             Etapa_situacion="Infancia", Carta_ID="I-C-1",
             Desenlace_elegido="A", Situacion="Caso A",
             Carta_Movimiento="", Dado=4, Distancia_movimiento=4,
             Pos_antes=1, Pos_despues=5, Canje="", Ruta_JSON="[]"),
        dict(Partida="test_v21_6p", Ronda=1, Turno_global=4, Jugador=4,
             Etapa_antes="Infancia", Etapa_despues="Infancia",
             Etapa_situacion="Infancia", Carta_ID="I-L-1",
             Desenlace_elegido="B", Situacion="Caso B",
             Carta_Movimiento="", Dado=3, Distancia_movimiento=3,
             Pos_antes=1, Pos_despues=4, Canje="",
             Ruta_JSON="[]"),
        dict(Partida="test_v21_6p", Ronda=2, Turno_global=7, Jugador=1,
             Etapa_antes="Juventud", Etapa_despues="Juventud",
             Etapa_situacion="Juventud", Carta_ID="J-C-2",
             Desenlace_elegido="B", Situacion="Caso C",
             Carta_Movimiento="M-12", Desenlace_movimiento="B",
             Dado="", Distancia_movimiento=5,
             Pos_antes=2, Pos_despues=6, Canje="A 2; P 1", Ruta_JSON="[]"),
    ]
    event_rows = []
    events = [
        (1, 1, 1, "duelo", "duel", {"challenger": 1, "defender": 4, "result": "win"}),
        (2, 1, 1, "competencia", "duelo", {"challenger": 1, "defender": 4}),
        (3, 1, 1, "economia", "issue", {"player": 1, "resource": "A", "amount": 3, "source": "infancia_destino_1"}),
        (4, 2, 7, "economia", "invest", {"player": 1, "project": "Titulo-1", "receipt": "R1"}),
        (5, 2, 7, "economia", "issue", {"player": 1, "resource": "P", "amount": 1, "source": "conversion_bancaria"}),
        (6, 2, 7, "economia", "pair", {"players": [1, 4]}),
        (7, 2, 7, "competencia", "evento_irrelevante", {"player": 2}),
        (8, 3, 14, "economia", "married", {"players": [1, 4]}),
    ]
    for seq, rnd, turn, source, action, data in events:
        event_rows.append({
            "Partida": "test_v21_6p",
            "Secuencia": seq, "Ronda": rnd, "Turno_global": turn,
            "Jugador_activo": 1 if turn != 4 else 4, "Jugador_afectado": "",
            "Fase": "turn", "Fuente": source, "Accion": action,
            "Detalle_JSON": json.dumps(data),
        })
    files = {"turnos.csv": to_csv(turns),
             "eventos.csv": to_csv(event_rows),
             "hitos.csv": b"",
             "estados_jugadores.csv": b"",
             "recursos_por_ronda.csv": b""}
    manifest["file_sha256"] = {k: hashlib.sha256(v).hexdigest() for k, v in files.items()}
    files["manifest.json"] = json.dumps(manifest).encode()
    return files


def zipped(files, prefix="trazas/n6_s17"):
    out = BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        for name, data in files.items():
            z.writestr(f"{prefix}/{name}", data)
    return out.getvalue()


class SIMLOGViewerTests(unittest.TestCase):
    def test_zip_discovery_and_load(self):
        blob = zipped(fixture())
        games = discover_games(".", blob)
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0]["pair"], (1,4))
        self.assertTrue(games[0]["won"])
        game = load_game(".", games[0]["directory"], blob)
        self.assertEqual(len(game["turnos.csv"]), 3)
        self.assertEqual(audit(game, ".", blob), [])

    def test_only_winners_and_no_double_duel(self):
        blob = zipped(fixture())
        game = load_game(".", "trazas/n6_s17", blob)
        items = build_events(game)
        duels = [x for x in items if x["categoria"] == "Duelos"]
        self.assertEqual(len(duels), 2)  # Un duelo en dos carriles, no dos duelos.
        self.assertEqual({x["jugador"] for x in duels}, {1,4})
        self.assertFalse(any(x["evento"] == "evento_irrelevante" for x in items))
        self.assertEqual(sum(x["categoria"] == "Canjes" for x in items), 1)
        self.assertEqual(sum(x["categoria"] == "Noviazgo" for x in items), 2)
        self.assertFalse(any("propuesta" in x["evento"].lower() for x in items))
        self.assertEqual(sum(x["categoria"] == "Subhitos" for x in items), 1)
        self.assertEqual(sum(x["categoria"] == "Situación A/B" for x in items), 3)

    def test_filter_and_stages(self):
        blob = zipped(fixture())
        game = load_game(".", "trazas/n6_s17", blob)
        stages = stage_intervals(game, (1,4))
        self.assertIn((1, "Infancia", 1, 1), stages)
        self.assertIn((1, "Juventud", 2, 2), stages)
        filtered = visible_events(build_events(game), ["Duelos"], 1, 1)
        self.assertEqual(len(filtered), 2)
        self.assertEqual(visible_events(build_events(game), ["Duelos"], 2, 3), [])

    def test_censored_or_old_version_not_forged(self):
        censored = zipped(fixture(status="round_limit", pair=None))
        games = discover_games(".", censored)
        self.assertEqual(len(games), 1)
        self.assertFalse(games[0]["won"])
        game = load_game(".", games[0]["directory"], censored)
        self.assertEqual(pair_from_manifest(game["manifest"]), ())
        self.assertEqual(build_events(game), [])
        old = zipped(fixture(schema="SIMLOG-2.0"))
        self.assertEqual(discover_games(".", old), [])

    def test_folder_access_and_hash_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / "trazas" / "n6_s17"
            run.mkdir(parents=True)
            for name, content in fixture().items():
                (run / name).write_bytes(content)
            games = discover_games(tmp)
            self.assertEqual(len(games), 1)
            game = load_game(tmp, games[0]["directory"])
            self.assertEqual(audit(game, tmp), [])
            (run / "turnos.csv").write_bytes((run / "turnos.csv").read_bytes() + b"\n")
            self.assertIn("SHA-256 diferente: turnos.csv", audit(game, tmp))

    def test_no_untrusted_directory(self):
        with self.assertRaises(ValueError):
            load_game(".", "otro/directorio", zipped(fixture()))


if __name__ == "__main__":
    unittest.main()
