"""Pruebas de la regla Casa v2.3 (10-11-2026), sin modificar v2.2."""
from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from simulador.agentes_v2 import AgentConfig
from simulador.agentes_v23 import GameAgentV23
from simulador.economia_v2 import EconomyV2
from simulador.experimento_politicas_v22 import EconomyBankV22
from simulador.movimiento_v2 import Coord
from simulador.movimiento_v22 import walk_adult_v22
from simulador.reglas_v23 import EconomyV23
from simulador.turnos_v2 import PlayerState, Stage


def setup_four():
    players = [
        PlayerState(1, "Clarisa", Stage.ADULTEZ, Coord(3, 3)),
        PlayerState(2, "Lucas", Stage.ADULTEZ, Coord(3, 3)),
        PlayerState(3, "Clarisa", Stage.ADULTEZ, Coord(3, 3)),
        PlayerState(4, "Lucas", Stage.ADULTEZ, Coord(3, 3)),
    ]
    eco = EconomyV23(players)
    for p in players:
        for r, amount in {"A": 35, "P": 25, "K": 10, "M": 70}.items():
            eco.issue(p.id, r, amount, "fixture")
    eco.form_pair(players[0], players[1])
    eco.form_pair(players[2], players[3])
    return players, eco


def owner_at(players, pos):
    for p in players[:2]:
        p.position = pos


def contenders_at(players, pos):
    for p in players[2:]:
        p.position = pos


