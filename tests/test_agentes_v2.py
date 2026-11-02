"""Pruebas Fase 5: agentes legales, perfiles y partida sintética reproducible."""
import random
import unittest
from simulador.agentes_v2 import AgentConfig
from simulador.economia_v2 import EconomyV2, EconomyScenario
from simulador.movimiento_v2 import Coord, youth_cards
from simulador.transiciones_v2 import ProfileDecksV2
from simulador.turnos_v2 import CardPool, PlayerState, RoundEngine, SituationCard, Stage
from laboratorio.experimento_agentes_v2 import adult_cards, create_situations, run_game, summary


class TestMarket(unittest.TestCase):
    def setUp(self):
        self.p = PlayerState(1,'Lucas',Stage.JUVENTUD,1)
        self.eco=EconomyV2([self.p],scenario=EconomyScenario(neutral_situations=True))
        self.profiles=ProfileDecksV2(seed=7)
        self.profiles.award_utn(self.eco,self.p)
        for r in ('A','P','K','M'):self.eco.issue(1,r,12,'test')

    def test_hidden_visible_change_and_cost(self):
        previous=self.profiles.active[1]
        actual=self.profiles.change(self.eco,self.p,1,take='hidden',discard='visible')
        self.assertNotEqual(previous.id,actual.id)
        self.assertEqual(self.profiles.top_visible('Lucas'),previous)
        self.assertTrue(all(self.eco.accounts[1].free[r]==9 for r in ('A','P','K','M')))
        self.assertEqual(self.eco.accounts[1].affinity,actual.affinity)
        with self.assertRaises(ValueError):self.profiles.change(self.eco,self.p,1)
        from_visible=self.profiles.change(self.eco,self.p,2,take='visible',discard='hidden')
        self.assertEqual(from_visible,previous)
        self.assertIsNone(self.profiles.top_visible('Lucas'))
        self.assertTrue(self.profiles.audit() and self.eco.audit())

    def test_exclusive_market_and_no_unpaid_change(self):
        with self.assertRaises(ValueError):self.profiles.change(self.eco,self.p,1,take='visible')
        p2=PlayerState(2,'Lucas',Stage.JUVENTUD,1)
        self.eco._players[2]=p2
        self.eco.accounts[2]=type(self.eco.accounts[1])()
        self.profiles.award_utn(self.eco,p2)
        with self.assertRaises(ValueError):self.profiles.change(self.eco,p2,1)
        self.assertTrue(self.profiles.audit())

    def test_returned_to_hidden_bottom(self):
        old=self.profiles.active[1]
        self.profiles.change(self.eco,self.p,1,take='hidden',discard='hidden')
        self.assertIsNone(self.profiles.top_visible('Lucas'))
        self.assertNotEqual(self.profiles.active[1],old)
        self.assertTrue(self.profiles.audit())


class TestSyntheticGames(unittest.TestCase):
    def test_six_situation_decks_distinct(self):
        decks=create_situations(5)
        self.assertEqual(len(decks),6)
        for (stage,role),deck in decks.items():
            self.assertEqual(deck.available,20)
            deck.assert_conservation()
        self.assertEqual(len(adult_cards()),120)

    def test_rng_dice_is_created_and_active(self):
        p=PlayerState(1,'Clarisa')
        eco=EconomyV2([p],scenario=EconomyScenario(neutral_situations=True))
        situations=create_situations(1)
        engine=RoundEngine([p],situations,CardPool(youth_cards(),random.Random(1)),
                           rng_dice=random.Random(4),hooks=eco.hooks())
        self.assertIsInstance(engine.rng_dice.randint(1,6),int)
        engine.start_round()
        result=engine.play_turn(1,choose_utn=False)
        self.assertIn(result.distance,range(1,7))
        self.assertEqual(len([e for e in engine.events if e['action']=='movement']),1)

    def test_replay_fixed_seed(self):
        x=run_game(6,2,'planificador',max_rounds=50)
        y=run_game(6,2,'planificador',max_rounds=50)
        self.assertEqual(x,y)
        self.assertTrue(x['synthetic_cards'])
        self.assertGreater(x['investments'],0)
        self.assertGreater(x['utn_passes'],0)

    def test_both_agent_types_and_hand_variants(self):
        rows=[run_game(n,3,policy,max_rounds=35,hand_size=hand)
              for n in (6,10) for policy in ('aleatorio','planificador') for hand in (3,4)]
        self.assertEqual(len(rows),8)
        self.assertTrue(all(row['rounds']<=35 for row in rows))
        self.assertTrue(all(row['utn_passes']>0 for row in rows))
        self.assertTrue(all(row['turns']>0 for row in rows))
        self.assertEqual(len(summary(rows)),4)

    def test_no_unapproved_social_outcomes(self):
        x=run_game(6,4,'aleatorio',max_rounds=35,with_events=True)
        events=x['economy_log']
        self.assertTrue(any(e['action']=='situation_synthetic_experimental' for e in events))
        self.assertFalse(any(e['action'] in ('auction','social_intervention') for e in events))


if __name__=='__main__':unittest.main()