"""Fase 4.1: conservación de reglas, cronología por pareja ganadora y semilla."""
from __future__ import annotations

from dataclasses import replace
import unittest

from laboratorio.comparacion import escenario_base, ejecutar
from laboratorio.trazabilidad import (JuegoObservado, construir_cronologia,
                                      obtener_periodos, trazar_partida)
from laboratorio.gantt import grafico_gantt, grafico_vigencia
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

    def test_cronologia_marca_logros_y_gantt_de_vigencia_opcional(self):
        valid = trazar_partida(self.base, 1, self.rows[0])
        chart = grafico_gantt(valid)
        self.assertGreaterEqual(len(chart.data), 4)
        self.assertTrue(all(str(x.type) == 'scatter' for x in chart.data))
        self.assertTrue(any('R' in str(t) for trace in chart.data for t in (trace.text or [])))
        self.assertTrue(all(str(x.type) == 'bar' for x in grafico_vigencia(valid).data))
        self.assertGreaterEqual(len([t for t in chart.data if t.mode == 'markers+text']), 4)
        self.assertIn('primera inversión hasta adjudicación', chart.layout.title.text)
        self.assertEqual(chart.layout.yaxis.ticktext.count('Ingreso UTN'), 2)
        self.assertIn('Casa en propiedad', chart.layout.yaxis.ticktext)

        self.assertEqual(len(grafico_gantt({'finalizada': False}).data), 0)

    def test_gantt_inicio_en_primera_inversion_del_proyecto_adjudicado(self):
        cronologia = trazar_partida(self.base, 1, self.rows[0])
        trabajos = cronologia['tramos_trabajo']
        self.assertTrue(trabajos)
        self.assertTrue(all(t['clave'].startswith(('titulo_', 'pasaporte_'))
                            for t in trabajos))
        self.assertTrue(all(t['rondas_transcurridas'] ==
                            t['ronda_fin'] - t['ronda_inicio'] for t in trabajos))
        self.assertTrue(all(t['rondas_transcurridas'] >= 0 for t in trabajos))
        self.assertEqual(len(trabajos), len({(t['clave'], t['proyecto']) for t in trabajos}))

        config = self.base
        juego = JuegoObservado(1, config.seed, config.jugadores, parse_cards(CARDS),
                               log=False, max_rounds=config.max_rondas,
                               bot_mode=config.bot, economia=config.economia).run()
        self.assertEqual(juego.summary(), self.rows[0])
        for trabajo in trabajos:
            inversiones = [inv for inv in juego.inversiones_proyectos
                           if inv['proyecto'] == trabajo['proyecto']]
            self.assertTrue(inversiones)
            primera = inversiones[0]
            self.assertEqual(trabajo['ronda_inicio'], primera['ronda'])
            self.assertEqual(trabajo['turno_inicio'], primera['turno'])
            self.assertEqual(trabajo['inversor_inicial'], primera['inversor'])
            self.assertEqual(trabajo['subhito_inicial'], 1)
            self.assertLessEqual(trabajo['turno_inicio'], trabajo['turno_fin'])
            self.assertTrue(any(periodo['clave'] == trabajo['clave'] and
                                periodo.get('proyecto') == trabajo['proyecto'] and
                                periodo['turno_inicio'] == trabajo['turno_fin']
                                for periodo in cronologia['periodos']))

        chart = grafico_gantt(cronologia)
        barras = [x for x in chart.data if x.mode == 'lines+markers']
        self.assertEqual(len(barras), len(trabajos))
        self.assertTrue(all('Primera inversión' in x.hovertemplate
                            for x in barras))
        self.assertTrue(all('Entre hitos' not in str(x.name) for x in barras))

    def test_sin_inversiones_no_inventa_tramos(self):
        self.assertEqual(trazar_partida(
            replace(self.base, max_rondas=1), 1)['tramos_trabajo'], [])
        self.assertEqual(len(grafico_gantt({
            'finalizada': True, 'periodos': [], 'tramos_trabajo': []
        }).data), 0)

    def test_perdidas_y_recuperaciones_son_eventos_separados(self):
        # En la referencia de 6 jugadores, semilla 131028, se pierde y
        # recupera la Casa: la vista principal nunca dibuja una barra larga.
        cronologia = trazar_partida(self.base, 1, self.rows[0])
        grafico = grafico_gantt(cronologia)
        nombres = [x.name for x in grafico.data]
        self.assertIn('Recuperación', nombres)
        self.assertIn('Pérdida / ruptura', nombres)
        self.assertTrue(all(x.type == 'scatter' for x in grafico.data))
        self.assertGreaterEqual(len(grafico_vigencia(cronologia).data), 1)

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
    def test_gantt_aparece_automaticamente_y_cambia_con_la_seleccion(self):
        try:
            from streamlit.testing.v1 import AppTest
        except ImportError:
            self.skipTest('Streamlit solo disponible en el CI de GitHub')
        from laboratorio.ejecucion import ROOT
        app = AppTest.from_file(str(ROOT/'laboratorio/app.py'), default_timeout=120).run()
        self.assertFalse(app.exception)
        # La ejecución inicial abre el Gantt automáticamente sin otro botón.
        app.button[0].click().run(timeout=120)
        self.assertFalse(app.exception, str(app.exception))
        self.assertTrue(any('Cronología de hitos' in s.value for s in app.subheader))
        self.assertFalse(any(b.label == 'Ver cronología y verificar partida' for b in app.button))
        self.assertGreaterEqual(len(app.success), 1)
        self.assertEqual(
            len([x for x in app.radio if x.label == 'Escenario de la partida']), 1)
        self.assertEqual(
            len([x for x in app.selectbox if x.label == 'Partida seleccionada']), 1)
        self.assertFalse(any(x.label.startswith('Escenario de interacciones')
                             for x in app.radio))
        self.assertFalse(any(x.label.startswith('Partida para auditar')
                             for x in app.selectbox))
        self.assertEqual(len(app.tabs), 4)
        primer = app.session_state['gantt_ultimo']
        self.assertEqual(primer[1]['partida'], 1)
        # Cambiar de partida debe reconstruirla sin clic adicional.
        selector = next(x for x in app.selectbox if x.label == 'Partida seleccionada')
        selector.set_value(2).run(timeout=120)
        self.assertFalse(app.exception, str(app.exception))
        segundo = app.session_state['gantt_ultimo']
        self.assertEqual(segundo[1]['partida'], 2)
        self.assertNotEqual(primer[0], segundo[0])
        # Cambiar de escenario también reconstruye, aunque conserve número.
        escenario = next(x for x in app.radio if x.label == 'Escenario de la partida')
        escenario.set_value('Experimento').run(timeout=120)
        self.assertFalse(app.exception, str(app.exception))
        tercero = app.session_state['gantt_ultimo']
        self.assertNotEqual(segundo[0], tercero[0])
        self.assertEqual(tercero[1]['partida'], 2)