class HouseV23Tests(unittest.TestCase):
    def test_bank_only_at_center(self):
        players, eco = setup_four()
        contenders_at(players, Coord(4, 4))
        self.assertFalse(eco.house_encounter(players[2]))
        with self.assertRaisesRegex(ValueError, "CASA"):
            eco.buy_house(players[2], dice=[(12, 2)])
        self.assertIsNone(eco.house_owner)
        contenders_at(players, Coord(3, 3))
        self.assertTrue(eco.buy_house(players[2], dice=[(12, 2)]))
        self.assertEqual(eco.house_owner, (3, 4))
        self.assertEqual(
            [e["location"] for e in eco.events if e["action"] == "house_attempt"],
            [(3, 3)],
        )
        eco.audit()

    def test_house_dispute_at_owner_position_outside_center(self):
        players, eco = setup_four()
        self.assertTrue(eco.buy_house(players[0], dice=[(12, 2)]))
        owner_at(players, Coord(4, 4))
        contenders_at(players, Coord(4, 4))
        self.assertTrue(eco.house_encounter(players[2]))
        old_money = [eco.accounts[pid].free["M"] for pid in (1, 2, 3, 4)]
        self.assertTrue(eco.buy_house(players[2], dice=[(12, 2)]))
        self.assertEqual(eco.house_owner, (3, 4))
        self.assertEqual([eco.accounts[x].house_a for x in (1, 2, 3, 4)],
                         [0, 0, 8, 8])
        self.assertEqual([eco.accounts[x].house_p for x in (1, 2, 3, 4)],
                         [0, 0, 5, 5])
        self.assertEqual(eco.accounts[1].free["M"], old_money[0] + 15)
        self.assertEqual(eco.accounts[2].free["M"], old_money[1] + 15)
        self.assertEqual(eco.accounts[3].free["M"], old_money[2] - 15)
        self.assertEqual(eco.accounts[4].free["M"], old_money[3] - 15)
        events = [e for e in eco.events if e["action"] == "house_attempt"]
        self.assertEqual(events[-1]["location"], (4, 4))
        self.assertEqual(events[-1]["mode"], "propietarios")
        self.assertEqual(events[-1]["owners"], (1, 2))
        self.assertEqual(events[-1]["buyers"], (3, 4))
        self.assertTrue(any(e["action"] == "house_encounter" for e in eco.events))
        eco.audit()

    def test_central_cell_does_not_challenge_owners_elsewhere(self):
        players, eco = setup_four()
        eco.buy_house(players[0], dice=[(12, 2)])
        owner_at(players, Coord(4, 4))
        contenders_at(players, Coord(3, 3))
        self.assertFalse(eco.house_encounter(players[2]))
        with self.assertRaisesRegex(ValueError, "propietarios"):
            eco.buy_house(players[2], dice=[(12, 2)])
        self.assertEqual(eco.house_owner, (1, 2))

    def test_not_enough_to_cross_owner_cell_must_finish_there(self):
        players, eco = setup_four()
        eco.buy_house(players[0], dice=[(12, 2)])
        owner_at(players, Coord(4, 4))
        route = walk_adult_v22(Coord(4, 3), 2, "E")
        self.assertIn(Coord(4, 4), route.visited)
        self.assertEqual(route.destination, Coord(4, 5))
        contenders_at(players, route.destination)
        self.assertFalse(eco.house_encounter(players[2]))

    def test_failed_attempt_then_escalated_second_win(self):
        players, eco = setup_four()
        eco.buy_house(players[0], dice=[(12, 2)])
        owner_at(players, Coord(2, 5))
        contenders_at(players, Coord(2, 5))
        cash = [eco.accounts[x].free["M"] for x in (1, 2, 3, 4)]
        self.assertTrue(eco.buy_house(
            players[2], dice=[(2, 12), (12, 2)], max_attempts=2,
        ))
        attempts = [e for e in eco.events if e["action"] == "house_attempt"][-2:]
        self.assertEqual([a["price_per_player"] for a in attempts], [15, 20])
        self.assertEqual([a["location"] for a in attempts], [(2, 5), (2, 5)])
        self.assertEqual(eco.accounts[1].free["M"], cash[0] + 20)
        self.assertEqual(eco.accounts[3].free["M"], cash[2] - 20)
        eco.audit()

    def test_tie_does_not_transfer_house(self):
        players, eco = setup_four()
        eco.buy_house(players[0], dice=[(12, 2)])
        owner_at(players, Coord(5, 2))
        contenders_at(players, Coord(5, 2))
        self.assertFalse(eco.buy_house(players[2], dice=[(7, 7)]))
        self.assertEqual(eco.house_owner, (1, 2))
        last = [e for e in eco.events if e["action"] == "house_attempt"][-1]
        self.assertFalse(last["won"])
        eco.audit()

    def test_owners_cannot_challenge_themselves(self):
        players, eco = setup_four()
        eco.buy_house(players[0], dice=[(12, 2)])
        owner_at(players, Coord(4, 4))
        self.assertFalse(eco.house_encounter(players[0]))
        with self.assertRaisesRegex(ValueError, "propietarios"):
            eco.buy_house(players[0], dice=[(12, 2)])

    def test_planner_targets_owner_instead_of_center(self):
        players, eco = setup_four()
        eco.buy_house(players[0], dice=[(12, 2)])
        owner_at(players, Coord(4, 4))
        contenders_at(players, Coord(4, 3))
        agent = GameAgentV23(None, eco, AgentConfig("planificador"), seed=13, profiles=None)
        owner_route = walk_adult_v22(Coord(4, 3), 1, "E")
        center_route = walk_adult_v22(Coord(4, 3), 1, "N")
        self.assertEqual(owner_route.destination, Coord(4, 4))
        self.assertEqual(center_route.destination, Coord(3, 3))
        self.assertGreater(agent._adult_score(players[2], owner_route),
                           agent._adult_score(players[2], center_route))

    def test_v22_bank_rule_unchanged(self):
        players = [
            PlayerState(1, "Clarisa", Stage.ADULTEZ, Coord(4, 4)),
            PlayerState(2, "Lucas", Stage.ADULTEZ, Coord(4, 4)),
        ]
        old = EconomyBankV22(players)
        for p in players:
            for r, n in {"A": 30, "P": 15, "M": 40}.items():
                old.issue(p.id, r, n, "fixture")
        old.form_pair(players[0], players[1])
        with self.assertRaisesRegex(ValueError, "Casa solo"):
            old.buy_house(players[0], dice=[(12, 2)])


class EndToEndV23Tests(unittest.TestCase):
    def test_simulation_produces_distinct_simlog_v23(self):
        from laboratorio.simular_v23 import run_game
        with tempfile.TemporaryDirectory() as folder:
            result = run_game(6, 3201, round_limit=100, trace_dir=Path(folder))
            self.assertEqual(result["size"], 6)
            self.assertIn(result["stop"], ("marriage", "rule_pending", "round_limit"))
            manifest_path = Path(folder) / "manifest.json"
            if result["stop"] == "rule_pending":
                self.assertTrue((Path(folder) / "bloqueo_reglamentario.json").exists())
                return
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["schema"], "SIMLOG-2.3")
            self.assertEqual(manifest["ruleset"], "especificacion-integral-2026-11-10")
            self.assertEqual(manifest["source_document_id"], "16IOCwC72fT__n5b19PQm-LRa7CenB5S_")
            with (Path(folder) / "eventos.csv").open(encoding="utf-8-sig") as stream:
                events = list(csv.DictReader(stream))
            for e in events:
                if e["Accion"] != "house_attempt":
                    continue
                detail = json.loads(e["Detalle_JSON"])
                self.assertEqual(len(detail["location"]), 2)
                self.assertIn(detail["mode"], ("banca", "propietarios"))
            self.assertTrue((Path(folder) / "turnos.csv").exists())


if __name__ == "__main__":
    unittest.main()
