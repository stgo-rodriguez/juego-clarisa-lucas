"""Regresión de las reglas v2.1 del 08-11-2026, sin cambiar el motor histórico."""
import csv
import json
import random
import tempfile
import unittest
from pathlib import Path

from simulador.economia_v2 import EconomyScenario
from simulador.movimiento_v2 import youth_cards, Coord
from simulador.mazos_vigentes_v2 import CurrentResolver, load_current, new_decks
from simulador.reglas_v21 import EconomyV21, RoundEngineV21, transition_hooks_v21
from simulador.transiciones_v2 import ProfileDecksV2
from simulador.turnos_v2 import AdultChoice, CardPool, PlayerState, RuleHooks, Stage


def game(players, *, hooks=None):
    eco = EconomyV21(players, scenario=EconomyScenario(
        adult_square_amounts=dict.fromkeys('APKM', 2),
        neutral_situations=False
    ))
    eco.dynamic_affinity = {p.id: 0 for p in players}
    profiles = ProfileDecksV2(43)
    if hooks is None:
        hooks = transition_hooks_v21(eco, profiles)
        hooks.apply_situation = CurrentResolver(eco, 'aleatorio', 59).resolve
    g = RoundEngineV21(
        players, new_decks(load_current(), 31),
        CardPool(youth_cards(), random.Random(13), recycle=True),
        CardPool(youth_cards(), random.Random(14), recycle=True),
        hooks=hooks, rng_dice=random.Random(19),
    )
    return g, eco, profiles


class MotorV21Tests(unittest.TestCase):
    def test_shared_infancy_per_role_and_individual_choices(self):
        players = [PlayerState(1, 'Clarisa'), PlayerState(2, 'Clarisa'),
                   PlayerState(3, 'Lucas')]
        resolved = []
        hooks = RuleHooks(apply_situation=lambda e, p, c, choice:
                          resolved.append((p.id, c.id)))
        g, _, _ = game(players, hooks=hooks)
        g.start_round()
        self.assertEqual(sum(ev['action'] == 'situation_revealed' for ev in g.events), 2)
        for i, die in [(1, 1), (2, 2), (3, 3)]:
            g.play_turn(i, childhood_die=die)
        self.assertEqual(resolved[0][1], resolved[1][1])
        self.assertNotEqual(resolved[1][1], resolved[2][1])
        g.start_round()
        self.assertEqual(sum(ev['action'] == 'situation_revealed' for ev in g.events), 4)

    def test_same_role_different_stages_distinct_shared_cards(self):
        players = [PlayerState(1, 'Clarisa', Stage.ADULTEZ, Coord(5, 3)),
                   PlayerState(2, 'Clarisa', Stage.ADULTEZ, Coord(5, 3)),
                   PlayerState(3, 'Clarisa', Stage.JUVENTUD, 1),
                   PlayerState(4, 'Lucas', Stage.INFANCIA, 1)]
        observed = []
        g, _, _ = game(players, hooks=RuleHooks(
            apply_situation=lambda e, p, c, choice:
            observed.append((p.id, c.stage.value, c.id))))
        g.start_round()
        revealed = [e for e in g.events if e['action'] == 'situation_revealed']
        self.assertEqual(len(revealed), 3)
        for i in (1, 2):
            g.play_turn(i, adult_choice=lambda p, s, h:
                        AdultChoice(h.cards[0].id, 'A', 'N'))
        g.play_turn(3, youth_choice=lambda p, c, m: 'B')
        g.play_turn(4, childhood_die=1)
        self.assertEqual(observed[0][2], observed[1][2])
        self.assertNotEqual(observed[1][2], observed[2][2])
        self.assertNotEqual(observed[2][2], observed[3][2])
        self.assertEqual(sum(e['action'] == 'situation_resolved'
                             for e in g.events), 4)
        self.assertEqual(len(g._revealed), 3)

    def test_destination_only_and_order_before_situation(self):
        p = PlayerState(1, 'Clarisa')
        observed = []
        g, eco, _ = game([p])
        resolver = g.hooks.apply_situation
        def capture(e, player, card, letter):
            observed.append(dict(eco.accounts[player.id].free))
            resolver(e, player, card, letter)
        g.hooks.apply_situation = capture
        g.start_round()
        g.play_turn(1, childhood_die=2)  # 1 -> 2 -> 3 = +3 Amor
        issues = [e for e in eco.events if e['action'] == 'issue'
                  and e.get('source', '').startswith('infancia_destino_')]
        self.assertEqual([(e['resource'], e['amount'], e['source']) for e in issues],
                         [('A', 3, 'infancia_destino_3')])
        self.assertEqual(observed[0]['A'], 3)

    def test_new_economic_board_exact_falls(self):
        for position, (resource, amount) in [
            (1, ('A', 3)), (2, ('P', 2)), (3, ('A', 3)),
            (4, ('P', 2)), (5, ('K', 1)), (6, ('A', 3))
        ]:
            p = PlayerState(1, 'Lucas', Stage.INFANCIA, (position - 2) % 6 + 1)
            g, eco, _ = game([p], hooks=RuleHooks(
                on_destination=lambda e, p, t: eco.on_destination(e, p, t)))
            g.start_round()
            g.play_turn(1, childhood_die=1)
            issues = [e for e in eco.events if e.get('source') == f'infancia_destino_{position}']
            self.assertEqual(len(issues), 1)
            self.assertEqual((issues[0]['resource'], issues[0]['amount']), (resource, amount))

    def test_entry_utn_consumes_step_exam_only_later(self):
        p = PlayerState(1, 'Clarisa', Stage.INFANCIA, 3)
        g, eco, profiles = game([p])
        eco.issue(1, 'P', 2, 'fixture')
        eco.issue(1, 'K', 1, 'fixture')
        # Neutralizar la carta para comprobar exclusivamente la secuencia UTN.
        g.hooks.apply_situation = lambda engine, player, card, letter: None
        g.start_round()
        outcome = g.play_turn(1, childhood_die=3, utn_die=6, choose_utn=True)
        self.assertEqual(outcome.target, 'UTN')
        self.assertEqual(p.stage, Stage.UTN)
        self.assertFalse(p.utn_passed)
        entry = [e for e in g.events if e['action'] == 'enter_utn']
        self.assertEqual((entry[0]['consumed'], entry[0]['discarded']), (3, 0))
        self.assertFalse(profiles.active)
        g.start_round()
        self.assertIn((Stage.INFANCIA, 'Clarisa'), g._revealed)
        out2 = g.play_turn(1, utn_die=6)
        self.assertEqual(out2.situation_id, g._revealed[(Stage.INFANCIA, 'Clarisa')].id)
        self.assertTrue(p.utn_passed)
        self.assertIn(1, profiles.active)
        g.start_round()
        self.assertEqual(p.stage, Stage.JUVENTUD)

    def test_utn_missing_resources_returns_to_circuit(self):
        p = PlayerState(1, 'Lucas', Stage.INFANCIA, 3)
        g, eco, _ = game([p], hooks=RuleHooks())
        g.start_round()
        g.play_turn(1, childhood_die=4, choose_utn=True)
        self.assertEqual(p.stage, Stage.UTN)
        self.assertTrue(p.utn_return_pending)
        g.start_round()
        g.play_turn(1, childhood_die=1, choose_utn=True)
        self.assertEqual((p.stage, p.position), (Stage.INFANCIA, 5))
        self.assertFalse(p.utn_return_pending)

    def test_youth_dublin_branch_spends_extra_step(self):
        a = PlayerState(1, 'Clarisa', Stage.JUVENTUD, 1, partner_id=2)
        b = PlayerState(2, 'Lucas', Stage.JUVENTUD, 1, partner_id=1)
        hooks = RuleHooks()
        def exit_dublin(engine, active):
            for member in engine.members(active):
                member.stage = Stage.DUBLIN
                member.position = Stage.DUBLIN.value
            return True
        hooks.dublin_exit = exit_dublin
        g, _, _ = game([a, b], hooks=hooks)
        g.start_round()
        letter = 'A' if a.youth_movement.a >= 2 else 'B'
        expected = a.youth_movement.distance(letter)
        out = g.play_turn(1, youth_choice=lambda p, c, m: letter,
                          choose_dublin=True)
        self.assertEqual(out.target, Stage.DUBLIN.value)
        event = next(e for e in g.events if e['action'] == 'enter_dublin_from_youth')
        self.assertEqual((event['consumed'], event['discarded']), (2, expected - 2))
        self.assertEqual(b.stage, Stage.DUBLIN)


