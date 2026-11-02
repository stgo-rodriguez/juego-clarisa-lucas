"""Fase 8: escenarios contrafactuales y reglas de conservación."""
from __future__ import annotations

import unittest

from laboratorio.sensibilidad_v2 import (
    SCENARIOS, StressScenario, paired_differences, run_game, summarize,
    synthetic_decks, thin, compare,
)
from laboratorio.experimento_competencia_v2 import run_game as original_v7
from simulador.interacciones_v2 import AuctionCard
from simulador.turnos_v2 import Stage


class TestStressV2(unittest.TestCase):
    def test_scenarios_explicitly_distinct(self):
        self.assertEqual(len({s.id for s in SCENARIOS}),len(SCENARIOS))
        self.assertEqual(SCENARIOS[0].situation_yield,1)
        self.assertEqual(SCENARIOS[0].profile_yield,1)
        self.assertEqual(SCENARIOS[0].adult_square_amount,2)
        self.assertTrue(any(s.extra_loss for s in SCENARIOS))

    def test_invalid_parameters_rejected(self):
        for args in ({'id':'bad','situation_yield':0},
                     {'id':'bad','situation_yield':1.2},
                     {'id':'bad','situation_yield':1,'loss_fraction':1.2},
                     {'id':'bad','situation_yield':1,'extra_loss':-1},
                     {'id':'bad','situation_yield':1,'adult_square_amount':-1},
                     {'id':'bad','situation_yield':1,'profile_yield':0}):
            with self.assertRaises(ValueError):StressScenario(**args)

    def test_thin_is_deterministic_and_monotone(self):
        for number in range(1,10):
            p=[thin(number,f,'partida',number) for f in (1,.9,.8,.6,.25)]
            self.assertEqual(p[0],number)
            self.assertTrue(all(p[i]>=p[i+1] for i in range(len(p)-1)))
            self.assertTrue(all(x==p[i] for i,x in enumerate(
                [thin(number,f,'partida',number) for f in (1,.9,.8,.6,.25)])))
        self.assertEqual(thin(0,.9,'x'),0)
        with self.assertRaises(ValueError):thin(-1,.9,'x')

    def test_decks_have_same_identity_and_randomized_order(self):
        prev=None
        for scenario in SCENARIOS:
            decks,losses=synthetic_decks(112,scenario)
            self.assertEqual(len(decks),6)
            identity={key:[card.id for card in pile._deck] for key,pile in decks.items()}
            if prev is not None:self.assertEqual(identity,prev)
            else:prev=identity
            for pile in decks.values():pile.assert_conservation()
            self.assertEqual(sum(isinstance(c.payload,AuctionCard)
                for pile in decks.values() for c in pile._deck),24)
            if scenario.extra_loss==0:self.assertFalse(losses)

    def test_auction_floors_and_conservation_at_extreme(self):
        extreme=next(s for s in SCENARIOS if 'extremo' in s.id)
        decks,_=synthetic_decks(112,extreme)
        for (_, _),pile in decks.items():
            for card in pile._deck:
                if isinstance(card.payload,AuctionCard):
                    self.assertGreaterEqual(card.payload.total,1)
                    self.assertGreaterEqual(card.payload.appropriable,1)
                    self.assertLessEqual(card.payload.appropriable,card.payload.total)

    def test_replay_is_identical(self):
        a=run_game(6,2,'planificador',True,SCENARIOS[-2],rounds=80)
        b=run_game(6,2,'planificador',True,SCENARIOS[-2],rounds=80)
        self.assertEqual(a,b)
        self.assertTrue(a['synthetic_scenarios'])
        self.assertLessEqual(a['turns_without_durable_progress'],a['turns_executed'])
        self.assertEqual(a['duels'],a['duels_hito']+a['duels_perfil']+a['duels_ordinarios'])

    def test_base_reproduces_phase7(self):
        for competition in (False,True):
            original=original_v7(6,4,'planificador',competition,max_rounds=80)
            current=run_game(6,4,'planificador',competition,SCENARIOS[0],rounds=80)
            for key in ('rounds','won','duels','bids','auctions','house_transfers'):
                self.assertEqual(original[key],current[key],key)

    def test_no_competition_no_paid_bids_or_duels(self):
        r=run_game(6,1,'aleatorio',False,SCENARIOS[3],rounds=60)
        self.assertEqual(r['duels'],0)
        self.assertEqual(r['bids'],0)
        self.assertGreaterEqual(r['free_resources_lost'],0)

    def test_capped_games_do_not_count_as_wins(self):
        r=run_game(6,1,'planificador',False,SCENARIOS[-1],rounds=1)
        self.assertFalse(r['won'])
        self.assertEqual(r['rounds'],1)
        self.assertEqual(r['stop'],'round_limit')
        self.assertEqual(summarize([r])[0]['casamientos'],0)
        self.assertIsNone(summarize([r])[0]['rondas_mediana_victorias'])

    def test_pairing_and_summaries_per_seed(self):
        samples=compare(1,rounds=40,policies=('planificador',),competitions=(False,))
        self.assertEqual(len(samples),2*len(SCENARIOS))
        summaries=summarize(samples)
        self.assertEqual(len(summaries),2*len(SCENARIOS))
        effects=paired_differences(samples)
        self.assertEqual(len(effects),2*(len(SCENARIOS)-1))
        self.assertTrue(all(x['pares']==1 for x in effects))
        self.assertTrue(all(x['partidas']==1 for x in summaries))

    def test_missing_baseline_pair_rejected(self):
        row=run_game(6,1,'planificador',False,SCENARIOS[1],rounds=15)
        with self.assertRaises(ValueError):paired_differences([row])


