"""Smoke v2 (sin economía): 6/10 jugadores, Juventud y Adultez."""
from __future__ import annotations
import argparse
import json
import random
from simulador.movimiento_v2 import Coord, MovementCard, youth_cards
from simulador.turnos_v2 import (
    AdultChoice, CardPool, PlayerState, RoundEngine, SituationCard, Stage)


def decks(seed: int):
    result = {}
    for index,(stage,role) in enumerate(
        (s,r) for s in (Stage.INFANCIA,Stage.JUVENTUD,Stage.ADULTEZ)
              for r in ('Clarisa','Lucas')):
        cards=[SituationCard(f'{stage.value}:{role}:{i}',stage,role) for i in range(12)]
        result[(stage,role)]=CardPool(cards,random.Random(seed+index),recycle=True)
    return result


def run_case(n: int, stage: Stage, rounds: int = 2, seed: int = 20261101):
    if n not in (6,10) or stage not in (Stage.JUVENTUD,Stage.ADULTEZ):
        raise ValueError('Solo casos de humo 6/10 en Juventud o Adultez')
    players=[
        PlayerState(i+1,'Clarisa' if i < n//2 else 'Lucas',stage,
                    1 if stage==Stage.JUVENTUD else Coord(5,3))
        for i in range(n)]
    # Cartas sintéticas: NO suponen composición aprobada de Adultez.
    example=[MovementCard(f'TEST-A-{i}',i%6+1,(i+2)%6+1) for i in range(72)]
    game=RoundEngine(players,decks(seed),
        CardPool(youth_cards(),random.Random(seed+10),recycle=True),
        CardPool(example,random.Random(seed+11),recycle=True),hand_size=3)
    for _ in range(rounds):
        game.start_round()
        for player in players:
            if stage==Stage.JUVENTUD:
                game.play_turn(player.id,youth_choice=lambda p,s,c:'A')
            else:
                game.play_turn(player.id,adult_choice=lambda p,s,h:
                    AdultChoice(h.cards[0].id,'A','N' if p.position.row>1 else 'S'))
        game.youth_deck.assert_conservation()
        game.adult_deck.assert_conservation()
        for deck in game.situation_decks.values():deck.assert_conservation()
    count=lambda action:sum(e['action']==action for e in game.events)
    result={'jugadores':n,'etapa':stage.value,'rondas':rounds,
            'turnos':count('movement'),
            'situaciones_resueltas':count('situation_resolved'),
            'situaciones_reveladas':count('situation_revealed'),
            'repartos_juveniles':count('youth_dealt'),
            'renovaciones_mano':count('hand_renewed')}
    assert result['turnos']==n*rounds
    assert result['situaciones_resueltas']==n*rounds
    assert result['situaciones_reveladas']==2*rounds
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--rondas',type=int,default=2)
    args=parser.parse_args()
    if not 1<=args.rondas<=4:raise ValueError('El smoke admite 1..4 rondas')
    results=[run_case(n,stage,args.rondas) for n in (6,10)
             for stage in (Stage.JUVENTUD,Stage.ADULTEZ)]
    print(json.dumps(results,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
