"""Fase 2: controles de invariantes y casos de borde sin modificar el motor v1.3.

Distinguir pruebas de comportamiento reglamentario de pruebas de robustez
experimental. No se alteran las cartas, los bots ni la secuencia de semillas.
"""
from __future__ import annotations

import hashlib
import json
import random
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from simulador import motor_v13_base as original
from simulador.economia import EconomyConfig, ScenarioConfig, scaled_int
from simulador.motor import Game, run_batch, parse_cards
from laboratorio.ejecucion import ROOT, run

CARDS = parse_cards(ROOT / 'simulador' / 'cards_v13_effects.txt')
MOTOR_SHA = '9ea6c0b19c8ff7f76e07bf13ab8831b5d48e373a57c7e3fb2ea3d1d349f8ef32'


class ConfiguracionEstricta(unittest.TestCase):
    def test_motor_reglamentario_congelado(self):
        self.assertEqual(hashlib.sha256((ROOT/'simulador/motor_v13_base.py').read_bytes()).hexdigest(), MOTOR_SHA)

    def test_escenarios_originales_sin_cambios_de_economia(self):
        for n, seed in ((6, 131028), (10, 231028)):
            with self.subTest(jugadores=n):
                s = ScenarioConfig.load(ROOT/f'escenarios/base_v13_{n}j.json')
                self.assertEqual((s.jugadores, s.partidas, s.seed, s.incremento_seed, s.max_rondas, s.bot),
                                 (n, 1000, seed, 103, 120, 'mixed'))
                self.assertEqual(s.economia, EconomyConfig())

    def test_rechaza_multiplicadores_y_etapas_invalidos(self):
        for field in ('perfiles_pct','cartas_ganancias_pct','cartas_perdidas_pct','infancia_pct'):
            for v in (49, 151, 100.0, '100', None, True):
                with self.subTest(field=field, valor=v), self.assertRaises(ValueError):
                    EconomyConfig(**{field: v})
        for field in ('juventud_pct','adultez_pct'):
            for v in (1, 50, 150, True, -100, '0'):
                with self.subTest(field=field, valor=v), self.assertRaises(ValueError):
                    EconomyConfig(**{field: v})

    def test_rechaza_bots_desconocidos_y_semillas_incorrectas(self):
        for d in ({'bot': 'perfecto'}, {'incremento_seed': 0}, {'partidas': 0},
                  {'seed': '131028'}, {'max_rondas': 0}, {'jugadores': 7}):
            with self.subTest(campos=d), self.assertRaises(ValueError):
                ScenarioConfig(**d)

    def test_json_rechaza_campos_inesperados(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'escenario.json'
            p.write_text(json.dumps({'jugadores': 6, 'reglas_inventadas': 1}), encoding='utf-8')
            with self.assertRaises(ValueError): ScenarioConfig.load(p)
            p.write_text(json.dumps({'economia': {'alterar_costos': 10}}), encoding='utf-8')
            with self.assertRaises(ValueError): ScenarioConfig.load(p)


class EscaladoIndependiente(unittest.TestCase):
    def test_100_pct_conserva_exactamente_todos_los_rng(self):
        rng = random.Random(44)
        state = rng.getstate()
        for n in range(0, 101):
            self.assertEqual(scaled_int(n, 100, rng), n)
        self.assertEqual(rng.getstate(), state)

    def test_productos_enteros_sin_sorteos(self):
        rng = random.Random(45)
        state = rng.getstate()
        self.assertEqual(scaled_int(4, 50, rng), 2)
        self.assertEqual(scaled_int(2, 150, rng), 3)
        self.assertEqual(scaled_int(0, 90, rng), 0)
        self.assertEqual(rng.getstate(), state)

    def test_redondeo_fraccionario_acotado_reproducible_y_esperado(self):
        for amount, pct in ((1, 50), (1, 90), (1, 150), (3, 110), (7, 75)):
            with self.subTest(monto=amount, porcentaje=pct):
                def sample(seed):
                    rng = random.Random(seed)
                    return [scaled_int(amount, pct, rng) for _ in range(5000)]
                a = sample(2026)
                self.assertEqual(a, sample(2026))
                ideal = amount*pct/100
                self.assertTrue(all(int(ideal)<=v<=int(ideal)+1 for v in a))
                self.assertLess(abs(sum(a)/len(a) - ideal), 0.05)

    def test_economia_usa_rng_separado(self):
        g = Game(1, 777, 6, CARDS,
                 economia=EconomyConfig(perfiles_pct=70, cartas_ganancias_pct=110,
                                         cartas_perdidas_pct=130, infancia_pct=80))
        p = g.players[0]
        before = [rng.getstate() for rng in (g.rng_dice, g.rng_cards, g.rng_bot)]
        g.produce(p, 'A', 1, 'square')
        g.produce(p, 'M', 1, 'profile')
        g._scale_card(CARDS['J'][0])
        after = [rng.getstate() for rng in (g.rng_dice, g.rng_cards, g.rng_bot)]
        self.assertEqual(before, after)

    def test_efecto_de_carta_no_muta_mazo(self):
        g = Game(1, 777, 6, CARDS,
                 economia=EconomyConfig(cartas_ganancias_pct=50, cartas_perdidas_pct=150))
        c = CARDS['J'][0]
        before = (c.a.copy(), c.b.copy())
        scaled = g._scale_card(c)
        self.assertEqual((c.a, c.b), before)
        self.assertEqual(scaled.id, c.id)
        self.assertIn(scaled.a['A'], (-4, -5))  # J01: -3 por 150%, redondeo reproducible
        self.assertTrue(all(isinstance(v, int) for e in (scaled.a,scaled.b) for v in e.values()))

    def test_carta_neutra_no_consumo_rng_economia(self):
        g = Game(1, 777, 6, CARDS)
        state = g.rng_economia.getstate()
        for stage in ('I','J','A'):
            for c in CARDS[stage]:
                self.assertIs(g._scale_card(c), c)
        self.assertEqual(state, g.rng_economia.getstate())

    def test_produccion_perfil_registra_monto_transformado(self):
        g = Game(1, 701, 6, CARDS, economia=EconomyConfig(perfiles_pct=150))
        p = g.players[0]
        p.stage = 'Juventud'
        p.profile = g.market.take('Clarisa', 'tapada')
        g.produce(p, 'A', 4, 'profile')
        self.assertEqual(p.r['A'], 6)
        self.assertEqual(g.resource_flow['profile_A'], 6)
        self.assertEqual(g.profile_production[f'{p.profile.uid}_A'], 2)
        self.assertFalse(g.audit_ledger())

    def test_ingresos_juventud_y_adultez_independientes(self):
        for youth, adult in ((0, 0), (100, 0), (0, 100), (100, 100)):
            with self.subTest(juventud=youth, adultez=adult):
                g = Game(1, 701, 6, CARDS,
                         economia=EconomyConfig(juventud_pct=youth, adultez_pct=adult))
                p = g.players[0]
                p.stage = 'Juventud'
                g.square_gain([p], 'Juventud', 1, True)
                self.assertEqual(p.r['K'], 2 if youth else 0)
                p.stage = 'Adultez'
                g.square_gain([p], 'Adultez', 1, True)
                self.assertEqual(p.r['M'], 6 if adult else 0)
                self.assertFalse(g.audit_ledger())

    def test_fuentes_separadas_de_los_costos(self):
        g = Game(1, 701, 6, CARDS,
                 economia=EconomyConfig(perfiles_pct=50, infancia_pct=150))
        p = g.players[0]
        g.produce(p, 'A', 2, 'square')
        g.produce(p, 'A', 4, 'card')
        self.assertEqual(p.r['A'], 7)
        self.assertEqual(g.resource_flow['square_A'], 3)
        self.assertEqual(g.resource_flow['card_A'], 4)
        self.assertTrue(g.pay(p, 'A', 5, 'prueba', share=False))
        self.assertEqual(p.r['A'], 2)
        self.assertEqual(g.resource_flow['consume_prueba_A'], 5)
        self.assertFalse(g.audit_ledger())


class InvariantesEnPartidas(unittest.TestCase):
    def test_horizonte_corto_censura_sin_confundirla_con_victoria(self):
        for n in (6,10):
            g = Game(1, 101, n, CARDS, max_rounds=1).run()
            s = g.summary()
            self.assertEqual(s['terminada'], 0)
            self.assertEqual(s['censurada'], 1)
            self.assertEqual(s['rondas_observadas'], 1)
            self.assertEqual(s['rondas_hasta_casamiento'], '')
            self.assertFalse(g.errors)

    def test_perdidas_no_producen_saldos_negativos(self):
        g = Game(1, 701, 6, CARDS)
        p = g.players[0]
        for resource in original.R:
            g.loss(p, resource, 10_000)
            self.assertEqual(p.r[resource], 0)
        self.assertFalse(g.audit_ledger())

    def test_libro_mayor_detecta_alteraciones(self):
        g = Game(1, 701, 6, CARDS)
        self.assertFalse(g.audit_ledger())
        g.players[0].r['M'] += 1  # corrupción inyectada, nunca reglamentaria
        self.assertIn('M', g.audit_ledger())
        self.assertFalse(g.validate())
        self.assertTrue(any('balance del libro' in msg for msg in g.errors))

    def test_eventos_de_produccion_coinciden_con_libro_mayor(self):
        g = Game(1, 701, 6, CARDS, log=True,
                 economia=EconomyConfig(perfiles_pct=90, cartas_ganancias_pct=80,
                                         cartas_perdidas_pct=130)).run()
        events = Counter()
        for e in g.eventlog:
            if e['evento'] == 'produce':
                events[f"{e['fuente']}_{e['recurso']}"] += e['n']
        for k, v in events.items():
            self.assertEqual(v, g.resource_flow[k])
        self.assertFalse(g.audit_ledger())
        self.assertFalse(g.errors)

    def test_lote_extremos_con_bots_y_roles_constantes(self):
        configs = (
            EconomyConfig(perfiles_pct=50, cartas_ganancias_pct=50, cartas_perdidas_pct=150, infancia_pct=50),
            EconomyConfig(perfiles_pct=150, cartas_ganancias_pct=150, cartas_perdidas_pct=50, infancia_pct=150),
            EconomyConfig(juventud_pct=100, adultez_pct=0),
            EconomyConfig(juventud_pct=0, adultez_pct=100),
        )
        for n in (6, 10):
            for i, econ in enumerate(configs):
                with self.subTest(jugadores=n, perfil=econ.perfiles_pct, variante=i):
                    rows, _ = run_batch(25, n, 31000+n*10+i*1000, CARDS,
                                        log_samples=0, max_rounds=120, economia=econ)
                    self.assertEqual(len(rows),25)
                    self.assertTrue(all(x['jugadores']==n and x['errores']==0 for x in rows))
                    self.assertTrue(all(x['terminada']+x['censurada']==1 for x in rows))
                    self.assertTrue(all(int(x['rondas_observadas'])<=120 for x in rows))
                    self.assertTrue(all(int(x[f'saldo_{r}'])>=0 for x in rows for r in original.R))

    def test_integridad_despues_de_cada_turno(self):
        # Instrumentación de prueba: verificar al final de cada turno,
        # no únicamente al concluir la partida completa.
        for n in (6, 10):
            for econ in (EconomyConfig(), EconomyConfig(perfiles_pct=50,
                             cartas_ganancias_pct=50, cartas_perdidas_pct=150, infancia_pct=50)):
                for seed in (7001, 7002, 7003):
                    with self.subTest(jugadores=n, seed=seed, economia=econ.perfiles_pct):
                        g = Game(1, seed, n, CARDS, economia=econ)
                        for rnd in range(1, 31):
                            g.round = rnd
                            for p in g.players:
                                g.do_turn(p)
                                self.assertTrue(g.validate(), f'{rnd=}, {p.id=}, {g.errors=}')
                                self.assertFalse(g.audit_ledger())
                                if g.finished: break
                            if g.finished: break

    def test_mismo_escenario_y_semilla_reproduce_registros_completos(self):
        econ = EconomyConfig(perfiles_pct=75, cartas_ganancias_pct=90,
                             cartas_perdidas_pct=115, infancia_pct=85)
        a, sample_a = run_batch(4, 6, 9919, CARDS, log_samples=2, economia=econ)
        b, sample_b = run_batch(4, 6, 9919, CARDS, log_samples=2, economia=econ)
        self.assertEqual(a,b)
        self.assertEqual(sample_a,sample_b)
        self.assertEqual([x['semilla'] for x in a], [9919+i*103 for i in range(4)])

    def test_manifest_no_altera_entrada_y_registra_version(self):
        scenario = ScenarioConfig(id='smoke_fase2',jugadores=6,partidas=3,seed=4801,
                                  economia=EconomyConfig(perfiles_pct=90))
        with tempfile.TemporaryDirectory() as d:
            output=run(scenario, d)
            manifest=json.loads((Path(d)/'manifiesto.json').read_text(encoding='utf-8'))
            self.assertEqual(manifest['escenario'],scenario.as_dict())
            self.assertEqual(manifest['motor_sha256'],MOTOR_SHA)
            self.assertEqual(manifest['salida_sha256'],output['sha256'])
            self.assertEqual(hashlib.sha256(Path(output['csv']).read_bytes()).hexdigest(),output['sha256'])
