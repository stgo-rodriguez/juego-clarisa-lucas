"""Integridad de datos históricos y aislamiento de la vista v2.1."""
import unittest
from collections import Counter
from laboratorio.v21_ultima import cargar_resumen, cargar_partida, cronologia


class TestResultadosV21(unittest.TestCase):
    def test_resumen_corresponde_a_la_corrida_oficial(self):
        x = cargar_resumen()
        self.assertEqual(x['source']['artifact_id'], 13606319833)
        self.assertEqual(x['source']['workflow_run_id'], 42454007039)
        self.assertEqual(x['summary']['total_games'], 200)
        self.assertEqual(x['summary']['total_marriages'], 200)
        self.assertEqual(x['summary']['total_decisions'], 28708)
        self.assertEqual(Counter(g['size'] for g in x['games']), {6: 100, 10: 100})
        self.assertEqual(x['summary']['winners_by_zone']['Neutro'], 147)
        self.assertEqual(x['summary']['summary'][0]['avg_rounds_censored'], 18.8)
        self.assertEqual(x['summary']['summary'][1]['avg_rounds_censored'], 18.14)

    def test_doscientas_partidas_con_traza_verificable(self):
        for size in (6, 10):
            for seed in range(101, 201):
                trace = cargar_partida(size, seed)
                self.assertTrue(trace['turns'])
                self.assertTrue(trace['resources'])
                self.assertTrue(trace['events'])

    def test_cronologia_inversion_y_casamiento_separados(self):
        games = cargar_resumen()['games']
        partida = next(g for g in games if g['size'] == 6 and g['seed'] == 101)
        hitos = cronologia(partida, cargar_partida(6, 101))
        self.assertTrue(any(h[0] == 'Casamiento' and h[3] == 21 for h in hitos))
        self.assertTrue(any(h[0] == 'Pareja formada' for h in hitos))
        self.assertTrue(any(h[0] == 'Título' for h in hitos))
        self.assertTrue(all(h[2] is None or h[2] <= h[3] for h in hitos))

    def test_vista_streamlit_v21_no_ejecuta_motor_v13(self):
        from streamlit.testing.v1 import AppTest
        from laboratorio.ejecucion import ROOT
        a = AppTest.from_file(str(ROOT / 'laboratorio/app.py'),
                              default_timeout=120).run()
        self.assertFalse(a.exception, str(a.exception))
        vista = next(x for x in a.radio if x.label == 'Versión del laboratorio')
        vista.set_value('Resultados v2.1').run(timeout=120)
        self.assertFalse(a.exception, str(a.exception))
        self.assertTrue(any('Última simulación registrada' in x.value for x in a.title))
        self.assertEqual(len(a.tabs), 4)
        self.assertTrue(any(s.label == 'Semilla' for s in a.selectbox))
        self.assertNotIn('ultima_comparacion', a.session_state)


if __name__ == '__main__':
    unittest.main()
