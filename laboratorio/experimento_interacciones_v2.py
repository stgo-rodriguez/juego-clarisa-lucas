"""Stress de subastas v2 con cartas sintéticas y 6/10 jugadores.

NO es Monte Carlo de partidas completas, NI carta oficial de Adultez.
Demuestra una vuelta, solvencia, ganador único y sensibilidad a reglas de puja.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path
from collections import Counter
from simulador.movimiento_v2 import Coord, MovementCard, youth_cards
from simulador.turnos_v2 import PlayerState, RoundEngine, CardPool, SituationCard, Stage
from simulador.economia_v2 import EconomyV2, EconomyScenario
from simulador.interacciones_v2 import AuctionCard, Bid, SocialAuctionsV2


def _setup(n:int,seed:int):
    rng=random.Random(seed*109+31)
    participants=[PlayerState(i+1,'Clarisa' if i<n//2 else 'Lucas',
                   Stage.ADULTEZ if i==0 or i%3==0 else Stage.JUVENTUD,
                   Coord(5,3) if i==0 or i%3==0 else 2) for i in range(n)]
    eco=EconomyV2(participants,scenario=EconomyScenario(neutral_situations=True,
                                 adult_square_amounts={'A':0,'P':0,'K':0,'M':0}))
    for p in participants:
        for r in 'APKM':
            eco.issue(p.id,r,rng.randint(0,9) if p.id!=1 else 0,'fixt_saldo_experimental')
    situation={(stage,role):CardPool([SituationCard(f'{stage.value}-{role}',stage,role)],random.Random(seed),recycle=True)
               for stage in (Stage.INFANCIA,Stage.JUVENTUD,Stage.ADULTEZ) for role in ('Clarisa','Lucas')}
    engine=RoundEngine(participants,situation,
          CardPool(youth_cards(),random.Random(seed+1),recycle=True),
          CardPool([MovementCard(f'exp-{i}',1,2) for i in range(100)],random.Random(seed+2),recycle=True),
          hooks=eco.hooks())
    return eco,engine,rng


def run_auction(n:int,seed:int,mode:str)->dict:
    if n not in (6,10) or mode not in ('fixed','heterogeneous'):
        raise ValueError('Tamaños 6/10 y puja fija/heterogénea')
    eco,e,rng=_setup(n,seed)
    contestants=list(range(2,n+1))
    rng.shuffle(contestants)
    initial={p:dict(eco.accounts[p].free) for p in eco.accounts}
    card=AuctionCard(id=f'EXP-{mode}',benefit_resource='A',total=6,appropriable=4,
        mode=mode,bid_resources=('M',) if mode=='fixed' else ('A','M'),
        no_bid_effect='full',reject_effect='none',allow_reject=True)
    eligible=tuple(contestants)
    calls=[]
    def compare_bid(new:Bid, old:Bid):
        # Preferencia del jugador activo EN ESTE EXPERIMENTO: Amor antes que
        # Dinero, y luego cantidad, sin convertir A y M a una tasa fija.
        def rank(b):return (1 if b.resource=='A' else 0,b.quantity)
        return (rank(new)>rank(old))-(rank(new)<rank(old))
    def bid_for(p:PlayerState,leader:Bid|None):
        calls.append(p.id)
        if rng.random()<.3:return None
        currency='M' if mode=='fixed' else rng.choice(('M','A'))
        budget=eco.accounts[p.id].free[currency]
        if not budget:return None
        cap=min(6,budget)
        quantity=rng.randint(1,cap)
        return Bid(p.id,currency,quantity)
    def select_winner(best:tuple[Bid,...]):
        if rng.random()<.15:return None
        return rng.choice(best).player_id
    auction=SocialAuctionsV2(eco,e)
    result=auction.run(1,card,bid_for=bid_for,select_winner=select_winner,
          bid_order=eligible,compare_heterogeneous=compare_bid if mode=='heterogeneous' else None)
    eco.audit()
    assert len(calls)==len(eligible)==n-1
    assert len(set(calls))==len(calls)
    assert set(calls)==set(eligible)
    assert result.credited_active + result.credited_winner in (0,6)
    payments={pid: initial[pid]['M']-eco.accounts[pid].free['M'] for pid in contestants}
    if mode=='fixed' and result.winner is not None:
        assert sum(payments.values())==result.best_bid.quantity
        assert len([x for x in payments.values() if x>0])==1
    return {'size':n,'seed':seed,'mode':mode,'winner':result.winner,
        'reason':result.reason,'bids_valid':len(result.bids),'passed':len(result.passed),
        'bidders_considered':len(calls),'active_credit':result.credited_active,
        'winner_credit':result.credited_winner,
        'winning_resource':result.best_bid.resource if result.best_bid else '',
        'winning_amount':result.best_bid.quantity if result.best_bid else 0,
        'experimental':True}


def experiment(seeds:int)->tuple[list[dict],list[dict]]:
    results=[run_auction(n,seed,mode) for n in (6,10)
             for mode in ('fixed','heterogeneous') for seed in range(1,seeds+1)]
    summary=[]
    for n in (6,10):
        for mode in ('fixed','heterogeneous'):
            subset=[row for row in results if row['size']==n and row['mode']==mode]
            reason=Counter(row['reason'] for row in subset)
            summary.append({'size':n,'mode':mode,'auctions':len(subset),
                'awarded':reason['awarded'],'no_bids':reason['no_bids'],
                'rejected':reason['rejected'],
                'mean_valid_offers':round(sum(r['bids_valid'] for r in subset)/len(subset),2),
                'mean_passes':round(sum(r['passed'] for r in subset)/len(subset),2)})
    return results,summary


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--semillas',type=int,default=50)
    parser.add_argument('--out',type=Path,default=Path('resultados/interacciones_v2'))
    args=parser.parse_args()
    if not 1<=args.semillas<=200:raise ValueError('Semillas deben ser entre 1 y 200')
    results,summary=experiment(args.semillas)
    args.out.mkdir(parents=True,exist_ok=True)
    with (args.out/'subastas_sinteticas_v2.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(results[0]));writer.writeheader();writer.writerows(results)
    report={'warning':'Cartas y decisiones sintéticas. NO representa balance de Clarisa y Lucas.',
            'seeds':args.semillas,'total_auctions':len(results),'summary':summary}
    (args.out/'resumen_interacciones_v2.json').write_text(
        json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':main()