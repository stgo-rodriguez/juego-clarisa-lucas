"""Fase 4.4: controles de observación pasiva, cobertura y UI."""
from __future__ import annotations
from collections import Counter
from dataclasses import replace
import json
import unittest

from laboratorio.comparacion import escenario_base,ejecutar
from laboratorio.ejecucion import CARDS
from laboratorio.turnos import (JuegoTurnos, trazar_turnos, resumir_turnos,
                               FAMILIAS, DECISIONES)
from laboratorio.graficos_turnos import figura_etapas, figura_familias
from simulador.economia import EconomyConfig
from simulador.motor import Game,parse_cards


class TestTurnos(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg6 = escenario_base(6,4)
        cls.filas6 = ejecutar(cls.cfg6)['filas']
        cls.cfg10 = escenario_base(10,4)
        cls.filas10 = ejecutar(cls.cfg10)['filas']

    def test_6_y_10_se_mantienen_equivalentes(self):
        for config, filas in ((self.cfg6,self.filas6),(self.cfg10,self.filas10)):
            for i, fila in enumerate(filas,1):
                out=trazar_turnos(config,i,fila)
                self.assertTrue(out['equivalencia_fila'])
                self.assertEqual(out['errores_auditoria'],[])
                self.assertEqual(out['errores_motor'],[])
                self.assertEqual(out['turnos'],fila['turnos_individuales'])

    def test_rng_eventlog_stats_sin_cambios(self):
        cards=parse_cards(CARDS)
        opts=dict(log=True,max_rounds=120,bot_mode='mixed',economia=EconomyConfig())
        original=Game(1,131028,6,cards,**opts).run()
        observed=JuegoTurnos(1,131028,6,cards,**opts).run()
        self.assertEqual(original.summary(),observed.summary())
        self.assertEqual(original.eventlog,observed.eventlog)
        self.assertEqual(original.stats,observed.stats)
        for attr in ('rng_dice','rng_cards','rng_bot','rng_economia'):
            self.assertEqual(getattr(original,attr).getstate(),getattr(observed,attr).getstate())

    def test_opciones_no_usan_rng_al_revisarlas(self):
        cards=parse_cards(CARDS)
        game=JuegoTurnos(1,131028,6,cards,economia=EconomyConfig())
        before=tuple(getattr(game,n).getstate() for n in ('rng_dice','rng_cards','rng_bot','rng_economia'))
        # no fase de turno activa; los chequeos no mutan
        game._op('Financiar subhito',True)
        after=tuple(getattr(game,n).getstate() for n in ('rng_dice','rng_cards','rng_bot','rng_economia'))
        self.assertEqual(before,after)

    def test_sumatoria_turnos_con_decision(self):
        r=trazar_turnos(self.cfg6,1,self.filas6[0]);t=r['turnos_detalle']
        self.assertEqual(sum(x['tiene_decision'] for x in t),r['turnos_con_decision'])
        self.assertEqual(sum(x['solo_automatico'] for x in t),r['turnos_solo_automaticos'])
        self.assertEqual(r['turnos_con_decision']+r['turnos_solo_automaticos'],r['turnos'])
        self.assertEqual(sum(x['decisiones_ejecutadas'] for x in t),r['decisiones_ejecutadas'])
        self.assertEqual(sum(x['Turnos'] for x in r['por_etapa']),r['turnos'])
        self.assertEqual(sum(x['Turnos'] for x in r['por_bot']),r['turnos'])

    def test_conteo_familias_es_por_turno_no_por_evento(self):
        r=trazar_turnos(self.cfg6,1,self.filas6[0]);t=r['turnos_detalle']
        for turn in t:
            self.assertEqual(len(turn['oportunidades']),len(set(turn['oportunidades'])))
            self.assertEqual(turn['familias_disponibles'],len(turn['oportunidades']))
            self.assertTrue(set(turn['oportunidades']).issubset(FAMILIAS))
            self.assertEqual(len(turn['activaciones']),len(set(turn['activaciones'])))
        for row in r['por_oportunidad']:
            self.assertEqual(row['Turnos disponibles'],sum(row['Acción'] in x['oportunidades'] for x in t))
            self.assertEqual(row['Turnos con ejecución'],sum(row['Acción'] in x['activaciones'] for x in t))

    def test_automatico_no_es_decision_del_bot(self):
        r=trazar_turnos(self.cfg6,1,self.filas6[0])
        decisiones=dict((e['Acción'],e['Cantidad']) for e in r['por_decision'])
        self.assertNotIn('Formar pareja',decisiones)
        self.assertNotIn('Intentar comprar Casa',decisiones)
        self.assertIn('Elegir desenlace de carta',DECISIONES.values())
        self.assertGreater(sum(t['eventos_automaticos'] for t in r['turnos_detalle']),0)

    def test_pruebas_pueden_detectar_error_contador(self):
        g=JuegoTurnos(1,131028,6,parse_cards(CARDS),economia=EconomyConfig()).run()
        self.assertEqual(resumir_turnos(g)['errores_auditoria'],[])
        g.stats['cards']+=1
        self.assertTrue(any('cards:' in x for x in resumir_turnos(g)['errores_auditoria']))

    def test_verifica_fila_alterada(self):
        row=dict(self.filas6[0]);row['ganadores']='cambiado'
        with self.assertRaisesRegex(AssertionError,'Divergencia de turnos'):
            trazar_turnos(self.cfg6,1,row)
        for n in (0,5):
            with self.assertRaises(ValueError):trazar_turnos(self.cfg6,n)

    def test_censura_y_economia_extrema(self):
        for players in (6,10):
            cfg=replace(escenario_base(players,1),max_rondas=2,
                economia=EconomyConfig(perfiles_pct=50,cartas_ganancias_pct=50,
                                      cartas_perdidas_pct=150,infancia_pct=50))
            row=ejecutar(cfg)['filas'][0]
            r=trazar_turnos(cfg,1,row)
            self.assertFalse(row['terminada'])
            self.assertEqual(r['turnos'],row['turnos_individuales'])
            self.assertEqual(r['errores_auditoria'],[])

    def test_ausencia_de_scores_pseudocientificos(self):
        r=trazar_turnos(self.cfg6,1,self.filas6[0])
        self.assertNotIn('diversion',r)
        self.assertNotIn('calidad_objetiva',r)
        self.assertIn('NO medida objetiva',r['advertencia'])

    def test_figuras_y_json(self):
        r=trazar_turnos(self.cfg6,2,self.filas6[1])
        self.assertEqual(json.loads(json.dumps(r))['turnos'],r['turnos'])
        self.assertEqual(len(figura_etapas(r).data),2)
        self.assertEqual(len(figura_familias(r).data),2)
        self.assertEqual(len(figura_etapas({'por_etapa':[]}).data),0)
        self.assertEqual(len(figura_familias({'por_oportunidad':[]}).data),0)


class TestStreamlitTurnos(unittest.TestCase):
    def test_panel_de_turnos_se_reconstruye(self):
        try:
            from streamlit.testing.v1 import AppTest
        except ImportError:
            self.skipTest('Streamlit se comprueba en GitHub Actions')
        from laboratorio.ejecucion import ROOT
        app=AppTest.from_file(str(ROOT/'laboratorio'/'app.py'),default_timeout=120).run()
        self.assertFalse(app.exception,str(app.exception))
        app.button[0].click().run(timeout=120)
        self.assertFalse(app.exception,str(app.exception))
        self.assertTrue(any('Actividad de turnos' in x.value for x in app.subheader))
        self.assertFalse(any('Reconstruir actividad de turnos' in x.label
                             for x in app.button))
        self.assertFalse(app.exception,str(app.exception))
        self.assertTrue(any('Actividad validada' in x.value for x in app.success))

if __name__=='__main__':unittest.main()
