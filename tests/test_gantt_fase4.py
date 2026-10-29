"""Fase 4.1: conservación de reglas, cronología por pareja ganadora y semilla."""
from __future__ import annotations

from dataclasses import replace
import unittest

from laboratorio.comparacion import escenario_base, ejecutar
from laboratorio.trazabilidad import (JuegoObservado, construir_cronologia,
                                      obtener_periodos, trazar_partida)
from laboratorio.gantt import grafico_gantt
from simulador.economia import EconomyConfig
from simulador.motor import Game, parse_cards
from laboratorio.ejecucion import CARDS


class PruebasGanttFase4(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = escenario_base(6, 3)
        cls.rows = ejecutar(cls.base)['filas']

    def test_trazado_reproduce_fila_original_y_ganadores(self):
        for n, esperado in enumerate(self.rows, 1):
            result = trazar_partida(self.base, n, esperado)
            self.assertTrue(result['equivalencia_fila'])
            self.assertTrue(result['finalizada'])
            self.assertEqual({x['id'] for x in result['ganadores']},
                             {int(x) for x in esperado['ganadores'].split('-')})
            self.assertEqual(result['ronda_casamiento'], esperado['rondas_observadas'])
            self.assertFalse(result['errores_integridad'])

    def test_individual_vs_mesa_y_pareja_ganadora(self):
        c = self.base
        result = trazar_partida(c, 2, self.rows[1])
        self.assertEqual(len([r for r in result['hitos'] if r['Grupo'] == 'Individual']), 6)
        self.assertEqual(len([r for r in result['hitos'] if r['Grupo'] == 'Pareja']), 3)
        self.assertEqual(len(result['ganadores']), 2)
        for h in result['hitos']:
            self.assertIsNotNone(h['Primera ronda'], h['Hito'])
            self.assertLessEqual(h['Primera ronda'], h['Ronda vigente final'])
            self.assertLessEqual(h['Ronda vigente final'], result['ronda_casamiento'])
        self.assertGreater(len(result['periodos']), len(result['hitos']))

    def test_grafico_contiene_barras_y_sin_datos_con_censura(self):
        valid = trazar_partida(self.base, 1, self.rows[0])
        chart = grafico_gantt(valid)
        self.assertGreaterEqual(len(chart.data), 4)
        self.assertTrue(all(str(x.type) == 'bar' for x in chart.data))
        self.assertEqual(len(grafico_gantt({'finalizada': False}).data), 0)

    def test_reduccion_economica_y_diez_jugadores(self):
        for cfg in (replace(self.base, economia=EconomyConfig(
                cartas_ganancias_pct=90, cartas_perdidas_pct=110)),
                escenario_base(10, 1)):
            row = ejecutar(cfg)['filas'][0]
            trace = trazar_partida(cfg, 1, row)
            self.assertTrue(trace['equivalencia_fila'])
            self.assertEqual(trace['ronda_casamiento'], row['rondas_observadas'])

    def test_motor_original_y_trazado_tienen_mismo_rng_y_eventos(self):
        cards = parse_cards(CARDS)
        kwargs = dict(log=True, max_rounds=120, bot_mode='mixed',
                      economia=EconomyConfig())
        original = Game(1, 131028, 6, cards, **kwargs).run()
        observado = JuegoObservado(1, 131028, 6, cards, **kwargs).run()
        self.assertEqual(original.summary(), observado.summary())
        self.assertEqual(original.eventlog, observado.eventlog)
        self.assertEqual(original.rng_dice.getstate(), observado.rng_dice.getstate())
        self.assertEqual(original.rng_cards.getstate(), observado.rng_cards.getstate())
        self.assertEqual(original.rng_bot.getstate(), observado.rng_bot.getstate())
        self.assertEqual(original.rng_economia.getstate(), observado.rng_economia.getstate())

    def test_intervalos_separan_perdida_y_recuperacion_en_misma_ronda(self):
        def snapshot(turno, activo):
            return dict(ronda=10, turno=turno,
                        jugadores={1:dict(pareja=4, titulo=activo, pasaporte=True,
                                         utn=True, afinidad=1, etapa='Juventud'),
                                   4:dict(pareja=1, titulo=True, pasaporte=True,
                                          utn=True, afinidad=1, etapa='Juventud')},
                        casa=None, finalizada=False, ganadores=None)
        snapshots = [snapshot(50, False), snapshot(51, True), snapshot(52, False),
                     snapshot(53, True), snapshot(54, True)]
        episodes = obtener_periodos(snapshots, (1, 4),
                                    [('titulo_1', 'Título #1', 'Individual')], 6)
        self.assertEqual(len(episodes), 2)
        self.assertEqual([x['turno_inicio'] for x in episodes], [51, 53])
        self.assertEqual([x['turno_fin'] for x in episodes], [52, 54])

    def test_censura_no_inventa_pareja_ganadora(self):
        cfg = replace(self.base, max_rondas=1)
        row = ejecutar(cfg)['filas'][0]
        self.assertFalse(row['terminada'])
        timeline = trazar_partida(cfg, 1, row)
        self.assertFalse(timeline['finalizada'])
        self.assertEqual(timeline['ganadores'], [])
        self.assertEqual(timeline['periodos'], [])

    def test_partida_fuera_de_lote_rechazada(self):
        with self.assertRaisesRegex(ValueError, 'fuera'):
            trazar_partida(self.base, 0)
        with self.assertRaisesRegex(ValueError, 'fuera'):
            trazar_partida(self.base, self.base.partidas+1)

    def test_no_confiar_en_resumen_divergente(self):
        altered = dict(self.rows[0])
        altered['ganadores'] = '1-2'
        with self.assertRaisesRegex(AssertionError, 'Divergencia'):
            trazar_partida(self.base, 1, altered)

class TestStreamlitGantt(unittest.TestCase):
    def test_gantt_visible_al_reconstruir(self):
        try:
            from streamlit.testing.v1 import AppTest
        except ImportError:
            self.skipTest('Streamlit solo disponible en el CI de GitHub')
        from laboratorio.ejecucion import ROOT
        app = AppTest.from_file(str(ROOT/'laboratorio/app.py'),default_timeout=120).run()
        self.assertFalse(app.exception)
        app.button[0].click().run(timeout=120)
        self.assertFalse(app.exception)
        self.assertTrue(any('Cronología de hitos' in s.value for s in app.subheader))
        self.assertGreaterEqual(len(app.button), 2)
        app.button[1].click().run(timeout=120)
        self.assertFalse(app.exception, str(app.exception))
        self.assertGreaterEqual(len(app.success), 1)


if __name__ == '__main__': unittest.main()
