"""Pruebas de trazabilidad pasiva de economía y conservación Fase 4.2."""
from __future__ import annotations
from collections import defaultdict
from dataclasses import replace
import unittest

from laboratorio.comparacion import escenario_base, ejecutar
from laboratorio.economia_trazable import JuegoEconomico, trazar_economia
from laboratorio.graficos_economia import resumen_lote, figura_flujos, figura_saldos
from laboratorio.ejecucion import CARDS
from simulador.motor import Game, parse_cards
from simulador.economia import EconomyConfig


class TestEconomiaFase4(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = escenario_base(6, 4)
        cls.resultado = ejecutar(cls.base)

    def test_regresion_economia_base(self):
        for i, fila in enumerate(self.resultado['filas'], 1):
            valor = trazar_economia(self.base, i, fila)
            self.assertTrue(valor['equivalencia_fila'])
            self.assertFalse(valor['errores_conciliacion'])
            self.assertFalse(valor['errores_motor'])
            self.assertTrue(valor['movimientos'])

    def test_stock_final_es_sumatoria_de_todos_los_movimientos(self):
        datos = trazar_economia(self.base, 1, self.resultado['filas'][0])
        neto = defaultdict(int)
        for item in datos['movimientos']:
            neto[item['recurso']] += item['delta']
            self.assertEqual(item['cantidad'], abs(item['delta']))
            self.assertIn(item['etapa'], ('Infancia', 'UTN', 'Juventud', 'Adultez'))
        self.assertEqual(dict(neto), datos['stock_final'])

    def test_transferencias_conservan_fichas_y_reparten_por_jugador(self):
        datos = trazar_economia(self.base, 1, self.resultado['filas'][0])
        grupos = defaultdict(list)
        for e in datos['movimientos']:
            if e['clase'] == 'transferencia':
                grupos[(e['turno'], e['ronda'], e['fuente'], e['recurso'])].append(e)
                self.assertIsNotNone(e['contraparte'])
        self.assertTrue(grupos)
        for _, grupo in grupos.items():
            self.assertEqual(sum(e['delta'] for e in grupo), 0)

    def test_fuente_perfil_carta_casilleros_y_banco(self):
        d = trazar_economia(self.base, 1, self.resultado['filas'][0])
        fuentes = {x['fuente'] for x in d['movimientos']}
        self.assertTrue({'profile', 'square', 'card', 'banco'}.issubset(fuentes))
        self.assertTrue(any(x['clase'] == 'inversion' for x in d['movimientos']))
        self.assertTrue(any(x['clase'] == 'perdida' for x in d['movimientos']))

    def test_stock_libre_mas_reservado_igual_stock(self):
        for n in (1, 2):
            d = trazar_economia(self.base, n, self.resultado['filas'][n-1])
            self.assertTrue(d['stock_por_etapa'])
            for x in d['stock_por_etapa']:
                total = (x['Libre medio']+x['Reservado pareja medio']+
                         x['Reservado casa medio'])
                self.assertAlmostEqual(total, x['Stock medio'], places=2)

    def test_restriccion_y_habilitar_ingresos_etapas(self):
        for players in (6, 10):
            config = replace(escenario_base(players, 1),
                             economia=EconomyConfig(cartas_ganancias_pct=90,
                                                    cartas_perdidas_pct=110,
                                                    juventud_pct=100,
                                                    adultez_pct=100))
            fila = ejecutar(config)['filas'][0]
            trace = trazar_economia(config, 1, fila)
            self.assertFalse(trace['errores_conciliacion'])
            self.assertFalse(trace['errores_motor'])
            self.assertEqual(trace['rondas_observadas'], fila['rondas_observadas'])

    def test_partida_censurada_conserva_economia(self):
        c = replace(self.base, max_rondas=2)
        fila = ejecutar(c)['filas'][0]
        d = trazar_economia(c, 1, fila)
        self.assertFalse(d['terminada'])
        self.assertTrue(d['movimientos'])
        self.assertFalse(d['errores_conciliacion'])

    def test_mismo_rng_eventos_y_resumen(self):
        cards = parse_cards(CARDS)
        cfg = dict(log=True, bot_mode='mixed', max_rounds=120,
                   economia=EconomyConfig())
        g = Game(1, 131028, 6, cards, **cfg).run()
        e = JuegoEconomico(1, 131028, 6, cards, **cfg).run()
        self.assertEqual(g.summary(), e.summary())
        self.assertEqual(g.eventlog, e.eventlog)
        for name in ('rng_dice', 'rng_cards', 'rng_bot', 'rng_economia'):
            self.assertEqual(getattr(g, name).getstate(),
                             getattr(e, name).getstate(), name)
        self.assertFalse(e.desajustes)

    def test_validacion_partida_y_comparacion_de_filas(self):
        with self.assertRaises(ValueError):
            trazar_economia(self.base, 0)
        with self.assertRaises(ValueError):
            trazar_economia(self.base, 5)
        bad = dict(self.resultado['filas'][0], ganadores='1-2')
        with self.assertRaisesRegex(AssertionError, 'divergente'):
            trazar_economia(self.base, 1, bad)

    def test_metricas_por_lote_no_inventan_etapas(self):
        vals = resumen_lote(self.resultado['filas'])
        self.assertTrue(vals)
        self.assertFalse(any('Etapa' in x for x in vals))
        self.assertTrue(any(x['Fuente'] == 'profile' for x in vals))

    def test_figuras_economicas(self):
        d = trazar_economia(self.base, 1, self.resultado['filas'][0])
        self.assertGreater(len(figura_flujos(d['movimientos']).data), 2)
        self.assertEqual(len(figura_saldos(d['stock_por_etapa']).data), 3)
        self.assertEqual(len(figura_flujos(d['movimientos'], etapas=['Sin etapa']).data), 0)


if __name__ == '__main__':
    unittest.main()

class TestStreamlitEconomia(unittest.TestCase):
    def test_interfaz_economia_disponible_y_trazable(self):
        try:
            from streamlit.testing.v1 import AppTest
        except ImportError:
            self.skipTest('Streamlit no disponible en este entorno')
        from laboratorio.ejecucion import ROOT
        app = AppTest.from_file(str(ROOT / 'laboratorio/app.py'), default_timeout=120).run()
        self.assertFalse(app.exception, str(app.exception))
        app.button[0].click().run(timeout=120)
        self.assertFalse(app.exception, str(app.exception))
        self.assertTrue(any('Economía de recursos' in x.value for x in app.subheader))
        self.assertTrue(any('Reconstruir economía' in x.label for x in app.button))
        btn = next(x for x in app.button if 'Reconstruir economía' in x.label)
        btn.click().run(timeout=120)
        self.assertFalse(app.exception, str(app.exception))
        self.assertTrue(any('Economía verificada' in x.value for x in app.success))
