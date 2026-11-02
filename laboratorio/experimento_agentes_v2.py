"""Experimento de políticas v2.x con seis mazos SINTÉTICOS, NO aprobados.

No es una simulación de balance del juego definitivo. Es una prueba
reproducible de mecánicas integradas desde cero: UTN, inversiones,
adjudicación, pareja, Dublín, movimiento con mano, Casa y Casamiento.
"""
from __future__ import annotations
import argparse
import csv
import json
import random
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from simulador.agentes_v2 import AgentConfig, GameAgent
from simulador.economia_v2 import EconomyV2, EconomyScenario, PASSPORT_KIND
from simulador.movimiento_v2 import MovementCard, youth_cards
from simulador.transiciones_v2 import ProfileDecksV2, transition_hooks
from simulador.turnos_v2 import CardPool, PlayerState, RoundEngine, SituationCard, Stage


def effect(stage: Stage, i: int):
    if stage==Stage.INFANCIA:
        return {'base':({'K':1},{'A':2},{'P':2},{'K':1,'M':1},{'A':1,'P':1})[i%5]}
    if stage==Stage.JUVENTUD:
        variant=i%5
        return {'A':({'K':3},{'A':3},{'P':3},{'M':3},{'K':2,'P':1})[variant],
                'B':({'M':3},{'P':3},{'K':3},{'A':3},{'M':2,'A':1})[variant]}
    return {'base':({'A':4,'P':1},{'M':4,'P':1},{'P':4,'A':1},
                    {'K':3,'M':2},{'A':2,'M':3})[i%5]}


def create_situations(seed:int)->dict:
    situation={}
    for k,(stage,role) in enumerate((s,r) for s in (Stage.INFANCIA,Stage.JUVENTUD,Stage.ADULTEZ)
                 for r in ('Clarisa','Lucas')):
        cards=[SituationCard(f'SYN-{stage.value}-{role}-{i}',stage,role,effect(stage,i))
               for i in range(20)]
        situation[(stage,role)]=CardPool(cards,random.Random(seed+13*k),recycle=True)
    return situation


def adult_cards()->tuple[MovementCard,...]:
    # Mazo exclusivamente experimental: cada par A!=B repetido cuatro veces,
    # se entrega barajado y nunca se modifica por el comportamiento del bot.
    return tuple(MovementCard(f'SYN-A-{i}-{a}-{b}',a,b)
                 for i in range(4) for a in range(1,7) for b in range(1,7) if a!=b)


