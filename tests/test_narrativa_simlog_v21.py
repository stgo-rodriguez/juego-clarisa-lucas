"""Regresión del relato coloquial contra eventos y comprobantes reales de SIMLOG."""
from __future__ import annotations

import json
import unittest

from laboratorio.narrativa_simlog_v21 import summarize_player_round


def event(seq, rnd, turn, active, source, action, detail):
    return {
        "Secuencia": str(seq), "Ronda": str(rnd),
        "Turno_global": str(turn), "Jugador_activo": str(active),
        "Fuente": source, "Accion": action,
        "Detalle_JSON": json.dumps(detail, ensure_ascii=False),
    }


CATALOG = {"cards": [{
    "id": "INF-C-01", "title": "La tortuga necesita un hogar",
    "context": "La tortuga del aula necesita un terrario nuevo.",
    "text_a": "Construís el terrario con la escuela.",
    "text_b": "Organizás una rifa para conseguir dinero.",
    "effects": {"A": {"P": 1, "K": 1, "M": -2}, "B": {"M": 3}},
}]}


def fake_game():
    turns = [
        {
            "Ronda": "1", "Turno_global": "1", "Jugador": "1",
            "Etapa_antes": "Infancia", "Etapa_despues": "Infancia",
            "Pos_antes": "3", "Pos_despues": "6",
            "Dado": "3", "Pasos_consumidos": "3", "Pasos_descartados": "0",
            "Carta_ID": "INF-C-01", "Situacion": "La tortuga necesita un hogar",
            "Desenlace_elegido": "A", "Afinidad_posicion_antes": "0",
            "Afinidad_posicion_despues": "-1",
            "Afinidad_zona_antes": "Neutro", "Afinidad_zona_despues": "Neutro",
        },
        {
            "Ronda": "1", "Turno_global": "4", "Jugador": "4",
            "Etapa_antes": "Infancia", "Etapa_despues": "Infancia",
            "Pos_antes": "1", "Pos_despues": "2",
            "Dado": "1", "Carta_ID": "", "Desenlace_elegido": "",
        }
    ]
    events = [
        event(1, 1, 1, 1, "observador", "paso_por_casillero", {"player": 1, "position": 4}),
        event(2, 1, 1, 1, "economia", "issue", {"player": 1, "resource": "A",
                                                "amount": 3, "source": "infancia_destino_6"}),
        event(3, 1, 1, 1, "motor", "situation_context", {"player": 1, "card": "INF-C-01"}),
        event(4, 1, 1, 1, "economia", "spend", {"player": 1, "resource": "M",
                                                "amount": 1, "source": "situacion_vigente_perdida"}),
        event(5, 1, 1, 1, "economia", "issue", {"player": 1, "resource": "P",
                                                "amount": 1, "source": "situacion_vigente_premio"}),
        event(6, 1, 1, 1, "economia", "issue", {"player": 1, "resource": "K",
                                                "amount": 1, "source": "situacion_vigente_premio"}),
        event(7, 1, 1, 1, "economia", "spend", {"player": 1, "resource": "A",
                                                "amount": 4, "source": "conversion_bancaria"}),
        event(8, 1, 1, 1, "economia", "issue", {"player": 1, "resource": "P",
                                                "amount": 2, "source": "conversion_bancaria"}),
        event(9, 1, 1, 1, "observador", "noviazgo_propuesta", {"player": 1, "target": 4}),
        event(10, 1, 1, 1, "observador", "noviazgo_resultado", {"player": 1, "target": 4,
                                                               "accepted": True}),
        event(11, 1, 1, 1, "economia", "pair", {"players": [1, 4]}),
        event(12, 1, 1, 1, "economia", "invest", {"player": 1, "project": "Titulo-1",
                                                "receipt": "Titulo-1-S2"}),
        event(13, 1, 2, 2, "economia", "transfer", {"source": 1, "dest": 2,
                                                   "resource": "M", "amount": 2}),
        event(14, 1, 2, 2, "duelo", "duel", {"challenger": 2, "defender": 1,
                                          "result": "victoria", "kind": "ordinario",
                                          "defender_die": 1, "challenger_die": 5,
                                          "paid_resource": "M", "paid": 2}),
        event(15, 1, 4, 4, "observador", "paso_por_casillero", {"player": 4, "position": 2}),
        event(16, 1, 4, 4, "economia", "issue", {"player": 4, "resource": "P",
                                                "amount": 2, "source": "infancia_destino_2"}),
        event(17, 2, 8, 2, "duelo", "duel", {"challenger": 2, "defender": 4,
                                          "result": "derrota", "kind": "ordinario",
                                          "defender_die": 6, "challenger_die": 3,
                                          "paid_resource": "M", "paid": 2}),
    ]
    states = [{
        "Ronda": "1", "Turno_global": "1", "Jugador": "1",
        "Momento": "despues",
        "Comprobantes_JSON": json.dumps([{
            "id": "Titulo-1-S2", "project": "Titulo-1",
            "resource": "K", "amount": 2, "subhito": 2,
        }]),
    }]
    return {
        "manifest": {"roles": {"1": "Clarisa", "2": "Lucas", "4": "Lucas"}},
        "turnos.csv": turns, "eventos.csv": events,
        "estados_jugadores.csv": states,
    }