class SIMLogV21Tests(unittest.TestCase):
    def test_shared_round_audit_and_3plus3(self):
        from laboratorio.simular_mazos_vigentes_v2 import run_game
        with tempfile.TemporaryDirectory() as folder:
            dest = Path(folder)
            result = run_game(6, 1, round_limit=5, trace_dir=dest)
            manifest = json.loads((dest / 'manifest.json').read_text(encoding='utf-8'))
            self.assertEqual(manifest['schema'], 'SIMLOG-2.1')
            self.assertEqual(manifest['ruleset'], 'especificacion-integral-2026-11-08')
            self.assertEqual(list(manifest['roles'].values()).count('Clarisa'), 3)
            with (dest / 'turnos.csv').open(encoding='utf-8-sig', newline='') as f:
                turns = list(csv.DictReader(f))
            with (dest / 'situaciones_por_ronda.csv').open(encoding='utf-8-sig', newline='') as f:
                shared = list(csv.DictReader(f))
            self.assertTrue(shared)
            self.assertEqual(len(turns), result['turns'])
            self.assertTrue(all('Recursos_antes_AB_JSON' in t for t in turns))
            for cohort in shared:
                assigned = [t for t in turns
                            if t['Ronda'] == cohort['Ronda']
                            and t['Situacion_grupo_etapa'] == cohort['Etapa']
                            and t['Situacion_grupo_rol'] == cohort['Rol']]
                self.assertEqual({t['Carta_ID'] for t in assigned},
                                 {cohort['Carta_compartida_ID']})
                self.assertEqual(len(assigned), int(cohort['Participantes_que_resolvieron']))


if __name__ == '__main__':
    unittest.main()