def run_game(n:int,seed:int,policy:str,max_rounds:int=120,hand_size:int=3,
             dublin_policy:str='next_turn',with_events:bool=False)->dict:
    if n not in (6,10):raise ValueError('Experimentar únicamente con 6 o 10')
    if max_rounds<1:raise ValueError('max_rounds debe ser positivo')
    if dublin_policy not in ('next_turn','next_round'):raise ValueError('Política Dublín inválida')
    players=[PlayerState(i+1,'Clarisa' if i<n//2 else 'Lucas') for i in range(n)]
    eco=EconomyV2(players,scenario=EconomyScenario(
        adult_square_amounts={'A':2,'P':2,'K':2,'M':2},neutral_situations=False),
        rng=random.Random(seed*97+14))
    profiles=ProfileDecksV2(seed*23+14)
    hooks=transition_hooks(eco,profiles)

    def synthetic_situation(engine,p,card,letter):
        # La forma base/A/B está contenida en el mazo visible. No se consultan
        # cartas ocultas del futuro. La economía NO tiene fichas hipotéticas
        # fuera de este modo experimental.
        key=letter if p.stage==Stage.JUVENTUD else 'base'
        delta=card.payload[key]
        for resource,amount in delta.items():
            if amount>=0:eco.issue(p.id,resource,amount,'situacion_sintetica_experimental')
            else:eco.spend(p.id,resource,min(-amount,eco.accounts[p.id].free[resource]),'situacion_sintetica_experimental')
        eco.events.append({'action':'situation_synthetic_experimental',
                           'player':p.id,'card':card.id,'choice':letter})
    hooks.apply_situation=synthetic_situation
    engine=RoundEngine(players,create_situations(seed*37),
        CardPool(youth_cards(),random.Random(seed*97+44),recycle=True),
        CardPool(adult_cards(),random.Random(seed*97+45),recycle=True),
        hand_size=hand_size,rng_dice=random.Random(seed*97+32),
        hooks=hooks,dublin_policy=dublin_policy)
    for p in players:
        eco.new_project(f'Titulo-{p.id}','Titulo')
        eco.new_project(f'{PASSPORT_KIND[p.role]}-{p.id}',PASSPORT_KIND[p.role])
    agent=GameAgent(engine,eco,AgentConfig(policy),seed*97+64,profiles)
    original_after=hooks.after_turn
    def after_turn(eng,p,out):
        agent.after_turn(eng,p,out)
        original_after(eng,p,out)
    hooks.after_turn=after_turn
    stop='round_limit'
    for _ in range(max_rounds):
        engine.start_round()
        for p in players:
            engine.play_turn(p.id,
                youth_choice=agent.choose_youth,
                adult_choice=agent.choose_adult,
                choose_utn=True,choose_dublin=True)
            if eco.married is not None:
                stop='marriage'
                break
        if stop=='marriage':break
        eco.audit()
    eco.audit();profiles.audit()
    engine.youth_deck.assert_conservation()
    engine.adult_deck.assert_conservation()
    for deck in engine.situation_decks.values():deck.assert_conservation()
    types=Counter(p.stage.value for p in players)
    count=Counter(e['action'] for e in agent.actions)
    economic=Counter(e['action'] for e in eco.events)
    first_pair=next((tuple(e['players']) for e in eco.events if e['action']=='pair'),None)
    adult_moves=sum(e['action']=='movement' and e.get('origin','').startswith('Coord(') for e in engine.events)
    result={'size':n,'seed':seed,'policy':policy,'hand_size':hand_size,
        'dublin_policy':dublin_policy,'rounds':engine.round_no,
        'turns':sum(e['action']=='movement' for e in engine.events),
        'stop':stop,'won':eco.married is not None,
        'first_pair_round':agent.first_pair_round,
        'first_house_round':agent.first_house_round,
        'couples_at_end':sum(p.partner_id is not None for p in players)//2,
        'titles':sum(a.title for a in eco.accounts.values()),
        'passports':sum(a.passport is not None for a in eco.accounts.values()),
        'adults':types[Stage.ADULTEZ.value],
        'utn_passes':sum(p.utn_passed for p in players),
        'investments':count['investment'],
        'profile_changes':count['profile_change'],
        'house_transfers':sum(e['action']=='house_bought' and e.get('prior') is not None for e in eco.events),
        'adjudications':count['adjudication'],
        'house_attempts':economic['house_attempt'],
        'adult_moves':adult_moves,
        'adult_hand_renewals':sum(e['action']=='hand_renewed' for e in engine.events),
        'first_pair_wins':first_pair is not None and eco.married==first_pair,
        'profile_activations':sum(e.get('source') in ('vuelta_juventud','caida_perfil_adultez','colocacion_inicial_dublin')
                                  for e in eco.events if e['action']=='issue'),
        'marriage_eligible_ever':eco.married is not None,
        'synthetic_cards':True,
    }
    if with_events:
        result['action_log']=agent.actions
        result['economy_log']=eco.events
        result['movement_log']=engine.events
    return result


def experiment(seeds:int,rounds:int,hand:int,policy_choices=('aleatorio','planificador')):
    if not 1<=seeds<=1000:raise ValueError('Número semillas fuera de rango')
    rows=[]
    for n in (6,10):
        for seed in range(1,seeds+1):
            for policy in policy_choices:
                rows.append(run_game(n,seed,policy,rounds,hand))
    return rows


def summary(rows):
    groups={}
    for row in rows:
        k=f"{row['size']}-{row['policy']}"
        groups.setdefault(k,[]).append(row)
    output=[]
    for k,items in sorted(groups.items()):
        output.append({'size':items[0]['size'],'policy':items[0]['policy'],
            'games':len(items),'wins':sum(x['won'] for x in items),
            'win_rate':round(sum(x['won'] for x in items)/len(items),4),
            'mean_rounds':round(sum(x['rounds'] for x in items)/len(items),2),
            'mean_titles':round(sum(x['titles'] for x in items)/len(items),2),
            'mean_passports':round(sum(x['passports'] for x in items)/len(items),2),
            'mean_investments':round(sum(x['investments'] for x in items)/len(items),2),
            'mean_house_attempts':round(sum(x['house_attempts'] for x in items)/len(items),2),
            'mean_profile_changes':round(sum(x['profile_changes'] for x in items)/len(items),2),
            'first_pair_wins':sum(x['first_pair_wins'] for x in items),
            'mean_adult_moves':round(sum(x['adult_moves'] for x in items)/len(items),2),
            'mean_house_transfers':round(sum(x['house_transfers'] for x in items)/len(items),2)})
    return output


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--semillas',type=int,default=20)
    ap.add_argument('--rondas',type=int,default=100)
    ap.add_argument('--mano',type=int,choices=(3,4),default=3)
    ap.add_argument('--out',type=Path,default=Path('resultados/fase5'))
    args=ap.parse_args()
    rows=experiment(args.semillas,args.rondas,args.mano)
    args.out.mkdir(parents=True,exist_ok=True)
    with (args.out/'partidas_sinteticas_v2.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows)
    report={'advertencia':'MAZOS SINTÉTICOS, montos adultos hipotéticos y sin intervenciones sociales. NO ES BALANCE OFICIAL.',
            'seeds':args.semillas,'round_limit':args.rondas,'hand_size':args.mano,
            'results':summary(rows)}
    (args.out/'resumen_v2_experimental.json').write_text(
        json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2,ensure_ascii=False))

if __name__=='__main__':main()