"""Comparación contrafactual de bots con/sin competencia (NO balance oficial).

Genera partidas desde Infancia con las seis barajas sintéticas, mazo adulto
experimental y políticas de selección/puja marcadas como HIPÓTESIS. Cada semilla
se repite con competencia desactivada y activada.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

from simulador.agentes_v2 import AgentConfig, GameAgent
from simulador.competencia_v2 import CompetitionConfig, CompetitiveController
from simulador.economia_v2 import EconomyScenario, EconomyV2, PASSPORT_KIND
from simulador.interacciones_v2 import AuctionCard, InteractionV2, SocialAuctionsV2
from simulador.movimiento_v2 import youth_cards
from simulador.transiciones_v2 import ProfileDecksV2, transition_hooks
from simulador.turnos_v2 import CardPool, PlayerState, RoundEngine, SituationCard, Stage
from laboratorio.experimento_agentes_v2 import effect, adult_cards


def create_situations(seed: int) -> dict:
    """Seis mazos sintéticos; 12/20 cartas adultas con apropiación experimental.

    NO se afirma que esta frecuencia o los montos sean los de v2.0.
    """
    decks={}
    for k,(stage,role) in enumerate((s,r) for s in (Stage.INFANCIA,Stage.JUVENTUD,Stage.ADULTEZ)
                            for r in ('Clarisa','Lucas')):
        cards=[]
        for i in range(20):
            payload=effect(stage,i)
            if stage==Stage.ADULTEZ and i%5 in (0,1,2):
                mode=('fixed','heterogeneous','active_choice')[i%5]
                if mode=='fixed':
                    payload=AuctionCard(f'AUC-{role}-{i}',benefit_resource='A',total=6,
                        appropriable=4,mode=mode,bid_resources=('M',),allow_reject=False,
                        no_bid_effect='full',reject_effect='full')
                elif mode=='heterogeneous':
                    payload=AuctionCard(f'AUC-{role}-{i}',benefit_resource='M',total=5,
                        appropriable=3,mode=mode,bid_resources=('A','P'),allow_reject=False,
                        no_bid_effect='full',reject_effect='none')
                else:
                    payload=AuctionCard(f'AUC-{role}-{i}',benefit_resource='P',total=5,
                        appropriable=3,mode=mode,bid_resources=('M','K'),allow_reject=True,
                        no_bid_effect='full',reject_effect='full')
            cards.append(SituationCard(f'SYN-{stage.value}-{role}-{i}',stage,role,payload))
        decks[(stage,role)]=CardPool(cards,random.Random(seed+13*k),recycle=True)
    return decks


def run_game(size:int,seed:int,agent_policy:str,competition:bool,
             *,max_rounds:int=80,hand_size:int=3,return_youth_pos:int | None=None,
             with_events:bool=False)->dict:
    if size not in (6,10) or agent_policy not in ('planificador','aleatorio'):
        raise ValueError('Configuración inválida')
    players=[PlayerState(i+1,'Clarisa' if i<size//2 else 'Lucas') for i in range(size)]
    eco=EconomyV2(players,scenario=EconomyScenario(
        adult_square_amounts={'A':2,'P':2,'K':2,'M':2},neutral_situations=False),
        rng=random.Random(seed*97+14))
    profiles=ProfileDecksV2(seed*23+14)
    hooks=transition_hooks(eco,profiles)
    engine=RoundEngine(players,create_situations(seed*37),
        CardPool(youth_cards(),random.Random(seed*97+44),recycle=True),
        CardPool(adult_cards(),random.Random(seed*97+45),recycle=True),
        hand_size=hand_size,rng_dice=random.Random(seed*97+32),
        hooks=hooks,dublin_policy='next_turn')
    for p in players:
        eco.new_project(f'Titulo-{p.id}','Titulo')
        eco.new_project(f'{PASSPORT_KIND[p.role]}-{p.id}',PASSPORT_KIND[p.role])
    agent=GameAgent(engine,eco,AgentConfig(agent_policy),seed*97+64,profiles)
    interactions=InteractionV2(engine,eco,profiles,rng=random.Random(seed*97+65))
    auctions=SocialAuctionsV2(eco,engine)
    controller=CompetitiveController(engine,eco,agent,interactions,auctions,
          CompetitionConfig(enabled=competition,youth_return_pos=return_youth_pos),seed*97+66)

    def synthetic_effect(e,p,card,letter):
        key=letter if p.stage==Stage.JUVENTUD else 'base'
        delta=card.payload[key]
        for resource,amount in delta.items():
            if amount>=0:eco.issue(p.id,resource,amount,'situacion_sintetica_experimental')
            else:eco.spend(p.id,resource,min(-amount,eco.accounts[p.id].free[resource]),
                           'situacion_sintetica_experimental')
        eco.events.append({'action':'situation_synthetic_experimental',
                          'player':p.id,'card':card.id,'choice':letter})

    def resolve(e,p,card,letter):
        controller.resolve_social_situation(e,p,card,synthetic_effect,letter)

    hooks.apply_situation=resolve
    previous_after=hooks.after_turn
    def after(e,p,out):
        agent.after_turn(e,p,out)
        controller.after_turn(e,p,out)
        previous_after(e,p,out)
    hooks.after_turn=after

    stop='round_limit'
    for _ in range(max_rounds):
        engine.start_round()
        for p in players:
            engine.play_turn(p.id,youth_choice=agent.choose_youth,
                adult_choice=agent.choose_adult,choose_utn=True,choose_dublin=True)
            if eco.married is not None:
                stop='marriage'
                break
        if stop=='marriage':break
        eco.audit()
    eco.audit()
    profiles.audit()
    engine.youth_deck.assert_conservation()
    engine.adult_deck.assert_conservation()
    for deck in engine.situation_decks.values():deck.assert_conservation()
    auction_counts=Counter(e['reason'] for e in auctions.events)
    duel_counts=Counter(e['result'] for e in interactions.events if e['action']=='duel')
    duel_types=Counter(e['kind'] for e in interactions.events if e['action']=='duel')
    result={
        'size':size,'seed':seed,'policy':agent_policy,'competition':competition,
        'hand_size':hand_size,'max_rounds':max_rounds,'rounds':engine.round_no,
        'stop':stop,'won':eco.married is not None,
        'auctions':len(auctions.events),'auctions_awarded':auction_counts['awarded'],
        'auctions_rejected':auction_counts['rejected'],
        'auctions_no_bids':auction_counts['no_bids'],
        'bids':sum(len(e['bids']) for e in auctions.events),
        'duels':sum(duel_counts.values()),'duels_won':duel_counts['victoria'],
        'duels_retreat':duel_counts['retirada'],'duels_lost':duel_counts['derrota'],
        'duels_tied':duel_counts['empate'],
        'ordinary_duels':duel_types['ordinario'],'profile_duels':duel_types['perfil'],
        'milestone_duels':duel_types['hito'],
        'pair_breaks':sum(e['action']=='pair_broken' for e in eco.events),
        'house_transfers':sum(e['action']=='house_bought' and e.get('prior') is not None for e in eco.events),
        'titles':sum(ac.title for ac in eco.accounts.values()),
        'passports':sum(ac.passport is not None for ac in eco.accounts.values()),
        'adult_moves':sum(e['action']=='movement' and e.get('origin','').startswith('Coord(') for e in engine.events),
        'synthetic_scenarios':True,'experimental_return_youth_pos':return_youth_pos,
    }
    if with_events:
        result['auction_log']=auctions.events
        result['duel_log']=interactions.events
        result['controller_log']=controller.events
        result['economy_log']=eco.events
    return result


def compare(seeds:int=30,rounds:int=80,hand_size:int=3)->list[dict]:
    if seeds<1 or rounds<1:raise ValueError('Semillas/rondas deben ser positivas')
    rows=[]
    for size in (6,10):
        for seed in range(1,seeds+1):
            for policy in ('aleatorio','planificador'):
                for enabled in (False,True):
                    rows.append(run_game(size,seed,policy,enabled,
                                         max_rounds=rounds,hand_size=hand_size))
    return rows


def summarize(rows:list[dict]):
    groups=defaultdict(list)
    for row in rows:
        groups[(row['size'],row['policy'],row['competition'])].append(row)
    output=[]
    for (size,policy,comp),g in sorted(groups.items()):
        output.append({'jugadores':size,'politica':policy,'competencia':comp,
             'partidas':len(g),'casamientos':sum(x['won'] for x in g),
             'rondas_medias':round(sum(x['rounds'] for x in g)/len(g),2),
             'subastas_medias':round(sum(x['auctions'] for x in g)/len(g),2),
             'adjudicadas_medias':round(sum(x['auctions_awarded'] for x in g)/len(g),2),
             'ofertas_medias':round(sum(x['bids'] for x in g)/len(g),2),
             'duelos_medios':round(sum(x['duels'] for x in g)/len(g),2),
             'transferencias_casa_medias':round(sum(x['house_transfers'] for x in g)/len(g),2),
             'rupturas_medias':round(sum(x['pair_breaks'] for x in g)/len(g),2)})
    return output


def paired_effects(rows: list[dict]) -> list[dict]:
    """Diferencia POR SEMILLA, separada de comparar promedios independientes."""
    groups=defaultdict(dict)
    for r in rows:
        k=(r['size'],r['policy'],r['seed'])
        if r['competition'] in groups[k]:
            raise ValueError('Configuración de semilla duplicada')
        groups[k][r['competition']]=r
    paired=defaultdict(list)
    for (size,policy,seed),treatments in groups.items():
        if set(treatments)!={False,True}:
            raise ValueError('Se requieren ambos tratamientos para cada semilla')
        paired[(size,policy)].append(treatments[True]['rounds']-treatments[False]['rounds'])
    return [{'jugadores':size,'politica':policy,'semillas':len(diffs),
             'delta_rondas_con_menos_sin':round(sum(diffs)/len(diffs),3),
             'competencia_mas_rapida':sum(d<0 for d in diffs),
             'competencia_mas_lenta':sum(d>0 for d in diffs),
             'sin_cambio':sum(d==0 for d in diffs)}
            for (size,policy),diffs in sorted(paired.items())]


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--semillas',type=int,default=30)
    ap.add_argument('--rondas',type=int,default=80)
    ap.add_argument('--mano',type=int,choices=(3,4),default=3)
    ap.add_argument('--out',type=Path,default=Path('resultados/fase7'))
    args=ap.parse_args()
    rows=compare(args.semillas,args.rondas,args.mano)
    args.out.mkdir(parents=True,exist_ok=True)
    with (args.out/'partidas_competencia_v2.csv').open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows)
    report={'advertencia':'Escenarios y mazos SINTÉTICOS; pujas y elegibilidad de cartas EXPERIMENTALES, NO balance oficial.',
            'semillas':args.semillas,'rondas_max':args.rondas,'mano':args.mano,
            'partidas':len(rows),'resultados':summarize(rows),
            'diferencias_pareadas':paired_effects(rows)}
    (args.out/'resumen_competencia_v2.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2,ensure_ascii=False))


if __name__=='__main__':main()