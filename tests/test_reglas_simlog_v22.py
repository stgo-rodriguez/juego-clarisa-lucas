"""Regresiones independientes para las reglas nuevas de la v2.2 (09-11-2026)."""
from __future__ import annotations

import csv
import json
import random
import tempfile
import unittest
from pathlib import Path

from simulador.economia_v2 import EconomyScenario
from simulador.reglas_v21 import EconomyV21, transition_hooks_v21
from simulador.reglas_v22 import EconomyV22, RoundEngineV22
from simulador.movimiento_v2 import Coord, MovementCard, adult_options, cell_at, youth_cards
from simulador.movimiento_v22 import (
    BOARD_V22, adult_options_v22, cell_at_v22, walk_adult_v22,
)
from simulador.mazos_vigentes_v2 import load_current, new_decks
from simulador.transiciones_v2 import ProfileDecksV2
from simulador.turnos_v2 import CardPool, PlayerState, RuleHooks, Stage, AdultChoice
from laboratorio.experimento_agentes_v2 import adult_cards


def make_game(players):
    eco = EconomyV22(
        players,
        scenario=EconomyScenario(adult_square_amounts=None,
                                 neutral_situations=False),
    )
    eco.dynamic_affinity = {p.id: 0 for p in players}
    profiles = ProfileDecksV2(11)
    hooks = transition_hooks_v21(eco, profiles)
    hooks.apply_situation = lambda engine, player, card, choice: None
    engine = RoundEngineV22(
        players, new_decks(load_current(), 12),
        CardPool(youth_cards(), random.Random(13), recycle=True),
        CardPool(adult_cards(), random.Random(14), recycle=True),
        hooks=hooks, rng_dice=random.Random(15),
        dublin_policy='next_round',
    )
    return engine, eco, profiles


class BoardV22Tests(unittest.TestCase):
    def test_exact_board_and_gates(self):
        self.assertEqual(len(BOARD_V22), 5)
        self.assertEqual(sum(cell != '.' for row in BOARD_V22 for cell in row), 2)
        self.assertEqual(cell_at_v22(Coord(3, 3)), 'Casa')
        self.assertEqual(cell_at_v22(Coord(5, 3)), 'Perfil')
        for coord in [Coord(1, 1), Coord(1, 5), Coord(2, 1),
                      Coord(3, 5), Coord(4, 2), Coord(5, 2)]:
            self.assertEqual(cell_at_v22(coord), '.')
        self.assertEqual(cell_at(Coord(1, 1)), 'K')

    def test_route_geometry_unchanged_but_activation_changes(self):
        old = adult_options(Coord(2, 1), 1)
        new = adult_options_v22(Coord(2, 1), 1)
        self.assertEqual([q.destination for q in old], [q.destination for q in new])
        old_to_corner = next(x for x in old if x.destination == Coord(1, 1))
        new_to_corner = next(x for x in new if x.destination == Coord(1, 1))
        self.assertEqual(old_to_corner.activation, 'K')
        self.assertEqual(new_to_corner.activation, '.')
        self.assertEqual(walk_adult_v22(Coord(4, 3), 1, 'N').activation, 'Casa')
        self.assertEqual(walk_adult_v22(Coord(4, 3), 1, 'S').activation, 'Perfil')

    def test_youth_steps_never_grant_resource(self):
        p = PlayerState(1, 'Clarisa', Stage.JUVENTUD, 1)
        engine, eco, _ = make_game([p])
        for pos in range(1, 7):
            eco.on_step(engine, p, pos, pos in (2, 5))
        eco.on_destination(engine, p, 'Universidad')
        eco.on_destination(engine, p, 'Tramite')
        self.assertEqual(eco.issued, dict.fromkeys('APKM', 0))
        self.assertFalse(any(e['action'] == 'issue' for e in eco.events))

    def test_adult_plain_cells_do_not_issue_resource(self):
        p = PlayerState(1, 'Lucas', Stage.ADULTEZ, Coord(3, 3))
        engine, eco, profiles = make_game([p])
        profiles.award_utn(eco, p)
        existing = dict(eco.issued)
        for target in ('.', 'Casa'):
            eco.on_destination(engine, p, target)
        self.assertEqual(eco.issued, existing)
        with self.assertRaisesRegex(AssertionError, 'no tiene casilleros'):
            eco.on_destination(engine, p, 'K')

    def test_first_adult_turn_uses_v22_route_and_no_square_income(self):
        p = PlayerState(1, 'Lucas', Stage.ADULTEZ, Coord(2, 1))
        engine, eco, profiles = make_game([p])
        profiles.award_utn(eco, p)
        engine.start_round()
        result = engine.play_turn(
            1, adult_choice=lambda player, situation, hand:
            AdultChoice(hand.cards[0].id, 'A', 'N'),
        )
        self.assertIn(result.target, ('.', 'Casa', 'Perfil'))
        self.assertNotIn(
            'adultez_casillero',
            [ev.get('source') for ev in eco.events],
        )
        route_events = [e for e in engine.events
                        if e.get('action') == 'adult_route_v22']
        self.assertEqual(len(route_events), 1)
        self.assertEqual(route_events[0]['activation'], result.target)

    def test_previous_version_still_issues_youth_resources(self):
        p = PlayerState(1, 'Lucas', Stage.JUVENTUD, 1)
        old = EconomyV21([p])
        old.on_step(None, p, 1, True)
        self.assertEqual(old.accounts[1].free['K'], 2)


class SimulationV22Tests(unittest.TestCase):
    def test_simlog_v22_one_complete_game_without_removed_sources(self):
        from laboratorio.simular_v22 import run_game
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            result = run_game(6, 101, round_limit=55, trace_dir=out)
            self.assertEqual(result['size'], 6)
            manifest = json.loads((out / 'manifest.json').read_text())
            self.assertEqual(manifest['schema'], 'SIMLOG-2.2')
            self.assertEqual(manifest['ruleset'], 'especificacion-integral-2026-11-09')
            with (out / 'eventos.csv').open(encoding='utf-8-sig', newline='') as stream:
                events = list(csv.DictReader(stream))
            sources = {
                json.loads(e['Detalle_JSON']).get('source')
                for e in events if e['Accion'] == 'issue'
            }
            self.assertFalse(sources.intersection({
                'adultez_casillero', 'juventud_universidad',
                'juventud_tramite',
            }))
            self.assertTrue((out / 'situaciones_por_ronda.csv').exists())
            self.assertTrue((out / 'turnos.csv').exists())


if __name__ == '__main__':
    unittest.main()