class NarrativaTests(unittest.TestCase):
    def test_orden_movimiento_casillero_situacion(self):
        data = summarize_player_round(fake_game(), 1, 1, CATALOG)
        names = [e["titulo"] for e in data["eventos"]]
        self.assertEqual(names[:3], [
            "Movimiento", "Casillero 6",
            "Carta de Situación · La tortuga necesita un hogar (INF-C-01)",
        ])
        self.assertIn("Salió 3 en el dado", data["eventos"][0]["texto"])
        self.assertIn("casillero 3 al 6", data["eventos"][0]["texto"])
        self.assertIn("3 de Amor", data["eventos"][1]["texto"])

    def test_situacion_muestra_textos_y_efectos_reales(self):
        data = summarize_player_round(fake_game(), 1, 1, CATALOG)
        choice = next(e for e in data["eventos"] if e["tipo"] == "Situación")
        self.assertEqual(choice["elegida"], "A")
        self.assertEqual(len(choice["opciones"]), 2)
        self.assertIn("tortuga del aula", choice["texto"])
        self.assertIn("ganó 1 de Personalidad y 1 de Conocimiento", choice["texto"])
        self.assertIn("perdió 1 de Dinero", choice["texto"])
        self.assertNotIn("perdió 2 de Dinero", choice["texto"])
        self.assertIn("afinidad pasó de 0", choice["texto"])

    def test_canje_subhito_noviazgo_y_duelo_ajeno(self):
        data = summarize_player_round(fake_game(), 1, 1, CATALOG)
        events = data["eventos"]
        conversion = next(e for e in events if e["tipo"] == "Canje")
        self.assertIn("4 de Amor", conversion["texto"])
        self.assertIn("2 de Personalidad", conversion["texto"])
        invested = next(e for e in events if e["tipo"] == "Subhito")
        self.assertIn("subhito 2", invested["texto"])
        self.assertIn("2 de Conocimiento", invested["texto"])
        proposal = [e for e in events if e["titulo"] == "Propuesta de noviazgo"]
        self.assertEqual(len(proposal), 1)
        self.assertIn("Lucas #4", proposal[0]["texto"])
        self.assertEqual(sum(e["titulo"] == "Pareja formada" for e in events), 0)
        duels = [e for e in events if e["tipo"] == "Duelo"]
        self.assertEqual(len(duels), 1)
        self.assertIn("Recibió un desafío de Lucas #2", duels[0]["texto"])
        self.assertIn("perdió el duelo y entregó 2 de Dinero", duels[0]["texto"])
        self.assertFalse(any(e["titulo"] == "Transferencia de recursos" for e in events))

    def test_otro_integrante_no_inventa_acciones(self):
        data = summarize_player_round(fake_game(), 1, 4, CATALOG)
        self.assertTrue(any(e["titulo"] == "Propuesta de noviazgo" for e in data["eventos"]))
        self.assertFalse(any(e["tipo"] == "Duelo" for e in data["eventos"]))
        self.assertFalse(any(e["tipo"] == "Situación" for e in data["eventos"]))

    def test_sin_turno_propio_pero_con_duelo(self):
        data = summarize_player_round(fake_game(), 2, 4, CATALOG)
        self.assertFalse(data["turno_propio"])
        self.assertEqual(data["etapa"], "Infancia")
        self.assertEqual(len(data["eventos"]), 1)
        self.assertIn("Recibió un desafío", data["eventos"][0]["texto"])
        self.assertIn("ganó el duelo", data["eventos"][0]["texto"])

    def test_integracion_con_simlog_v21_real(self):
        """Recorre una traza escrita por el motor real, no una fila sintética."""
        import tempfile
        from pathlib import Path
        from laboratorio.simular_mazos_vigentes_v2 import run_game
        from laboratorio.simlog_viewer_v21 import load_game
        from simulador.mazos_vigentes_v2 import load_current

        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / "traza"
            run_game(6, 1, round_limit=4, trace_dir=folder)
            data = load_game(folder, str(folder.resolve()))
            catalog = load_current()
            for player in (1, 4):
                for rnd in range(1, 5):
                    with self.subTest(player=player, rnd=rnd):
                        story = summarize_player_round(data, rnd, player, catalog)
                        self.assertEqual(story["jugador"], player)
                        self.assertEqual(story["ronda"], rnd)
                        self.assertTrue(story["turno_propio"])
                        own = next(t for t in data["turnos.csv"]
                                   if int(t["Jugador"]) == player and int(t["Ronda"]) == rnd)
                        if own.get("Tipo_movimiento_infancia") != "utn_exam_or_wait":
                            self.assertTrue(any(e["tipo"] == "Movimiento"
                                                for e in story["eventos"]),
                                            "Se espera un movimiento salvo en un turno de examen UTN")
                        else:
                            self.assertFalse(any(e["tipo"] == "Movimiento"
                                                 for e in story["eventos"]))
                        situations = [e for e in story["eventos"] if e["tipo"] == "Situación"]
                        if situations:
                            self.assertEqual(len(situations[0]["opciones"]), 2)
                            self.assertIn(situations[0]["elegida"], ("A", "B"))

    def test_utn_examen_no_se_confunde_con_movimiento(self):
        game = fake_game()
        game["turnos.csv"] = [{
            "Ronda": "1", "Turno_global": "1", "Jugador": "1",
            "Etapa_antes": "UTN", "Etapa_despues": "UTN",
            "Pos_antes": "UTN", "Pos_despues": "UTN",
            "Dado": "5", "Tipo_movimiento_infancia": "utn_exam_or_wait",
        }]
        game["eventos.csv"] = [
            event(1, 1, 1, 1, "motor", "utn_exam",
                  {"player": 1, "die": 5, "passed": True})
        ]
        data = summarize_player_round(game, 1, 1, CATALOG)
        self.assertFalse(any(e["tipo"] == "Movimiento" for e in data["eventos"]))
        self.assertIn("aprobó", data["eventos"][0]["texto"])


if __name__ == "__main__":
    unittest.main()
