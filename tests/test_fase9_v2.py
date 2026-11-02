"""Fase 9: diseño factorial completo y reserva juvenil con ayuda/ruptura."""
import tempfile
import unittest
from pathlib import Path

from laboratorio.factorial_v2 import (FACTORS, treatments, treatment, grouped_summary,
                                    paired_effects, save)
from laboratorio.rupturas_v2 import summarize as reserve_summary, paired as reserve_paired
from laboratorio.sensibilidad_v2 import StressScenario, run_game


class TestFactorial(unittest.TestCase):
    def test_ocho_tratamientos_sin_duplicacion(self):
        combos=treatments()
        self.assertEqual(len(combos),8)
        self.assertEqual(len({item.id for _,item in combos}),8)
        self.assertEqual(combos[0][1], StressScenario('F000',1.0,adult_square_amount=2,profile_yield=1.0))
        self.assertEqual(combos[-1][1], StressScenario('F111',.6,adult_square_amount=1,profile_yield=.6))
        self.assertEqual(FACTORS,('situation','profile','square'))

    def test_invalid_binary_levels(self):
        with self.assertRaises(ValueError):treatment((0,1))
        with self.assertRaises(ValueError):treatment((0,2,1))

    @staticmethod
    def sample_factorial():
        out=[]
        for bits,scenario in treatments():
            a,b,c=bits
            # Y=10+3A+2B+C+4AB+7BC+9ABC: known interaction exactly 9.
            rounds=10+3*a+2*b+c+4*a*b+7*b*c+9*a*b*c
            out.append({'size':6,'seed':1,'policy':'planificador','competition':True,
                        'scenario':scenario.id,'f_situation':a,'f_profile':b,'f_square':c,
                        'rounds':rounds,'won':True,'no_progress_ratio':.1,'pair_breaks':0})
        return out

    def test_interactions_not_confounded_with_main_effects(self):
        e=paired_effects(self.sample_factorial())
        triple=next(r for r in e if r['type']=='interaction3')
        self.assertEqual(triple['mean'],9)
        pair=next(r for r in e if r['type']=='interaction2' and r['factor']=='situation×profile')
        self.assertEqual(pair['mean'],8.5)
        self.assertEqual(pair['blocks'],1)
        self.assertEqual(len(e),10)

    def test_incomplete_factorial_refused(self):
        with self.assertRaises(ValueError):paired_effects(self.sample_factorial()[:-1])
        with self.assertRaises(ValueError):paired_effects(self.sample_factorial()*2)

    def test_export_reproducible_and_exploratory(self):
        with tempfile.TemporaryDirectory() as d:
            report=save(self.sample_factorial(),Path(d),{'sample':'synthetic'})
            self.assertEqual(report['runs'],8)
            self.assertEqual(len(grouped_summary(self.sample_factorial())),8)
            self.assertTrue((Path(d)/'partidas_factorial_v2.csv').is_file())
            self.assertTrue((Path(d)/'efectos_factoriales_v2.csv').is_file())
            self.assertIn('SINTÉTICOS',report['disclaimer'])


class TestReserveLoss(unittest.TestCase):
    scenario=StressScenario('prueba_juventud',1.0)

    def test_parameter_validation(self):
        for rate,amount in [(-.1,5),(1.01,5),(.1,0),(.1,6)]:
            with self.assertRaises(ValueError):
                run_game(6,1,'planificador',True,self.scenario,
                         rounds=5,youth_reserve_loss_rate=rate,youth_reserve_loss_amount=amount)

    def test_fixture_disabled_is_baseline_reproducible(self):
        kw=dict(size=6,seed=2,policy='planificador',competition=True,
                scenario=self.scenario,rounds=50)
        a=run_game(**kw)
        b=run_game(**kw,youth_reserve_loss_rate=0.0)
        self.assertEqual((a['rounds'],a['won'],a['duels']),
                         (b['rounds'],b['won'],b['duels']))
        self.assertEqual(a['reserve_events'],0)
        self.assertEqual(a['reserve_breaks'],0)

    def test_loss_at_situation_before_movement_can_break(self):
        r=run_game(6,2,'planificador',True,self.scenario,
                   rounds=45,youth_reserve_loss_rate=1.0,youth_reserve_loss_amount=5,
                   with_events=True)
        self.assertGreater(r['reserve_events'],0)
        self.assertGreater(r['reserve_repairs'],0)
        self.assertGreater(r['reserve_breaks'],0)
        self.assertEqual(r['reserve_events'],r['reserve_repairs']+r['reserve_breaks'])
        self.assertEqual(r['reserve_breaks'],r['pair_breaks'])
        # A fixture with reserve damage cannot create/lose unaccounted resources.
        events=r['interaction_events']
        self.assertTrue(any(x['action']=='pair_reserve_repaired' for x in events))
        self.assertTrue(any(x['action']=='pair_reserve_not_repaired' for x in events))

    def test_loss_run_is_deterministic(self):
        kw=dict(size=6,seed=3,policy='aleatorio',competition=False,
                scenario=self.scenario,rounds=40,youth_reserve_loss_rate=.35)
        a,b=run_game(**kw),run_game(**kw)
        self.assertEqual((a['rounds'],a['reserve_breaks'],a['reserve_repairs']),
                         (b['rounds'],b['reserve_breaks'],b['reserve_repairs']))

    def test_paired_controls_require_baseline(self):
        with self.assertRaises(ValueError):
            reserve_paired([{'size':6,'seed':1,'policy':'planificador','competition':True,
                             'youth_reserve_loss_rate_experimental':.35,'rounds':20,'won':True}])


if __name__=='__main__':unittest.main()
