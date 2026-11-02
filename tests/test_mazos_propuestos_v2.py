"""Pruebas Fase 10 con catálogo documental completo (no aprobado)."""
import copy
import random
import unittest
from collections import Counter
from simulador.movimiento_v2 import Coord
from simulador.turnos_v2 import PlayerState, RoundEngine, SituationCard, Stage, CardPool
from simulador.economia_v2 import EconomyV2, EconomyScenario
from simulador.mazos_propuestos_v2 import load_catalog, build_decks, ProposedResolver
from laboratorio.experimento_mazos_propuestos_v2 import run_proposal
from laboratorio.experimento_agentes_v2 import adult_cards
from simulador.movimiento_v2 import youth_cards
from simulador.interacciones_v2 import SocialAuctionsV2, Bid


class TestDocumentedDecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog=load_catalog()

    def test_source_integrity(self):
        self.assertEqual(len(self.catalog['historical_78']),78)
        self.assertEqual(len(self.catalog['adult_proposals_30']),30)
        self.assertTrue(all(c['approval']=='PROPUESTA_NO_APROBADA' for c in self.catalog['adult_proposals_30']))
        self.assertEqual(Counter(c['mechanics']['type'] for c in self.catalog['adult_proposals_30']),
                         Counter({'choice':6,'choice_target':10,'coop':6,'auction':8}))

    def test_six_decks_and_duplicates_are_explicit(self):
        decks=build_decks(self.catalog,11)
        self.assertEqual({(stage.value,role):len(d._deck) for (stage,role),d in decks.items()},
             {(stage,role): (15 if stage=='Adultez' else 24) for stage in
              ('Infancia','Juventud','Adultez') for role in ('Clarisa','Lucas')})
        for d in decks.values():d.assert_conservation()
        self.assertEqual(sum(len(d._deck) for d in decks.values()),126)
        self.assertFalse(any(c.payload.get('origin')=='adult_proposal' for (s,r),d in decks.items()
                             if s!=Stage.ADULTEZ for c in d._deck))

    def test_seeded_shuffle_and_no_future_peeking(self):
        def deal(seed):
            decks=build_decks(self.catalog,seed)
            return [[c.id for c in d.draw(3)] for d in decks.values()]
        self.assertEqual(deal(123),deal(123))
        self.assertNotEqual(deal(123),deal(124))

    def test_exact_juvenile_letter(self):
        p=PlayerState(1,'Clarisa',Stage.JUVENTUD,1)
        eco=EconomyV2([p],scenario=EconomyScenario(neutral_situations=False))
        resolver=ProposedResolver(eco)
        card=SituationCard('J-C-J01',Stage.JUVENTUD,'Clarisa',
              {'origin':'historical_copy','effects':{'A':{'K':3,'A':-5},'B':{'P':2}}})
        with self.assertRaises(ValueError):resolver.resolve(self._engine([p],eco),p,card,None)
        resolver.resolve(self._engine([p],eco),p,card,'B')
        self.assertEqual(eco.accounts[p.id].free['P'],2)
        self.assertEqual(eco.accounts[p.id].free['K'],0)
        eco.audit()

    def test_historical_losses_only_free(self):
        p=PlayerState(1,'Clarisa',Stage.INFANCIA,2)
        eco=EconomyV2([p],scenario=EconomyScenario(neutral_situations=False))
        eco.issue(1,'P',1,'fixture')
        resolver=ProposedResolver(eco,policy='planificador')
        card=SituationCard('I-C-I01',Stage.INFANCIA,'Clarisa',
              {'origin':'historical_copy','effects':{'A':{'K':1,'P':-50},'B':{'A':2,'P':-20}}})
        resolver.resolve(self._engine([p],eco),p,card,None)
        self.assertEqual(eco.accounts[1].free['P'],0)
        self.assertTrue(eco.audit())

    def test_conflict_no_target_fallback(self):
        p=PlayerState(1,'Clarisa',Stage.ADULTEZ,Coord(5,3))
        eco=EconomyV2([p])
        engine=self._engine([p],eco)
        card=self._adult('AD-C-04')
        ProposedResolver(eco).resolve(engine,p,card,None)
        self.assertEqual(eco.accounts[1].free['M'],2)
        self.assertTrue(eco.audit())

    def test_conflict_losses_do_not_touch_reserves(self):
        p=PlayerState(1,'Clarisa',Stage.ADULTEZ,Coord(5,3))
        q=PlayerState(2,'Clarisa',Stage.JUVENTUD,1)
        eco=EconomyV2([p,q]);engine=self._engine([p,q],eco)
        eco.issue(1,'M',4,'fixture');eco.issue(2,'P',1,'fixture')
        ProposedResolver(eco,policy='aleatorio',rng=random.Random(0)).resolve(engine,p,self._adult('AD-C-07'),None)
        self.assertEqual(eco.accounts[2].free['P'],0)
        self.assertEqual(eco.accounts[1].free['M'],2)
        self.assertTrue(eco.audit())

    def test_coop_costs_both_and_issues_both(self):
        p=PlayerState(1,'Clarisa',Stage.ADULTEZ,Coord(5,3))
        q=PlayerState(2,'Clarisa',Stage.JUVENTUD,1)
        eco=EconomyV2([p,q]);engine=self._engine([p,q],eco)
        eco.issue(1,'P',1,'fixture');eco.issue(2,'P',1,'fixture')
        r=ProposedResolver(eco)
        r.resolve(engine,p,self._adult('AD-C-10'),None)
        self.assertEqual(r.events[-1]['result'],'coop_accepted')
        self.assertEqual(eco.accounts[1].free['M'],2)
        self.assertEqual(eco.accounts[2].free['M'],2)
        self.assertEqual(eco.burned['P'],2)
        self.assertTrue(eco.audit())

    def test_auction_card_one_round_bid_to_active(self):
        p=PlayerState(1,'Clarisa',Stage.ADULTEZ,Coord(5,3))
        q=PlayerState(2,'Clarisa',Stage.JUVENTUD,1)
        r=PlayerState(3,'Lucas',Stage.JUVENTUD,1)
        eco=EconomyV2([p,q,r]);engine=self._engine([p,q,r],eco)
        eco.issue(2,'P',2,'fixture');eco.issue(3,'P',3,'fixture')
        auctions=SocialAuctionsV2(eco,engine)
        class Controlled:
            def resolve_social_situation(self,e,active,card,ordinary,letter):
                self.card=card.payload
                self.result=auctions.run(active.id,card.payload,
                    bid_order=(2,),bid_for=lambda player,high:Bid(player.id,'P',1),
                    select_winner=lambda candidates:candidates[0].player_id)
        stub=Controlled()
        ProposedResolver(eco,competition_controller=stub).resolve(engine,p,self._adult('AD-C-12'),None)
        self.assertEqual(stub.card.eligible_roles,('Clarisa',))
        self.assertEqual((stub.result.credited_active,stub.result.credited_winner),(2,4))
        self.assertEqual(eco.accounts[1].free['P'],1)
        self.assertEqual(eco.accounts[2].free['P'],1)
        self.assertEqual(eco.accounts[1].free['M'],2)
        self.assertEqual(eco.accounts[2].free['M'],4)
        eco.audit()

    def test_zero_bid_full_reward(self):
        p=PlayerState(1,'Clarisa',Stage.ADULTEZ,Coord(5,3))
        eco=EconomyV2([p]);engine=self._engine([p],eco)
        auctions=SocialAuctionsV2(eco,engine)
        class Nobody:
            def resolve_social_situation(self,e,active,card,ordinary,letter):
                auctions.run(active.id,card.payload,bid_order=(),
                    bid_for=lambda pl,high:None,select_winner=lambda b:None)
        ProposedResolver(eco,competition_controller=Nobody()).resolve(engine,p,self._adult('AD-C-13'),None)
        self.assertEqual(eco.accounts[1].free['A'],6)

    def test_baseline_game_with_documented_cards(self):
        for n in (6,10):
            r=run_proposal(n,1,'planificador',False,catalog=self.catalog,rounds=70)
            self.assertTrue(r['won'])
            self.assertGreater(r['situations_resolved'],0)
            self.assertEqual(r['duels'],0)

    def test_competition_runs_with_actual_social_cards(self):
        for n in (6,10):
            result=run_proposal(n,3,'planificador',True,catalog=self.catalog,rounds=75)
            self.assertTrue(result['won'])
            self.assertGreater(result['social_auctions'],0)
            self.assertGreater(result['bids'],0)
            self.assertGreater(result['duels'],0)

    def _adult(self,card_id):
        row=next(x for x in self.catalog['adult_proposals_30'] if x['id']==card_id)
        return SituationCard(row['id'],Stage.ADULTEZ,row['role'],{'origin':'adult_proposal',**row})

    @staticmethod
    def _engine(players,eco):
        # Cards remain inaccessible; only explicit social interfaces are tested.
        return RoundEngine(players,{(s,r):CardPool([SituationCard(f'{s}-{r}',s,r)],random.Random(1))
                     for s in (Stage.INFANCIA,Stage.JUVENTUD,Stage.ADULTEZ)
                     for r in ('Clarisa','Lucas')},
                     CardPool(youth_cards(),random.Random(2)),
                     CardPool(adult_cards(),random.Random(3)))

if __name__=='__main__':unittest.main()