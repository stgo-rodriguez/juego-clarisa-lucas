"""Integración experimental de ingresos por etapa, 6 y 10 jugadores.

No es Monte Carlo de partidas completas. Efectos de Situación neutrales
EXPRESAMENTE, montos de casilleros adultos hipotéticos configurables.
"""
from __future__ import annotations
import argparse
import json
import random
from collections import Counter
from simulador.economia_v2 import EconomyV2, EconomyScenario, RESOURCES
from simulador.movimiento_v2 import Coord, MovementCard, youth_cards
from simulador.turnos_v2 import (AdultChoice, CardPool, PlayerState,
                                 RoundEngine, SituationCard, Stage)


def run(stage: Stage, n: int, rounds: int=4, seed: int=7026):
    pos = 1 if stage==Stage.JUVENTUD else Coord(5,3)
    ps=[PlayerState(i+1,'Clarisa' if i<n//2 else 'Lucas',stage,pos) for i in range(n)]
    scenario=EconomyScenario(adult_square_amounts={'A':2,'P':2,'K':2,'M':2},neutral_situations=True)
    economy=EconomyV2(ps,scenario=scenario)
    for i in range(1,n+1):economy.set_profile(i,(i-1)%4)
    situ={(s,role):CardPool([SituationCard(f'{s.value}-{role}-{j}',s,role) for j in range(15)],
                           random.Random(seed+9*j0),recycle=True)
          for j0,(s,role) in enumerate((s,role) for s in (Stage.INFANCIA,Stage.JUVENTUD,Stage.ADULTEZ)
                                      for role in ('Clarisa','Lucas'))}
    adult=[MovementCard(f'EXPERIMENTAL-{i}',i%6+1,(i+2)%6+1) for i in range(120)]
    engine=RoundEngine(ps,situ,CardPool(youth_cards(),random.Random(seed+25),recycle=True),
                       CardPool(adult,random.Random(seed+26),recycle=True),hooks=economy.hooks())
    for _ in range(rounds):
        engine.start_round()
        for p in ps:
            if stage==Stage.JUVENTUD:
                engine.play_turn(p.id,youth_choice=lambda player,card,m:'A')
            else:
                engine.play_turn(p.id,adult_choice=lambda player,card,hand:
                    AdultChoice(hand.cards[0].id,'A','N' if player.position.row>1 else 'S'))
        economy.audit()
    for pool in [engine.youth_deck,engine.adult_deck,*engine.situation_decks.values()]:pool.assert_conservation()
    result={'stage':stage.value,'players':n,'rounds':rounds,'turns':len([e for e in engine.events if e['action']=='movement']),
            'situations_resolved':len([e for e in engine.events if e['action']=='situation_resolved']),
            'resources_issued':dict(economy.issued),'resources_burned':dict(economy.burned),
            'profile_activations':len([e for e in economy.events if e['action']=='issue' and
                           e.get('source')=='vuelta_juventud']),
            'experimental_assumptions':['Situaciones neutras','Ingresos casilleros adultos=2 por recurso',
                                        'Cartas adultas sintéticas','Bots geométricos no estratégicos']}
    return result


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--rondas',type=int,default=4)
    a=ap.parse_args()
    if not 1<=a.rondas<=10:raise ValueError('Rondas permitidas 1..10')
    print(json.dumps([run(stage,n,a.rondas) for stage in (Stage.JUVENTUD,Stage.ADULTEZ) for n in (6,10)],
                     indent=2,ensure_ascii=False))


if __name__=='__main__':main()