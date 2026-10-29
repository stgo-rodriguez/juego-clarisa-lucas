"""Pruebas de Fase 4.3: eventos, conciliación y comparabilidad de reejecución."""
from __future__ import annotations
from collections import Counter
from dataclasses import replace
import json
import unittest

from laboratorio.comparacion import escenario_base, ejecutar
from laboratorio.interacciones import (
    JuegoInteracciones, TIPOS, _resultado_duelo, resumen_interacciones,
    resumen_lote_interacciones, trazar_interacciones,
)
from laboratorio.graficos_interacciones import (
    figura_interacciones_por_ronda, figura_interacciones_por_tipo,
)
from laboratorio.ejecucion import CARDS
from simulador.economia import EconomyConfig
from simulador.motor import Game, parse_cards


class TestInteraccionesFase4(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c6 = escenario_base(6, 5)
        cls.b6 = ejecutar(cls.c6)
        cls.c10 = escenario_base(10, 5)
        cls.b10 = ejecutar(cls.c10)

    def test_replay_6_y_10_idéntico_y_sin_desajustes(self):
        for cfg, batch in ((self.c6, self.b6), (self.c10, self.b10)):
            for n, original in enumerate(batch['filas'], 1):
                r = trazar_interacciones(cfg, n, original)
                self.assertTrue(r['equivalencia_fila'])
                self.assertFalse(r['errores_auditoria'])
                self.assertFalse(r['errores_motor'])
                self.assertEqual(r['semilla'], original['semilla'])

    def test_log_original_y_rng_inalterados(self):
        cards = parse_cards(CARDS)
        opt = dict(max_rounds=120, bot_mode='mixed', log=True,
                   economia=EconomyConfig())
        original = Game(1, 131028, 6, cards, **opt).run()
        observado = JuegoInteracciones(1, 131028, 6, cards, **opt).run()
        self.assertEqual(original.summary(), observado.summary())
        self.assertEqual(original.eventlog, observado.eventlog)
        self.assertEqual(original.stats, observado.stats)
        for attr in ('rng_dice', 'rng_cards', 'rng_bot', 'rng_economia'):
            self.assertEqual(getattr(original, attr).getstate(),
                             getattr(observado, attr).getstate(), attr)

    def test_las_cuentas_de_duelo_conservan_resultados(self):
        r = trazar_interacciones(self.c10, 1, self.b10['filas'][0])
        outcomes = Counter(x['Resultado'] for x in r['por_resultado'] for _ in range(x['Cantidad']))
        self.assertEqual(sum(outcomes.values()), r['duelos'])
        self.assertEqual(outcomes['Retirada del retador'], r['retiradas'])
        self.assertEqual(outcomes['Gana defensor'] + outcomes['Empate'], r['defensas_sin_perder'])
        self.assertEqual(r['duelos'], sum(x['Cantidad'] for x in r['duelos_por_jugador']
                                        if x['Rol'] == 'Iniciados'))
        self.assertEqual(r['duelos'], sum(x['Cantidad'] for x in r['duelos_por_jugador']
                                        if x['Rol'] == 'Recibidos'))

    def test_dados_definen_el_resultado_sin_azar_adicional(self):
        self.assertEqual(_resultado_duelo('duelo', {'dado_retador':6, 'dado_defensor':5}), 'Gana retador')
        self.assertEqual(_resultado_duelo('duelo', {'dado_retador':1, 'dado_defensor':5}), 'Gana defensor')
        self.assertEqual(_resultado_duelo('duelo', {'dado_retador':3, 'dado_defensor':3}), 'Empate')
        self.assertEqual(_resultado_duelo('duelo_retirada', {}), 'Retirada del retador')
        self.assertIsNone(_resultado_duelo('ruptura', {}))

    def test_separacion_de_negociacion_ayuda_y_casa(self):
        r = trazar_interacciones(self.c6, 2, self.b6['filas'][1])
        for e in r['eventos']:
            self.assertIn(e['evento'], TIPOS)
            self.assertTrue(e['participantes'])
            self.assertEqual(e['categoria'], TIPOS[e['evento']][1])
            if e['evento'] == 'transfer_pair':
                self.assertEqual(e['categoria'], 'Redistribución')
            if e['evento'] == 'venta_comprobante':
                self.assertEqual(e['categoria'], 'Negociación')
            if e['evento'] == 'compra_casa':
                self.assertEqual(e['es_traspaso_casa'], bool(e['detalle']['expropietarios']))

    def test_audita_cuentas_contra_motor(self):
        cards = parse_cards(CARDS)
        juego = JuegoInteracciones(1, 131028, 6, cards, log=False,
                                  economia=EconomyConfig()).run()
        self.assertFalse(resumen_interacciones(juego)['errores_auditoria'])
        juego.stats['duels_started'] += 1
        errores = resumen_interacciones(juego)['errores_auditoria']
        self.assertTrue(any('duels_started' in e for e in errores))

    def test_rechaza_fila_alterada_y_numero_invalido(self):
        with self.assertRaises(ValueError):
            trazar_interacciones(self.c6, 0)
        with self.assertRaises(ValueError):
            trazar_interacciones(self.c6, 6)
        errada = dict(self.b6['filas'][0], ganadores='XXX')
        with self.assertRaisesRegex(AssertionError, 'divergentes'):
            trazar_interacciones(self.c6, 1, errada)

    def test_economia_extrema_y_escenarios_censurados(self):
        for n in (6,10):
            cfg = replace(escenario_base(n, 1),
                          economia=EconomyConfig(perfiles_pct=50,
                            cartas_ganancias_pct=50, cartas_perdidas_pct=150,
                            infancia_pct=50))
            a = ejecutar(cfg)
            r = trazar_interacciones(cfg, 1, a['filas'][0])
            self.assertFalse(r['errores_auditoria'])
            cfg_short = replace(cfg, max_rondas=2)
            row = ejecutar(cfg_short)['filas'][0]
            self.assertFalse(trazar_interacciones(cfg_short, 1, row)['finalizada'])

    def test_datos_del_lote_sin_participantes_ni_etapas_inventadas(self):
        datos = resumen_lote_interacciones(self.b6['filas'])
        self.assertEqual(len(datos), 13)
        self.assertNotIn('Etapa', datos[0])
        self.assertNotIn('Jugadores', datos[0])
        self.assertEqual(next(x['Total'] for x in datos if x['Código'] == 'duels_started'),
                         sum(int(x.get('duels_started', 0)) for x in self.b6['filas']))
        self.assertEqual(resumen_lote_interacciones([]), [])

    def test_resumen_tiene_conservacion_de_categorias_y_orden(self):
        r = trazar_interacciones(self.c10, 1, self.b10['filas'][0])
        self.assertEqual(sum(x['Cantidad'] for x in r['por_tipo']), r['total_eventos'])
        self.assertEqual(sum(x['Cantidad'] for x in r['por_categoria']), r['total_eventos'])
        self.assertEqual(sum(x['Cantidad'] for x in r['por_ronda']), r['total_eventos'])
        self.assertEqual([x['secuencia'] for x in r['eventos']],
                         list(range(1, r['total_eventos']+1)))
        self.assertGreater(r['total_eventos'],0)

    def test_json_exportable_y_figuras(self):
        r = trazar_interacciones(self.c6, 2, self.b6['filas'][1])
        raw = json.dumps(r, ensure_ascii=False)
        self.assertEqual(json.loads(raw)['total_eventos'],r['total_eventos'])
        self.assertGreaterEqual(len(figura_interacciones_por_tipo(r).data),1)
        self.assertGreaterEqual(len(figura_interacciones_por_ronda(r).data),1)
        empty = {'por_tipo': [], 'por_ronda': []}
        self.assertEqual(len(figura_interacciones_por_tipo(empty).data),0)
        self.assertEqual(len(figura_interacciones_por_ronda(empty).data),0)


class TestStreamlitInteracciones(unittest.TestCase):
    def test_panel_reconstruye_interacciones(self):
        try:
            from streamlit.testing.v1 import AppTest
        except ImportError:
            self.skipTest('Streamlit no está instalado aquí; se comprueba en GitHub Actions')
        from laboratorio.ejecucion import ROOT
        app = AppTest.from_file(str(ROOT/'laboratorio'/'app.py'), default_timeout=120).run()
        self.assertFalse(app.exception, str(app.exception))
        app.button[0].click().run(timeout=120)
        self.assertFalse(app.exception, str(app.exception))
        self.assertTrue(any('Interacciones' in x.value for x in app.subheader))
        self.assertFalse(any('Reconstruir y auditar interacciones' in b.label
                             for b in app.button))
        self.assertFalse(app.exception, str(app.exception))
        self.assertTrue(any('Interacciones verificadas' in x.value for x in app.success))

if __name__ == '__main__':
    unittest.main()
