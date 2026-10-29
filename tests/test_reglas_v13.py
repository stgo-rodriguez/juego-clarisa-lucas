"""Pruebas reglamentarias y de invariantes para simulador v1.3.0-exp1."""
import unittest
from pathlib import Path
from simulador.motor_v13_base import Game,parse_cards,Project,Receipt,PROFILES,R

CARDS=parse_cards(Path(__file__).resolve().parents[1]/'simulador'/'cards_v13_effects.txt')

class FixedDice:
    def __init__(self,*values):self.vals=list(values)
    def randint(self,a,b):return self.vals.pop(0) if self.vals else b

class Rules(unittest.TestCase):
    def setUp(self):
        self.g=Game(1,101,6,CARDS,log=True)
        self.a,self.b,self.c=self.g.players[:3]
        self.l=self.g.players[3]
    def youth(self,p):p.stage='Juventud';p.pos=1;p.utn=True
    def profile(self,p):
        p.profile=self.g.market.take(p.role,'tapada');return p.profile
    def test_card_decks_complete(self):
        self.assertEqual(tuple(len(CARDS[k]) for k in ('I','J','A')),(24,24,30))
        self.assertEqual(CARDS['J'][1].a,{'A':0,'P':0,'K':-2,'M':3})
    def test_utn_requirement_only_not_payment(self):
        self.a.r.update(P=2,K=1);self.a.stage='UTN';self.a.pos=0
        self.g.rng_dice=FixedDice(6);self.g.utntest(self.a)
        self.assertTrue(self.a.utn);self.assertEqual((self.a.free('P'),self.a.free('K')),(2,1))
        self.assertIsNotNone(self.a.profile)
        self.g.loss(self.a,'K',1);self.g.loss(self.a,'P',2)
        self.assertTrue(self.a.utn);self.assertTrue(self.a.utn_passed)
    def test_first_profile_after_utn(self):
        self.assertIsNone(self.a.profile)
        self.a.r.update(P=2,K=1);self.a.stage='UTN'
        self.g.rng_dice=FixedDice(3,6)
        self.g.utntest(self.a);self.assertIsNone(self.a.profile)
        self.g.utntest(self.a);self.assertIsNotNone(self.a.profile)
    def test_profile_production_only_when_crossing_mark(self):
        self.youth(self.a);card=self.profile(self.a)
        self.a.pos=5;self.g.rng_dice=FixedDice(1)
        before=self.a.r.copy();self.g.roll_movement(self.a)
        self.assertEqual(self.a.r,before)
        self.g.rng_dice=FixedDice(1);self.g.roll_movement(self.a)
        for i,r in enumerate(R):self.assertEqual(self.a.r[r]-before[r],card.production[i])
        self.assertEqual(self.g.stats['lap_crossings'],1)
    def test_childhood_circuits_cannot_cross_form_pair(self):
        self.a.r['A']=10;self.l.r['A']=10
        self.a.pos=self.l.pos=2
        self.g.pair_encounters(self.a)
        self.assertIsNone(self.a.pair)
    def test_subhitos_indivisible_sequential_and_no_double(self):
        self.youth(self.a);self.a.r['K']=10
        funded=set();self.g.funding(self.a,funded)
        uni=[x for x in self.g.projects.values() if x.kind=='Titulo'][0]
        self.assertEqual(len(uni.subhitos),1)
        self.g.funding(self.a,funded);self.assertEqual(len(uni.subhitos),1)
        self.assertEqual(self.g.receipts[uni.subhitos[0]].original,self.a.id)
        self.assertEqual(self.a.r['K'],9)
        self.assertEqual(self.g.receipts[uni.subhitos[0]].id,uni.id+'-S1')
    def test_passport_first_two_funders_must_match_role(self):
        self.youth(self.a);self.youth(self.l)
        pr=Project('Italia-1','Italia');self.g.projects[pr.id]=pr
        self.l.r['P']=12
        self.assertFalse(self.g.can_fund(self.l,pr))
        self.a.r['P']=2;self.assertTrue(self.g.can_fund(self.a,pr))
    def test_investment_protected(self):
        self.youth(self.a);self.a.r['K']=1
        self.g.funding(self.a,set())
        self.assertEqual(self.a.r['K'],0)
        self.g.loss(self.a,'K',20)
        self.assertEqual(self.a.r['K'],0)
        self.assertEqual(len(self.g.receipts),1)
    def test_receipt_transfer_changes_right(self):
        self.youth(self.a);self.youth(self.b)
        pr=Project('Titulo-1','Titulo',subhitos=['Titulo-1-S1'])
        self.g.projects[pr.id]=pr
        rec=Receipt('Titulo-1-S1',pr.id,1,self.a.id,self.a.id)
        self.g.receipts[rec.id]=rec
        self.assertTrue(self.g.owns_right(self.a,pr))
        rec.owner=self.b.id
        self.assertFalse(self.g.owns_right(self.a,pr))
        self.assertTrue(self.g.owns_right(self.b,pr))
        self.assertEqual(rec.original,self.a.id)
    def test_transfer_receipt_incompatible_nationality_is_legal_but_cannot_exercise(self):
        self.youth(self.a);self.youth(self.l)
        self.a.pos=self.l.pos=5
        pr=Project('Italia-1','Italia',subhitos=['Italia-1-S1'])
        self.g.projects[pr.id]=pr
        rec=Receipt('Italia-1-S1',pr.id,1,self.a.id,self.a.id)
        self.g.receipts[rec.id]=rec
        self.l.r['M']=4
        self.assertTrue(self.g.transfer_receipt(self.a,self.l,rec.id,price=2))
        self.assertFalse(self.g.owns_right(self.a,pr))
        self.assertTrue(self.g.owns_right(self.l,pr))
        self.assertEqual(rec.original,self.a.id)
        self.assertEqual(self.l.r['M'],2)
        self.assertEqual(self.a.r['M'],2)
        self.assertFalse(self.g.can_fund(self.l,pr))
    def test_market_exhausted_visible_unavailable_not_replenished(self):
        self.g.market.visible['Clarisa'].clear()
        self.assertIsNone(self.g.market.take('Clarisa','visible'))
    def test_duel_retreat_personality_transfers_not_consumes(self):
        self.youth(self.a);self.youth(self.b);self.a.pos=self.b.pos=1
        self.a.r.update(P=1,A=1);self.b.r.update(P=1,A=1)
        self.g.rng_dice=FixedDice(6)
        self.g.withdraw_or_roll=lambda *args:True
        self.assertTrue(self.g.execute_duel(self.a,self.b,'recursos','A',1))
        self.assertEqual(self.a.r['P'],0)
        self.assertEqual(self.b.r['P'],2)
        self.assertEqual(self.a.r['A'],1)
        self.assertEqual(self.b.r['A'],1)
    def test_adjudication_requires_right_and_exact_university(self):
        self.youth(self.a);self.youth(self.b)
        pr=Project('Titulo-1','Titulo',subhitos=['Titulo-1-S1','Titulo-1-S2','Titulo-1-S3'],completed=1)
        self.g.projects[pr.id]=pr
        for i in range(1,4):self.g.receipts[f'Titulo-1-S{i}']=Receipt(f'Titulo-1-S{i}',pr.id,i,self.a.id,self.a.id)
        self.a.r['K']=6;self.b.r['K']=6
        self.a.pos=2;self.g.rng_dice=FixedDice(6)
        self.g.try_adjudicate(self.a);self.assertFalse(self.a.title)
        self.a.pos=1;self.g.try_adjudicate(self.a);self.assertTrue(self.a.title)
        self.assertFalse(self.g.owns_right(self.b,pr))
        self.assertEqual(self.a.r['K'],2) # bot eligió pagar 4 para prueba de 4/6
    def test_earning_from_profile_without_replenishing_resources_after_adjudication(self):
        self.youth(self.a);self.a.title=True;self.a.title_project='X'
        self.g.loss(self.a,'K',10)
        self.assertTrue(self.a.title)
    def test_duel_start_requires_stake_and_retreat_personality(self):
        self.youth(self.a);self.youth(self.b);self.a.pos=self.b.pos=1
        self.a.r.update(K=5,P=0);self.b.r['K']=5
        self.assertFalse(self.g.duel_legal(self.a,self.b,'K',5))
        self.a.r['P']=1;self.assertTrue(self.g.duel_legal(self.a,self.b,'K',5))
        self.a.r['K']=4;self.assertFalse(self.g.duel_legal(self.a,self.b,'K',5))
    def test_duel_failed_transfers_losing_stake(self):
        self.youth(self.a);self.youth(self.b);self.a.pos=self.b.pos=1
        self.a.r.update(K=5,P=1);self.b.r['K']=0
        self.g.rng_dice=FixedDice(6,1);self.g.withdraw_or_roll=lambda *args:False
        pr=Project('Titulo-1','Titulo',subhitos=['Titulo-1-S1'],state='adjudicado',winner=self.b.id)
        self.g.projects[pr.id]=pr
        self.g.receipts['Titulo-1-S1']=Receipt('Titulo-1-S1',pr.id,1,self.a.id,self.a.id)
        self.b.title=True;self.b.title_project=pr.id
        self.assertTrue(self.g.execute_duel(self.a,self.b,'Titulo','K',5))
        self.assertFalse(self.a.title);self.assertEqual(self.a.r['K'],0)
        self.assertEqual(self.b.r['K'],5)
    def test_mercado_dos_pilas_sin_duplicacion(self):
        self.youth(self.a);self.profile(self.a)
        self.a.r={r:20 for r in R}
        n=self.g.market.visible[self.a.role][-1]
        self.a.profile=self.a.profile
        # Explicit operation, regardless of bot preference
        self.g.market.put(self.a.profile,'tapada');self.a.profile=self.g.market.take(self.a.role,'visible')
        self.assertEqual(self.a.profile.uid,n.uid)
        self.assertEqual(len(set([x.uid for r in self.g.market.hidden for x in self.g.market.hidden[r]+self.g.market.visible[r]] + [x.profile.uid for x in self.g.players if x.profile])),32)
    def test_cambio_personaje_pasaporte_se_convierte(self):
        self.youth(self.a);self.profile(self.a)
        self.a.r['P']=10;self.a.passport=True;self.a.passport_kind='Clarisa'
        self.g.change_character(self.a)
        self.assertEqual(self.a.role,'Lucas');self.assertEqual(self.a.passport_kind,'Lucas')
        self.assertEqual(self.a.r['P'],7)
        self.assertEqual(self.a.profile.role,'Lucas')
    def test_house_and_marriage_consume_only_free(self):
        self.youth(self.a);self.youth(self.l)
        self.a.pair=self.l.id;self.l.pair=self.a.id
        self.a.pair_res=self.l.pair_res=5
        self.a.stage=self.l.stage='Adultez';self.a.pos=self.l.pos=4
        for x in (self.a,self.l):
            x.r.update(A=30,P=25,K=8,M=35)
            x.title=True;x.passport=True;x.passport_kind=x.role
            self.profile(x)
        self.g.rng_dice=FixedDice(6,6,1,1)
        self.g.try_house(self.a)
        self.assertEqual(self.g.house_owner,(self.a.id,self.l.id))
        self.assertEqual(self.a.house_a,8);self.assertEqual(self.a.house_p,5)
        self.assertEqual(self.a.r['M'],20)
        self.l.profile=self.g.market.take('Lucas','tapada')
        # set affinity to make a legal married couple
        from dataclasses import replace
        self.l.profile=replace(self.l.profile,affinity=self.a.profile.affinity)
        # Profile uniqueness is temporarily irrelevant within this isolated marriage test.
        self.g.round=5;self.a.pos=self.l.pos=7
        self.g.try_marriage(self.a)
        self.assertTrue(self.g.finished)
        self.assertEqual(self.a.r['M'],15)
        self.assertEqual(self.a.pair_res,5)
        self.assertEqual(self.a.house_a,8)
    def test_change_character_before_utn_without_profile(self):
        self.a.r['P']=3
        self.a.pos=5
        self.g.change_character(self.a)
        self.assertEqual(self.a.role,'Lucas')
        self.assertEqual(self.a.pos,1)
        self.assertIsNone(self.a.profile)
        self.assertEqual(self.a.r['P'],0)
    def test_hito_transfer_retains_investor_rights(self):
        self.youth(self.a);self.youth(self.b);self.a.pos=self.b.pos=1
        pr=Project('Titulo-1','Titulo',subhitos=['Titulo-1-S1'],state='adjudicado',winner=self.a.id)
        self.g.projects[pr.id]=pr
        self.g.receipts['Titulo-1-S1']=Receipt('Titulo-1-S1',pr.id,1,self.a.id,self.a.id)
        self.a.title=True;self.a.title_project=pr.id
        self.assertTrue(self.g.transfer_hito(self.a,self.b,'Titulo'))
        self.assertFalse(self.a.title)
        self.assertTrue(self.b.title)
        self.assertTrue(self.g.owns_right(self.a,pr))
        self.assertEqual(pr.winner,self.b.id)
    def test_trade_resources_no_bank_rate(self):
        self.youth(self.a);self.youth(self.l);self.a.pos=self.l.pos=2
        self.a.r.update(K=4,M=0);self.l.r.update(K=0,M=9)
        self.assertTrue(self.g.trade_resources(self.a,self.l,{'K':1},{'M':4}))
        self.assertEqual((self.a.r['K'],self.a.r['M']),(3,4))
        self.assertEqual((self.l.r['K'],self.l.r['M']),(1,5))
    def test_project_turn_guard_not_only_bot_set(self):
        self.youth(self.a);self.a.r['K']=10
        self.g.funding(self.a,set())
        pr=[x for x in self.g.projects.values() if x.kind=='Titulo'][0]
        self.assertFalse(self.g.can_fund(self.a,pr))
        self.g.turn+=1
        self.assertTrue(self.g.can_fund(self.a,pr))
    def test_small_batch_reproducible_and_invariants(self):
        a=Game(1,505,6,CARDS).run()
        b=Game(1,505,6,CARDS).run()
        self.assertEqual(a.summary(),b.summary())
        self.assertFalse(a.errors)


