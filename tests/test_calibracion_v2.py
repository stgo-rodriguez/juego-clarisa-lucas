"""Fase 11: prueba de factores independientes, integridad documental y comparaciones apareadas."""
import csv
import hashlib
import json
from pathlib import Path
import random
import tempfile
import unittest
from types import SimpleNamespace
from simulador.turnos_v2 import PlayerState, SituationCard, Stage
from simulador.movimiento_v2 import Coord
from simulador.economia_v2 import EconomyV2, EconomyScenario
from simulador.mazos_propuestos_v2 import BalanceVariant, ProposedResolver, load_catalog, CATALOG_PATH
from laboratorio.experimento_mazos_propuestos_v2 import run_proposal
from laboratorio.calibracion_cartas_v2 import variants,simulate,aggregate,effects,write_report


class TestCalibration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog=load_catalog()
        cls.sha256=hashlib.sha256(Path(CATALOG_PATH).read_bytes()).hexdigest()

    def eco(self,stage=Stage.JUVENTUD):
        p=PlayerState(1,'Clarisa',stage,Coord(5,3) if stage==Stage.ADULTEZ else 1)
        return p,EconomyV2([p],scenario=EconomyScenario(adult_square_amounts=dict.fromkeys('APKM',2)))

    def test_eight_factorial_variants_and_original(self):
        vs=variants()
        self.assertEqual(len(vs),8)
        self.assertEqual(vs['cal_000'],BalanceVariant())
        self.assertEqual(vs['cal_111'],BalanceVariant(.60,.70,1.5))
        self.assertEqual({v.early_gain for v in vs.values()},{.60,1})

    def test_invalid_factors_rejected(self):
        for value in (-.1,0,3.5,float('nan'),True):
            with self.assertRaises(ValueError):BalanceVariant(early_gain=value)

    def test_integer_rounding_without_random_dice(self):
        self.assertEqual([ProposedResolver._scale(n,.75) for n in [1,2,3,4,6,10]],
                         [1,2,2,3,5,8])
        self.assertEqual(ProposedResolver._scale(3,1.5),5)

    def test_juvenile_gain_and_loss_scaled_on_free_only(self):
        p,eco=self.eco()
        eco.issue(1,'A',2,'fixture')
        resolver=ProposedResolver(eco,balance=BalanceVariant(.75,1,1.5))
        card=SituationCard('FIX',Stage.JUVENTUD,'Clarisa',{'origin':'historical_copy',
            'effects':{'A':{'K':4,'A':-3},'B':{'P':2}}})
        engine=SimpleNamespace(round_no=1)
        resolver.resolve(engine,p,card,'A')
        self.assertEqual(eco.accounts[1].free['K'],3)
        self.assertEqual(eco.accounts[1].free['A'],0)
        eco.audit()

    def test_adult_free_rewards_not_costs_are_scaled(self):
        p,eco=self.eco(Stage.ADULTEZ)
        eco.issue(1,'P',2,'fixture')
        resolver=ProposedResolver(eco,balance=BalanceVariant(.75,.5,1.5))
        resolver._pick=lambda choices,pid:0  # Forzar opción A para verificar costos sin optimización
        row=next(x for x in self.catalog['adult_proposals_30'] if x['id']=='AD-C-01')
        card=SituationCard(row['id'],p.stage,p.role,{'origin':'adult_proposal',**row})
        resolver.resolve(SimpleNamespace(round_no=1),p,card,None)
        # Pago original 2 Personalidad se conserva; ganancia 4M se reduce a 2M.
        self.assertEqual(eco.accounts[1].free['P'],0)
        self.assertEqual(eco.accounts[1].free['M'],2)
        eco.audit()

    def test_social_auction_proportions_conserved_after_calibration(self):
        class Stub:
            last=None
            def resolve_social_situation(self,e,p,card,cb,choice):self.last=card.payload
        for id in ('AD-C-12','AD-C-13','AD-C-14','AD-C-15'):
            p,eco=self.eco(Stage.ADULTEZ)
            controller=Stub()
            resolver=ProposedResolver(eco,balance=BalanceVariant(1,.75,1),
                                       competition_controller=controller)
            row=next(x for x in self.catalog['adult_proposals_30'] if x['id']==id)
            card=SituationCard(row['id'],p.stage,p.role,{'origin':'adult_proposal',**row})
            resolver.resolve(SimpleNamespace(round_no=1),p,card,None)
            self.assertEqual(controller.last.total,5)
            self.assertEqual(controller.last.appropriable,3)
            self.assertEqual(controller.last.total-controller.last.appropriable,2)
            self.assertEqual(controller.last.allow_reject, id in ('AD-C-14','AD-C-15'))

    def test_unchanged_source_json_hash(self):
        self.assertEqual(hashlib.sha256(Path(CATALOG_PATH).read_bytes()).hexdigest(),self.sha256)
        self.assertEqual(len(self.catalog['historical_78']),78)
        self.assertEqual(len(self.catalog['adult_proposals_30']),30)

    def test_baseline_matches_fase10_stored_games(self):
        file=Path(__file__).resolve().parent.parent/'docs/datos_fase10/partidas_mazos_documentados_320.csv'
        with file.open(encoding='utf-8') as handle:
            rows=list(csv.DictReader(handle))
        for row in (rows[0],rows[1],rows[50],rows[-1]):
            new=run_proposal(int(row['size']),int(row['seed']),row['policy'],
                    row['competition'].lower()=='true',rounds=100,balance=BalanceVariant())
            self.assertEqual(new['rounds'],int(row['rounds']))
            self.assertEqual(new['bids'],int(row['bids']))
            self.assertEqual(new['duels'],int(row['duels']))

    def test_deterministic_calibration(self):
        a=run_proposal(6,2,'planificador',True,rounds=80,
                       balance=BalanceVariant(.75,.75,1.5))
        b=run_proposal(6,2,'planificador',True,rounds=80,
                       balance=BalanceVariant(.75,.75,1.5))
        self.assertEqual(a,b)
        self.assertEqual(a['early_gain_factor'],.75)
        self.assertLessEqual(a['no_progress_ratio'],1.0)

    def test_small_factorial_and_aggregate_consistency(self):
        rows=simulate(1,80,policies=('planificador',),competitions=(True,),sizes=(6,))
        self.assertEqual(len(rows),8)
        self.assertEqual(len(aggregate(rows)),8)
        ef=effects(rows)
        self.assertEqual(len(ef),3)
        self.assertTrue(all(x['paired_n']==4 and x['independent_seed_blocks']==1 for x in ef))
        self.assertEqual(len({x['scenario'] for x in rows}),8)
        with tempfile.TemporaryDirectory() as d:
            report=write_report(rows,Path(d),seeds=1,rounds=80)
            self.assertEqual(report['total_games'],8)
            self.assertEqual(sum(r['won'] for r in rows),report['marriages'])
            self.assertTrue((Path(d)/'efectos_apareados_v2.csv').is_file())

    def test_social_conservation_in_real_game(self):
        r=run_proposal(10,1,'planificador',True,rounds=100,
                       balance=BalanceVariant(.75,.75,1.5))
        self.assertTrue(r['won'])
        self.assertGreater(r['social_auctions'],0)
        self.assertGreaterEqual(r['card_gains_units'],0)
        self.assertGreaterEqual(r['card_losses_units'],0)


if __name__=='__main__':unittest.main()