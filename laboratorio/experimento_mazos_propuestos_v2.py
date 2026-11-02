"""Comparación pareada de mazos documentados NO APROBADOS vs sintéticos.

Efectos históricos v0.1 de I/J duplicados por personaje; Adultez v0.2
multiverso (15+15) propuesta. No modifica el reglamento ni lo aprueba.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
import random
import statistics

from simulador.agentes_v2 import AgentConfig, GameAgent
from simulador.competencia_v2 import CompetitionConfig, CompetitiveController
from simulador.economia_v2 import EconomyScenario, EconomyV2, PASSPORT_KIND
from simulador.interacciones_v2 import InteractionV2, SocialAuctionsV2
from simulador.mazos_propuestos_v2 import CATALOG_PATH, ProposedResolver, BalanceVariant, build_decks, load_catalog
from simulador.movimiento_v2 import youth_cards
from simulador.transiciones_v2 import ProfileDecksV2, transition_hooks
from simulador.turnos_v2 import CardPool, PlayerState, RoundEngine, SituationCard, Stage
from laboratorio.experimento_agentes_v2 import adult_cards
from laboratorio.sensibilidad_v2 import StressScenario, run_game as synthetic_game, progress_score


def run_proposal(n:int,seed:int,policy:str,competition:bool,*,catalog=None,rounds:int=100,hand_size:int=3,balance:BalanceVariant|None=None):
    if n not in (6,10) or policy not in ('aleatorio','planificador') or type(competition) is not bool:
        raise ValueError('Parámetros de partida inválidos')
    catalog = catalog if catalog is not None else load_catalog()
    balance=balance or BalanceVariant()
    players=[PlayerState(i+1,'Clarisa' if i<n//2 else 'Lucas') for i in range(n)]
    eco=EconomyV2(players,scenario=EconomyScenario(
        adult_square_amounts=dict.fromkeys('APKM',2),neutral_situations=False),
        rng=random.Random(seed*97+14))
    profiles=ProfileDecksV2(seed*23+14)
    hooks=transition_hooks(eco,profiles)
    engine=RoundEngine(players,build_decks(catalog,seed*37),
        CardPool(youth_cards(),random.Random(seed*97+44),recycle=True),
        CardPool(adult_cards(),random.Random(seed*97+45),recycle=True),
        hand_size=hand_size,rng_dice=random.Random(seed*97+32),
        hooks=hooks,dublin_policy='next_turn')
    for p in players:
        eco.new_project(f'Titulo-{p.id}','Titulo')
        eco.new_project(f'{PASSPORT_KIND[p.role]}-{p.id}',PASSPORT_KIND[p.role])
    agent=GameAgent(engine,eco,AgentConfig(policy),seed*97+64,profiles)
    interactions=InteractionV2(engine,eco,profiles,rng=random.Random(seed*97+65))
    auctions=SocialAuctionsV2(eco,engine)
    controller=CompetitiveController(engine,eco,agent,interactions,auctions,
         CompetitionConfig(enabled=competition,youth_return_pos=None),seed*97+66)
    resolver=ProposedResolver(eco,policy=policy,competition_controller=controller,
                              rng=random.Random(seed*97+99),balance=balance)
    hooks.apply_situation=resolver.resolve
    prior_after=hooks.after_turn
    def after(e,p,out):
        agent.after_turn(e,p,out)
        controller.after_turn(e,p,out)
        prior_after(e,p,out)
    hooks.after_turn=after
    def youth(p,card,movement):
        # El planificador observa los A/B efectivos de la Situación juvenil.
        # No consulta cartas futuras y usa la MISMA letra para la distancia.
        effects=card.payload['effects']
        proxy=SituationCard(card.id,Stage.JUVENTUD,p.role,effects)
        return agent.choose_youth(p,proxy,movement)
    stop='round_limit';turns=0;no_progress=0
    for _ in range(rounds):
        engine.start_round()
        for p in players:
            prev_progress=progress_score(engine,eco)
            engine.play_turn(p.id,youth_choice=youth,adult_choice=agent.choose_adult,
                             choose_utn=True,choose_dublin=True)
            turns+=1
            if progress_score(engine,eco)<=prev_progress:no_progress+=1
            if eco.married is not None:
                stop='marriage';break
        if stop=='marriage':break
        eco.audit()
    eco.audit();profiles.audit()
    engine.youth_deck.assert_conservation()
    engine.adult_deck.assert_conservation()
    for d in engine.situation_decks.values():d.assert_conservation()
    events=Counter((e['stage'],e['family']) for e in resolver.events)
    outcomes=Counter(e['result'] for e in resolver.events)
    resource_card_gains=sum(e['amount'] for e in eco.events if e['action']=='issue' and e.get('source')=='propuesta_situacion_premio')
    resource_card_losses=sum(e['amount'] for e in eco.events if e['action']=='spend' and e.get('source')=='propuesta_situacion_perdida_libre')
    return {
        'size':n,'seed':seed,'policy':policy,'competition':competition,'model':'propuestas_documentadas',
        'early_gain_factor':balance.early_gain,'adult_gain_factor':balance.adult_gain,'loss_multiplier':balance.loss_multiplier,
        'rounds':engine.round_no,'turns_executed':turns,'won':eco.married is not None,'stop':stop,
        'no_progress_ratio':round(no_progress/turns,5) if turns else 0,
        'card_gains_units':resource_card_gains,'card_losses_units':resource_card_losses,
        'situations_resolved':len(resolver.events),'situations_adult':sum(e['stage']=='Adultez' for e in resolver.events),
        'individual_choices':sum(v for (stage,family),v in events.items() if stage=='Adultez' and family=='Decisión individual'),
        'conflicts':sum(v for (stage,family),v in events.items() if stage=='Adultez' and family=='Conflicto entre versiones'),
        'cooperations':sum(v for (stage,family),v in events.items() if stage=='Adultez' and family=='Cooperación entre versiones'),
        'social_auctions':sum(v for (stage,family),v in events.items() if stage=='Adultez' and family=='Subasta de apropiación'),
        'coop_accepted':outcomes['coop_accepted'], 'no_target':outcomes['no_target'],
        'auctions_awarded':sum(x['reason']=='awarded' for x in auctions.events),
        'bids':sum(len(x['bids']) for x in auctions.events),
        'duels':sum(x['action']=='duel' for x in interactions.events),
        'pairs_formed':sum(x['action']=='pair' for x in eco.events),
        'houses_bought':sum(x['action']=='house_bought' for x in eco.events),
        'profile_activations':sum(x['action']=='profile_activation' for x in eco.events),
        'source_legacy':'v0.1_histórica_duplicación_experimental',
        'source_adult':'v0.2_multiverso_propuesta_no_aprobada',
    }


def run_paired(seeds:int=8,rounds:int=100,policies=('planificador','aleatorio'),competitions=(True,False),catalog=None):
    if seeds<1 or rounds<1:raise ValueError('Semillas/rondas no válidas')
    catalog = catalog if catalog is not None else load_catalog()
    rows=[]
    for n in (6,10):
        for seed in range(1,seeds+1):
            for policy in policies:
                for competition in competitions:
                    proposal=run_proposal(n,seed,policy,competition,catalog=catalog,rounds=rounds)
                    synthetic=synthetic_game(n,seed,policy,competition,
                            StressScenario('base_sintetica',1.0),rounds=rounds)
                    rows.append({**proposal,
                        'synthetic_rounds':synthetic['rounds'],'synthetic_won':synthetic['won'],
                        'delta_rounds_proposals_minus_synthetic':proposal['rounds']-synthetic['rounds']})
    return rows


def summarize(rows):
    groups=defaultdict(list)
    for r in rows:groups[(r['size'],r['policy'],r['competition'])].append(r)
    result=[]
    for (n,policy,comp),group in sorted(groups.items()):
        mean=lambda k:round(statistics.mean(g[k] for g in group),2)
        result.append({'size':n,'policy':policy,'competition':comp,'runs':len(group),
            'proposals_marriages':sum(g['won'] for g in group),
            'synthetic_marriages':sum(g['synthetic_won'] for g in group),
            'mean_proposal_rounds_cap':mean('rounds'),
            'mean_synthetic_rounds_cap':mean('synthetic_rounds'),
            'paired_delta_rounds_cap':mean('delta_rounds_proposals_minus_synthetic'),
            'mean_adult_auctions':mean('social_auctions'),
            'mean_bids':mean('bids'),'mean_duels':mean('duels'),
            'mean_cooperations':mean('cooperations')})
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--semillas',type=int,default=8)
    parser.add_argument('--rondas',type=int,default=100)
    parser.add_argument('--out',type=Path,default=Path('resultados/fase10'))
    args=parser.parse_args()
    catalog=load_catalog()
    rows=run_paired(args.semillas,args.rondas,catalog=catalog)
    args.out.mkdir(parents=True,exist_ok=True)
    with (args.out/'partidas_mazos_documentados_v2.csv').open('w',newline='',encoding='utf-8') as file:
        writer=csv.DictWriter(file,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    report={'disclaimer':'NO APROBADOS: Infancia/Juventud histórico v0.1 duplicado por rol; Adultez propuestas v0.2 multiverso; los montos adultos y bots son experimentales.',
            'seeds':args.semillas,'round_limit':args.rondas,'games':len(rows),
            'summary':summarize(rows)}
    (args.out/'resumen_mazos_documentados_v2.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':main()