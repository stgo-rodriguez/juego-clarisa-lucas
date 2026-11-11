"""Regresión: los bots nunca eligen UTN sin 2 P + 1 K libres.

La regla física de la sección 06 permite llegar sin recursos y después
regresar al circuito; no se prohíbe esa decisión manual.
"""
from __future__ import annotations

import csv
import json
import random
import tempfile
import unittest
from pathlib import Path

from simulador.decision_utn_v2 import choose_utn_entry, record_utn_intent
from simulador.economia_v2 import EconomyScenario
from simulador.mazos_vigentes_v2 import load_current, new_decks
from simulador.movimiento_v2 import youth_cards
from simulador.reglas_v21 import EconomyV21, RoundEngineV21, transition_hooks_v21
from simulador.transiciones_v2 import ProfileDecksV2
from simulador.turnos_v2 import CardPool, PlayerState, Stage


def fixture():
    p=PlayerState(1,'Clarisa',Stage.INFANCIA,3)
    eco=EconomyV21([p],scenario=EconomyScenario(adult_square_amounts=None))
    profiles=ProfileDecksV2(13)
    hooks=transition_hooks_v21(eco, profiles)
    hooks.apply_situation=lambda engine,player,card,choice: None
    engine=RoundEngineV21(
        [p],new_decks(load_current(),17),
        CardPool(youth_cards(),random.Random(11),recycle=True),
        CardPool(youth_cards(),random.Random(12),recycle=True),
        hooks=hooks,rng_dice=random.Random(7),
    )
    engine.start_round()
    return p,eco,engine


class UTNPolicyTests(unittest.TestCase):
    def test_requires_both_free_resources(self):
        p,eco,g=fixture()
        self.assertFalse(choose_utn_entry(p,eco))
        eco.issue(1,'P',2,'fixture')
        self.assertFalse(choose_utn_entry(p,eco))
        eco.issue(1,'K',1,'fixture')
        self.assertTrue(choose_utn_entry(p,eco))
        p.stage=Stage.UTN
        self.assertFalse(choose_utn_entry(p,eco))

    def test_bot_skips_utn_without_knowledge_even_with_sufficient_personality(self):
        p,eco,g=fixture()
        eco.issue(1,'P',2,'fixture')
        decision=record_utn_intent(g,eco,p)
        self.assertFalse(decision)
        out=g.play_turn(1,childhood_die=3,choose_utn=decision)
        self.assertEqual(p.stage,Stage.INFANCIA)
        self.assertEqual(p.position,6)
        self.assertEqual(out.target,'casillero_infancia')
        self.assertFalse(any(e['action']=='enter_utn' for e in g.events))
        intent=[e for e in g.events if e['action']=='utn_entry_intent']
        self.assertEqual(len(intent),1)
        self.assertEqual((intent[0]['free_P'],intent[0]['free_K']), (2,0))

    def test_bot_enters_with_both_required_resources(self):
        p,eco,g=fixture()
        eco.issue(1,'P',2,'fixture');eco.issue(1,'K',1,'fixture')
        decision=record_utn_intent(g,eco,p)
        self.assertTrue(decision)
        out=g.play_turn(1,childhood_die=3,choose_utn=decision)
        self.assertEqual(p.stage,Stage.UTN)
        self.assertEqual(out.target,'UTN')
        self.assertFalse(p.utn_return_pending)
        self.assertTrue(any(e['action']=='utn_arrival_eligible' for e in g.events))
        self.assertEqual(sum(e['action']=='enter_utn' for e in g.events),1)
        self.assertEqual(eco.accounts[1].free['P'],2)
        self.assertEqual(eco.accounts[1].free['K'],1)

    def test_manual_entry_without_requirements_still_obeys_rule_06(self):
        p,eco,g=fixture()
        # Regla 06.1/06.3: entrada física permitida sin requisitos.
        out=g.play_turn(1,childhood_die=3,choose_utn=True)
        self.assertEqual(out.target,'UTN')
        self.assertTrue(p.utn_return_pending)
        self.assertFalse(p.utn_passed)
        self.assertEqual(len([e for e in g.events if e['action']=='utn_exam']),0)
        self.assertTrue(any(e['action']=='utn_requirements_missing' for e in g.events))

    def test_after_situation_resources_are_checked_again(self):
        p,eco,g=fixture()
        eco.issue(1,'P',2,'fixture');eco.issue(1,'K',1,'fixture')
        decision=record_utn_intent(g,eco,p)
        self.assertTrue(decision)
        # El jugador entró con recursos; la carta posterior le quita K.
        def lose_knowledge(engine,player,card,choice):
            eco.spend(1,'K',1,'situacion_fixture')
            return 'A'
        g.hooks.apply_situation=lose_knowledge
        g.play_turn(1,childhood_die=3,choose_utn=decision)
        self.assertEqual(p.stage,Stage.UTN)
        self.assertTrue(p.utn_return_pending)
        self.assertFalse(any(e['action']=='utn_exam' for e in g.events))
        self.assertEqual(eco.accounts[1].free['K'],0)


class SimulationsUTNTests(unittest.TestCase):
    def test_v22_simlog_audited_entry_intents(self):
        from laboratorio.simular_v22 import run_game as game22
        for version,run in [('2.2',game22)]:
            with self.subTest(version=version):
                with tempfile.TemporaryDirectory() as directory:
                    result=run(6,2001,round_limit=100,trace_dir=Path(directory),
                               policy='planificador',hand_size=3,bank_enabled=False)
                    self.assertEqual(result['size'],6)
                    self.assertGreater(result['utn_entry_intents_denied'],0)
                    self.assertGreater(result['utn_entries'],0)
                    if result['stop']=='rule_pending':
                        self.fail('Partida de regresión bloqueada por regla pendiente')
                    with (Path(directory)/'eventos.csv').open(encoding='utf-8-sig') as f:
                        events=list(csv.DictReader(f))
                    for idx,e in enumerate(events):
                        if e['Accion']!='enter_utn':
                            continue
                        options=[x for x in events[:idx]
                                 if x['Accion']=='utn_entry_intent'
                                 and x['Turno_global']==e['Turno_global']]
                        self.assertEqual(len(options),1)
                        intent=json.loads(options[0]['Detalle_JSON'])
                        self.assertTrue(intent['choose'])
                        self.assertGreaterEqual(intent['free_P'],2)
                        self.assertGreaterEqual(intent['free_K'],1)


if __name__=='__main__':
    unittest.main()