class TestSelectorCompartido(unittest.TestCase):
    def test_vista_ampliada_mantiene_selector_y_oculta_configuracion(self):
        try:
            from streamlit.testing.v1 import AppTest
        except ImportError:
            self.skipTest('Streamlit solo disponible en CI')
        from laboratorio.ejecucion import ROOT
        app = AppTest.from_file(str(ROOT / 'laboratorio/app.py'), default_timeout=120).run()
        app.button[0].click().run(timeout=120)
        self.assertFalse(app.exception, str(app.exception))
        self.assertEqual(len(app.tabs), 4)
        next(x for x in app.button if x.label == 'Pantalla de análisis').click().run(timeout=120)
        self.assertFalse(app.exception, str(app.exception))
        self.assertEqual(len(app.tabs), 4)
        self.assertEqual(len(app.form), 0)
        self.assertTrue(any('Análisis de una partida · 6 jugadores' in x.value
                            for x in app.markdown))
        estilos = ' '.join(x.value for x in app.markdown if isinstance(x.value, str))
        self.assertIn('position: fixed !important', estilos)
        self.assertIn('data-baseweb="tab-panel"', estilos)
        self.assertIn('overflow-y: auto !important', estilos)
        self.assertIn('100dvh', estilos)
        self.assertEqual(len([x for x in app.selectbox if x.label == 'Partida seleccionada']), 1)
        self.assertTrue(any(x.label == 'Salir de pantalla de análisis' for x in app.button))
        next(x for x in app.selectbox if x.label == 'Partida seleccionada').set_value(2).run(timeout=120)
        self.assertFalse(app.exception, str(app.exception))
        for clave in ('gantt_ultimo', 'economia_ultima',
                      'interacciones_ultimas', 'turnos_ultimos'):
            self.assertEqual(app.session_state[clave][1]['partida'], 2)
        next(x for x in app.button if x.label == 'Salir de pantalla de análisis').click().run(timeout=120)
        self.assertFalse(app.exception, str(app.exception))
        self.assertGreaterEqual(len(app.form), 1)
        self.assertTrue(any(x.label == 'Pantalla de análisis' for x in app.button))


    def test_las_cuatro_vistas_usen_misma_partida_y_escenario(self):
        try:
            from streamlit.testing.v1 import AppTest
        except ImportError:
            self.skipTest("Streamlit solo disponible en CI")
        from laboratorio.ejecucion import ROOT
        app = AppTest.from_file(str(ROOT / 'laboratorio/app.py'), default_timeout=120).run()
        self.assertFalse(app.exception, str(app.exception))
        app.button[0].click().run(timeout=120)
        self.assertFalse(app.exception, str(app.exception))

        # ÚNICOS selectores de partida/escenario; los cuatro paneles comparten contexto.
        self.assertEqual(len([x for x in app.selectbox if x.label == 'Partida seleccionada']), 1)
        self.assertEqual(len([x for x in app.radio if x.label == 'Escenario de la partida']), 1)
        self.assertEqual(len(app.tabs), 4)

        next(x for x in app.selectbox if x.label == 'Partida seleccionada').set_value(3).run(timeout=120)
        self.assertFalse(app.exception, str(app.exception))
        self.assertEqual(app.session_state['gantt_ultimo'][1]['partida'], 3)

        for clave in ('economia_ultima', 'interacciones_ultimas', 'turnos_ultimos'):
            self.assertEqual(app.session_state[clave][1]['partida'], 3)

        # Una nueva selección reconstruye el Gantt y oculta auditorías previas.
        next(x for x in app.selectbox if x.label == 'Partida seleccionada').set_value(4).run(timeout=120)
        self.assertFalse(app.exception, str(app.exception))
        self.assertEqual(app.session_state['gantt_ultimo'][1]['partida'], 4)
        self.assertEqual(app.session_state['economia_ultima'][1]['partida'], 4)
        self.assertEqual(app.session_state['interacciones_ultimas'][1]['partida'], 4)
        self.assertEqual(app.session_state['turnos_ultimos'][1]['partida'], 4)
        self.assertTrue(any('Economía verificada' in m.value for m in app.success))
        self.assertTrue(any('Interacciones verificadas' in m.value for m in app.success))
        self.assertTrue(any('Actividad validada' in m.value for m in app.success))

        next(x for x in app.radio if x.label == 'Escenario de la partida').set_value('Experimento').run(timeout=120)
        self.assertFalse(app.exception, str(app.exception))
        self.assertEqual(app.session_state['gantt_ultimo'][1]['partida'], 4)
        self.assertEqual(app.session_state['gantt_ultimo'][0],
                         app.session_state['economia_ultima'][0])
        self.assertEqual(app.session_state['interacciones_ultimas'][0],
                         app.session_state['turnos_ultimos'][0])


if __name__ == '__main__': unittest.main()
