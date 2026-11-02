"""Auditoría reproducible Fase 4: tres etapas con fixtures económicos EXPLÍCITOS.

No predice partidas: debido a que los seis mazos de Situación siguen sin
aprobarse, se utiliza un escenario neutral experimental y se entregan K
inicial, título, pasaporte y recursos de entrada de forma explícita.
Se mantienen reales los movimientos, las bifurcaciones, dados, Perfil,
reparto, mano de pareja, acceso a Dublín y cobro de entrada a Adultez.
"""
from __future__ import annotations
import argparse
import json
import random
from simulador.movimiento_v2 import Coord, MovementCard, youth_cards
from simulador.turnos_v2 import CardPool, PlayerState, RoundEngine, SituationCard, Stage,AdultChoice
from simulador.economia_v2 import EconomyV2, EconomyScenario
from simulador.transiciones_v2 import ProfileDecksV2, transition_hooks


def run_case(n: int,seed: int=42,max_rounds: int=15, dublin_policy: str = 'next_round'):
    if n not in (6,10):raise ValueError('Se requieren 6 o 10 jugadores')
    players=[PlayerState(i+1,'Clarisa' if i<n//2 else 'Lucas',Stage.INFANCIA,4)
             for i in range(n)]
    eco=EconomyV2(players,scenario=EconomyScenario(
        adult_square_amounts={'A':1,'P':1,'K':1,'M':1},neutral_situations=True))
    profiles=ProfileDecksV2(seed)
    situations={
        (stage,role):CardPool(
            [SituationCard(f'{stage.value}-{role}-{i}',stage,role) for i in range(20)],
            random.Random(seed+j),recycle=True)
        for j,(stage,role) in enumerate((s,r) for s in (Stage.INFANCIA,Stage.JUVENTUD,Stage.ADULTEZ)
            for r in ('Clarisa','Lucas'))
    }
    # Esta composición adulta también es sintética: no se la considera regla oficial.
    adult=[MovementCard(f'AD-{i}',i%6+1,(i+2)%6+1) for i in range(110)]
    engine=RoundEngine(players,situations,
        CardPool(youth_cards(),random.Random(seed+20),recycle=True),
        CardPool(adult,random.Random(seed+30),recycle=True),
        hooks=transition_hooks(eco,profiles),dublin_policy=dublin_policy)
    for p in players:eco.issue(p.id,'K',1,'fixture_conocimiento_para_utn')
    engine.start_round()
    for p in players:
        result=engine.play_turn(p.id,childhood_die=1,utn_die=6,choose_utn=True)
        assert result.target==Stage.UTN.value
        assert p.utn_passed
    assert len(profiles.active)==n
    # Se abren Juventud, sus dos Situaciones por rol y sus cartas personales.
    engine.start_round()
    a,b=players[0],players[n//2]
    for p in (a,b):
        ac=eco.accounts[p.id]
        # Los hitos son fixtures; su obtención futura se simulará con proyectos.
        ac.title=True
        ac.passport='Italia' if p.role=='Clarisa' else 'Polonia'
        for resource,quantity in {'A':5,'K':5,'M':5}.items():
            eco.issue(p.id,resource,quantity,'fixture_hitos_y_entrada')
    assert (a.position,b.position)==(1,1)
    assert eco.form_pair(a,b)
    eco.audit()

    def smart_youth(p,card,movement):
        if p.partner_id is not None:
            for letter in ('A','B'):
                distance=movement.distance(letter)
                if (p.position-1+distance)%6+1 in (2,5):return letter
        return 'A'

    entered_at=None
    adult_turns=0
    for round_number in range(2,max_rounds+1):
        if round_number>2:engine.start_round()
        for p in players:
            if p.stage==Stage.JUVENTUD:
                out=engine.play_turn(p.id,youth_choice=smart_youth,
                                     choose_dublin=p.partner_id is not None)
            elif p.stage==Stage.DUBLIN:
                out=engine.play_turn(p.id,adult_choice=lambda p,s,h:AdultChoice(
                    h.cards[0].id,'A','N' if p.position.row>1 else 'S'))
                if p.stage==Stage.ADULTEZ and p.id in (a.id,b.id):adult_turns+=1
            elif p.stage==Stage.ADULTEZ:
                out=engine.play_turn(p.id,adult_choice=lambda p,s,h:AdultChoice(
                    h.cards[0].id,'A','N' if p.position.row>1 else 'S'))
                if p.id in (a.id,b.id):adult_turns+=1
            else:
                raise AssertionError(f'Etapa inesperada: {p.stage}')
            if out.target==Stage.DUBLIN.value and entered_at is None:
                entered_at=round_number
        engine.youth_deck.assert_conservation()
        engine.adult_deck.assert_conservation()
        for d in engine.situation_decks.values():d.assert_conservation()
        profiles.audit();eco.audit()
        if adult_turns>=2:break
    assert entered_at is not None
    assert a.stage==b.stage==Stage.ADULTEZ
    assert adult_turns>=2
    categories={stage.value:sum(p.stage==stage for p in players) for stage in Stage}
    count=lambda action:sum(e['action']==action for e in engine.events)
    result={
        'players':n,'seed':seed,'dublin_policy_experimental':dublin_policy,
        'rounds_until_first_adult_pair_turns':engine.round_no,
        'dublin_entry_round':entered_at,
        'profiles_awarded':len(profiles.active),
        'utn_passes':sum(e['action']=='utn_exam' and e['passed'] for e in engine.events),
        'dublin_transitions':count('dublin_to_adult'),
        'dublin_wait_turns_experimental':count('dublin_wait_experimental'),
        'adult_hand_renewals':count('hand_renewed'),
        'round_movements':count('movement'),
        'stages':categories,
        'fixture_note':'K inicial, título/pasaporte y fondos extra: INYECCIÓN DE PRUEBA. No es Monte Carlo ni balance.'
    }
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--seed',type=int,default=42)
    parser.add_argument('--dublin-policy',choices=('next_round','next_turn','both'),default='both')
    opts=parser.parse_args()
    policies=('next_round','next_turn') if opts.dublin_policy=='both' else (opts.dublin_policy,)
    print(json.dumps([run_case(n,opts.seed,dublin_policy=policy) for n in (6,10)
                      for policy in policies],indent=2,ensure_ascii=False))


if __name__=='__main__':main()