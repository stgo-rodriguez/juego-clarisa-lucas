"""Pruebas de Fase 2: cartas, ronda global y pareja sobre movimiento_v2."""
import random
import unittest
from simulador.movimiento_v2 import Coord, youth_cards
from simulador.turnos_v2 import (AdultChoice, CardPool, PendingRuleError,
    PlayerState, RoundEngine, RuleHooks, SituationCard, Stage)


def make_decks():
    return {
        (s, r): CardPool(
            [SituationCard(f'{s.value}-{r}-{i}', s, r) for i in range(8)],
            random.Random(9), recycle=True)
        for s in (Stage.INFANCIA, Stage.JUVENTUD, Stage.ADULTEZ)
        for r in ('Clarisa', 'Lucas')
    }


def make_game(players, hooks=None):
    return RoundEngine(players, make_decks(),
        CardPool(youth_cards(), random.Random(3), recycle=True),
        CardPool(youth_cards(), random.Random(4), recycle=True),
        hooks=hooks)


class TestFase2(unittest.TestCase):
    def test_infant_turn_before_movement(self):
        log=[]
        g=make_game([PlayerState(1,'Clarisa')],
            RuleHooks(apply_situation=lambda e,p,c,ch:log.append('situation'),
                      on_step=lambda e,p,pos,last:log.append(pos)))
        g.start_round()
        g.play_turn(1,childhood_die=2)
        self.assertEqual(log,['situation',2,3])

    def test_youth_shared_situation_unique_move_card(self):
        applied=[]
        g=make_game([PlayerState(1,'Clarisa',Stage.JUVENTUD,1),
                     PlayerState(2,'Clarisa',Stage.JUVENTUD,1),
                     PlayerState(3,'Lucas',Stage.JUVENTUD,1)],
            RuleHooks(apply_situation=lambda e,p,c,ch:applied.append((p.id,c.id,ch))))
        g.start_round()
        self.assertEqual(sum(e['action']=='situation_revealed' for e in g.events),2)
        self.assertEqual(len({p.youth_movement.id for p in g.players.values()}),3)
        for i in (1,2,3):g.play_turn(i,youth_choice=lambda p,c,m:'B')
        self.assertEqual(applied[0][1],applied[1][1])
        self.assertNotEqual(applied[1][1],applied[2][1])
        self.assertEqual([x[2] for x in applied],['B']*3)

    def test_juvenile_a_b_distance_matches(self):
        g=make_game([PlayerState(1,'Lucas',Stage.JUVENTUD,1)])
        g.start_round()
        card=g.players[1].youth_movement
        out=g.play_turn(1,youth_choice=lambda p,c,m:'A')
        self.assertEqual(out.distance,card.a)
        self.assertEqual(out.choice,'A')

    def test_one_turn_per_player_global_order(self):
        g=make_game([PlayerState(2,'Lucas'),PlayerState(1,'Clarisa')])
        g.start_round()
        with self.assertRaises(ValueError):g.play_turn(1,childhood_die=2)
        g.play_turn(2,childhood_die=2)
        with self.assertRaises(ValueError):g.play_turn(2,childhood_die=2)
        g.play_turn(1,childhood_die=2)
        g.start_round()

    def test_youth_partner_shared_movement_not_cards(self):
        log=[]
        g=make_game([PlayerState(1,'Clarisa',Stage.JUVENTUD,1,partner_id=2),
                     PlayerState(2,'Lucas',Stage.JUVENTUD,1,partner_id=1)],
            RuleHooks(apply_situation=lambda e,p,c,ch:log.append(p.id)))
        g.start_round()
        companion_card=g.players[2].youth_movement
        g.play_turn(1,youth_choice=lambda p,c,m:'A')
        self.assertEqual(log,[1])
        self.assertIs(g.players[2].youth_movement,companion_card)
        self.assertEqual(g.players[1].position,g.players[2].position)

    def test_adult_partner_moves_one_hand(self):
        log=[]
        g=make_game([PlayerState(1,'Clarisa',Stage.ADULTEZ,Coord(5,3),partner_id=2),
                     PlayerState(2,'Lucas',Stage.ADULTEZ,Coord(5,3),partner_id=1)],
            RuleHooks(apply_situation=lambda e,p,c,ch:log.append((p.id,ch))))
        g.start_round()
        g.play_turn(1,adult_choice=lambda p,s,h:AdultChoice(h.cards[0].id,'A','N'))
        self.assertEqual(log,[(1,None)])
        self.assertEqual(len(g.players[1].hand.cards),2)
        self.assertTrue(g.players[2].hand.exhausted)
        self.assertEqual(g.players[1].position,g.players[2].position)

    def test_late_stage_without_card_fails(self):
        g=make_game([PlayerState(1,'Lucas')])
        g.start_round()
        g.players[1].stage=Stage.JUVENTUD
        with self.assertRaises(PendingRuleError):
            g.play_turn(1,youth_choice=lambda p,c,m:'A')

    def test_dublin_and_utn_require_explicit_policy(self):
        for s in (Stage.DUBLIN,Stage.UTN):
            g=make_game([PlayerState(1,'Lucas',s,s.value)])
            g.start_round()
            with self.assertRaises(PendingRuleError):g.play_turn(1)

    def test_marry_exit_requires_gate(self):
        p=PlayerState(1,'Lucas',Stage.ADULTEZ,Coord(1,3),partner_id=2)
        q=PlayerState(2,'Clarisa',Stage.ADULTEZ,Coord(1,3),partner_id=1)
        g=make_game([p,q],RuleHooks(marriage_eligible=lambda e,p:True))
        g.start_round()
        out=g.play_turn(1,adult_choice=lambda p,s,h:
                        AdultChoice(h.cards[0].id,'A',None,exit_after=0))
        self.assertEqual(out.target,'Casamiento')
        self.assertEqual(p.stage,Stage.CASAMIENTO)

    def test_cards_conserved(self):
        p=CardPool(youth_cards(),random.Random(19),recycle=True)
        cards=p.draw(30)
        self.assertEqual(len({c.id for c in cards}),30)
        for c in cards:p.discard(c)
        p.draw(30)
        p.assert_conservation()


if __name__=='__main__':
    unittest.main()
