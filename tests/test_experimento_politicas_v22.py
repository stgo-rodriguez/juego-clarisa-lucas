"""Regresión de banco, estrategias heterogéneas, A/B y mano experimental v2.2."""
import csv
import json
import random
import tempfile
import unittest
from pathlib import Path

from simulador.turnos_v2 import PlayerState, Stage
from simulador.experimento_politicas_v22 import (
    EconomyBankV22, assign_policies, CurrentResolverPoliciesV22,
)
from laboratorio.simular_v22 import run_game


class BankTests(unittest.TestCase):
    def setUp(self):
        self.a = PlayerState(1, 'Clarisa', Stage.INFANCIA, 1)
        self.eco = EconomyBankV22([self.a])
        self.eco.issue(1, 'A', 14, 'fixture')

    def test_multi_pairs_in_one_operation_and_conservation(self):
        self.eco.convert(1, 'A', 'P', 3, round_no=1)
        self.assertEqual(self.eco.accounts[1].free['A'], 8)
        self.assertEqual(self.eco.accounts[1].free['P'], 3)
        changes = [e for e in self.eco.events if e['action']=='conversion_bancaria']
        self.assertEqual(len(changes), 1)
        self.assertEqual((changes[0]['spent'], changes[0]['received']), (6, 3))
        self.assertTrue(self.eco.audit())

    def test_one_per_turn_and_can_reuse_next_round(self):
        self.eco.convert(1, 'A', 'P', 1, round_no=1)
        before = dict(self.eco.accounts[1].free)
        with self.assertRaisesRegex(ValueError, 'una operación'):
            self.eco.convert(1, 'A', 'P', 1, round_no=1)
        self.assertEqual(before, self.eco.accounts[1].free)
        self.eco.convert(1, 'A', 'P', 1, round_no=2)
        self.assertEqual(self.eco.accounts[1].free['P'], 2)

    def test_legal_adjacency_both_directions(self):
        self.eco.convert(1, 'A', 'P', 2, round_no=1)
        self.eco.convert(1, 'P', 'K', 1, round_no=2)
        self.eco.issue(1, 'K', 1, 'fixture')
        self.eco.convert(1, 'K', 'P', 1, round_no=3)
        self.assertTrue(self.eco.audit())
        with self.assertRaisesRegex(ValueError, 'A-P, P-K o K-M'):
            self.eco.convert(1, 'A', 'M', 1, round_no=4)
        with self.assertRaisesRegex(ValueError, 'A-P, P-K o K-M'):
            self.eco.convert(1, 'A', 'A', 1, round_no=4)

    def test_insufficient_funds_and_reserved_not_spendable(self):
        with self.assertRaisesRegex(ValueError, 'reservas'):
            self.eco.convert(1, 'A', 'P', 8, round_no=1)
        self.eco.accounts[1].free['A'] -= 5
        self.eco.accounts[1].pair_a = 5
        self.assertTrue(self.eco.audit())
        with self.assertRaisesRegex(ValueError, 'reservas'):
            self.eco.convert(1, 'A', 'P', 5, round_no=1)
        self.assertEqual(self.eco.accounts[1].pair_a, 5)

    def test_no_fractional_or_zero_pairs(self):
        for amount in [0, -2, 1.5, True]:
            with self.subTest(amount=amount):
                with self.assertRaises(ValueError):
                    self.eco.convert(1, 'A', 'P', amount, round_no=1)
        self.assertTrue(self.eco.audit())


class PolicyTests(unittest.TestCase):
    def test_assignment_balanced_by_role_and_seed(self):
        for size in (6, 10):
            players = [PlayerState(i+1, 'Clarisa' if i<size//2 else 'Lucas')
                       for i in range(size)]
            for seed in (3101,3102,3103):
                with self.subTest(size=size,seed=seed):
                    policies = assign_policies(players, 'mixto', seed)
                    self.assertEqual(policies, assign_policies(players, 'mixto', seed))
                    self.assertEqual(list(policies.values()).count('planificador'), size//2)
                    for role in ('Clarisa', 'Lucas'):
                        group=[policies[p.id] for p in players if p.role==role]
                        self.assertLessEqual(abs(group.count('planificador')-group.count('aleatorio')),1)
            self.assertNotEqual(assign_policies(players, 'mixto', 3101),
                                assign_policies(players, 'planificador', 3101))


class EndToEndTests(unittest.TestCase):
    def test_simlog_has_resolved_choices_and_bank_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            outcome=run_game(6,3101,round_limit=90,trace_dir=root,
                             policy='mixto',hand_size=3,bank_enabled=True)
            self.assertEqual(outcome['size'],6)
            self.assertEqual(outcome['hand_size'],3)
            self.assertGreater(outcome['bank_conversions'],0)
            manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
            self.assertEqual(manifest['schema'],'SIMLOG-2.2')
            self.assertEqual(manifest['adult_hand_size'],3)
            self.assertEqual(len(manifest['policies_by_player']),6)
            with (root/'eventos.csv').open(encoding='utf-8-sig') as f:
                events=list(csv.DictReader(f))
            actual=[json.loads(e['Detalle_JSON']).get('choice')
                    for e in events if e['Accion']=='situation_resolved']
            self.assertTrue(actual)
            self.assertTrue(all(x in ('A','B') for x in actual))
            with (root/'turnos.csv').open(encoding='utf-8-sig') as f:
                turns=list(csv.DictReader(f))
            bank=[t for t in turns if t['Canje']]
            self.assertGreater(len(bank),0)
            self.assertEqual(len(bank),outcome['bank_conversions'])
            policies={t['Politica'] for t in turns}
            self.assertEqual(policies, {'planificador','aleatorio'})
            self.assertEqual({t['Politica_partida'] for t in turns},{'mixto'})

    def test_four_card_hands_experimental_is_auditable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            outcome=run_game(6,3102,round_limit=90,trace_dir=root,
                             policy='planificador',hand_size=4,bank_enabled=True)
            self.assertEqual(outcome['hand_size'],4)
            manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
            self.assertEqual(manifest['adult_hand_size'],4)
            with (root/'eventos.csv').open(encoding='utf-8-sig') as f:
                renewed=[json.loads(e['Detalle_JSON'])
                         for e in csv.DictReader(f) if e['Accion']=='hand_renewed']
            self.assertTrue(renewed)
            self.assertTrue(all(len(ev['cards'])==4 for ev in renewed))

    def test_missing_adult_break_rule_is_censored_not_silently_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            out=run_game(6,3201,round_limit=100,trace_dir=root,
                         policy='mixto',hand_size=3,bank_enabled=True)
            self.assertIn(out['stop'], ('marriage','round_limit','rule_pending'))
            if out['stop']=='rule_pending':
                self.assertFalse(out['won'])
                self.assertIn('Ruptura',out['blocked_reason'])
                self.assertTrue((root/'bloqueo_reglamentario.json').exists())
                self.assertFalse((root/'turnos.csv').exists())
            else:
                self.assertTrue((root/'turnos.csv').exists())

    def test_random_policy_no_mixed_mapping_leak(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=run_game(6,3103,round_limit=90,trace_dir=Path(tmp),
                         policy='aleatorio',hand_size=3,bank_enabled=True)
            self.assertEqual(set(json.loads(out['policies_by_player']).values()), {'aleatorio'})


if __name__ == '__main__':
    unittest.main()