class IncomeExperimentTests(unittest.TestCase):
    def setUp(self):
        self.g=Game(1,101,6,CARDS,log=True,casilleros_solo_infancia=True)
        self.p=self.g.players[0]
    def test_infancia_still_pays_both_squares(self):
        self.g.square_gain([self.p],'Infancia',2,True)
        self.g.square_gain([self.p],'Infancia',5,True)
        self.assertEqual((self.p.free('A'),self.p.free('P')),(3,2))
    def test_youth_no_square_income_over_pass_or_exact(self):
        before=self.p.r.copy()
        for dest in (1,2,4,5):
            for exact in (True,False):self.g.square_gain([self.p],'Juventud',dest,exact)
        self.assertEqual(self.p.r,before)
    def test_adult_no_square_income_over_pass_or_exact(self):
        before=self.p.r.copy()
        for dest in (1,3):
            for exact in (True,False):self.g.square_gain([self.p],'Adultez',dest,exact)
        self.assertEqual(self.p.r,before)
    def test_original_behavior_reproducible_with_flag(self):
        original=Game(1,101,6,CARDS,casilleros_solo_infancia=False)
        p=original.players[0]
        original.square_gain([p],'Juventud',1,True)
        original.square_gain([p],'Adultez',1,True)
        self.assertEqual((p.r['K'],p.r['M']),(2,6))
    def test_profile_still_produces_when_crossing(self):
        self.p.stage='Juventud';self.p.pos=6
        self.p.profile=self.g.market.take(self.p.role,'tapada')
        expected=dict(zip(R,self.p.profile.production))
        self.g.rng_dice=FixedDice(1)
        self.g.roll_movement(self.p)
        self.assertEqual(self.p.r,expected)
        self.assertEqual(self.g.stats['lap_crossings'],1)
    def test_cards_remain_active_in_youth_and_adult(self):
        for stage in ('Juventud','Adultez'):
            self.p.stage=stage
            before=self.g.stats['cards']
            self.g.card_at(self.p)
            self.assertEqual(self.g.stats['cards'],before+1)
    def test_no_square_generation_in_bulk(self):
        g=Game(1,131028,6,CARDS,casilleros_solo_infancia=True).run()
        self.assertEqual(g.resource_flow.get('square_K',0),0)
        self.assertEqual(g.resource_flow.get('square_M',0),0)
        self.assertGreater(g.resource_flow.get('profile_M',0),0)
        self.assertFalse(g.errors)

if __name__=='__main__':unittest.main(verbosity=2)