if __name__=='__main__':
    unittest.main()

class TestBotLegalMarket(unittest.TestCase):
    def test_no_hidden_no_visible_no_change(self):
        import random
        from simulador.agentes_v2 import AgentConfig, GameAgent
        from simulador.economia_v2 import EconomyScenario, EconomyV2
        from simulador.movimiento_v2 import youth_cards
        from simulador.transiciones_v2 import ProfileDecksV2
        from simulador.turnos_v2 import CardPool, PlayerState, RoundEngine, Stage
        from laboratorio.experimento_agentes_v2 import create_situations
        players = [PlayerState(i+1,'Lucas',Stage.JUVENTUD,1) for i in range(16)]
        mate = PlayerState(17,'Clarisa',Stage.JUVENTUD,1)
        players.append(mate)
        eco=EconomyV2(players,scenario=EconomyScenario(neutral_situations=True))
        profiles=ProfileDecksV2(13)
        for p in players:profiles.award_utn(eco,p)
        self.assertEqual(profiles.decks['Lucas'].available,0)
        self.assertIsNone(profiles.top_visible('Lucas'))
        actor=players[0]
        actor.partner_id=mate.id
        mate.partner_id=actor.id
        eco.accounts[mate.id].affinity=(eco.accounts[actor.id].affinity+1)%4
        for r in 'APKM':eco.issue(actor.id,r,20,'test')
        engine=RoundEngine(players,create_situations(4),
            CardPool(youth_cards(),random.Random(2),recycle=True))
        engine.round_no=3
        agent=GameAgent(engine,eco,AgentConfig('planificador'),9,profiles)
        current=profiles.active[actor.id]
        agent._change_affinity(actor)
        self.assertEqual(profiles.active[actor.id],current)
        self.assertEqual(eco.accounts[actor.id].free['A'],20)
        self.assertTrue(profiles.audit() and eco.audit())

    def test_hidden_empty_uses_visible_fallback(self):
        import random
        from simulador.agentes_v2 import AgentConfig, GameAgent
        from simulador.economia_v2 import EconomyScenario, EconomyV2
        from simulador.movimiento_v2 import youth_cards
        from simulador.transiciones_v2 import ProfileDecksV2
        from simulador.turnos_v2 import CardPool, PlayerState, RoundEngine, Stage
        from laboratorio.experimento_agentes_v2 import create_situations
        players=[PlayerState(i+1,'Lucas',Stage.JUVENTUD,1) for i in range(15)]
        mate=PlayerState(16,'Clarisa',Stage.JUVENTUD,1)
        players.append(mate)
        eco=EconomyV2(players,scenario=EconomyScenario(neutral_situations=True))
        profiles=ProfileDecksV2(14)
        for p in players:profiles.award_utn(eco,p)
        actor=players[0]
        actor.partner_id=mate.id
        mate.partner_id=actor.id
        for r in 'APKM':eco.issue(actor.id,r,30,'test')
        profiles.change(eco,actor,1,take='hidden',discard='visible')
        self.assertEqual(profiles.decks['Lucas'].available,0)
        visible=profiles.top_visible('Lucas')
        options=set(range(4))-{visible.affinity,profiles.active[actor.id].affinity}
        self.assertTrue(options)
        eco.accounts[mate.id].affinity=min(options)
        engine=RoundEngine(players,create_situations(4),
            CardPool(youth_cards(),random.Random(3),recycle=True))
        engine.round_no=2
        agent=GameAgent(engine,eco,AgentConfig('planificador'),9,profiles)
        agent._change_affinity(actor)
        self.assertEqual(profiles.active[actor.id],visible)
        self.assertTrue(profiles.audit() and eco.audit())
