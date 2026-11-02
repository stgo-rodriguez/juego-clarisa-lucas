"""Comparación CONTRAFACTUAL de sincronización Dublín, con fixtures declarados.

No se interpreta como probabilidad de victoria ni evaluación económica real.
Las mismas semillas se aplican a 6/10 jugadores y ambas políticas.
"""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
from statistics import mean
from laboratorio.smoke_transiciones_v2 import run_case


def compare(*,runs: int = 50, output: Path = Path('resultados/fase4')):
    if not 1<=runs<=500:raise ValueError('Usar entre 1 y 500 semillas')
    output.mkdir(parents=True,exist_ok=True)
    cases=[]
    for players in (6,10):
        for seed in range(1,runs+1):
            for policy in ('next_round','next_turn'):
                cases.append(run_case(players,seed,dublin_policy=policy,max_rounds=20))
    fields=['players','seed','dublin_policy_experimental',
            'rounds_until_first_adult_pair_turns','dublin_entry_round',
            'profiles_awarded','utn_passes','dublin_transitions',
            'dublin_wait_turns_experimental','adult_hand_renewals',
            'round_movements']
    with (output/'corridas_dublin_v2.csv').open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore')
        writer.writeheader()
        writer.writerows(cases)
    summary={
        'scope':'Contrafactual técnico; recursos e hitos inyectados, situaciones neutrales; no es balance ni Monte Carlo integral',
        'seeds_per_configuration':runs,
        'results':[
            {'players':n,'policy':p,
             'runs':len(sub),
             'dublin_wait_turns_total':sum(x['dublin_wait_turns_experimental'] for x in sub),
             'round_moves_mean':round(mean(x['round_movements'] for x in sub),3),
             'adult_pair_turns_round_mean':round(mean(x['rounds_until_first_adult_pair_turns'] for x in sub),3),
             'initial_dublin_entry_round_mean':round(mean(x['dublin_entry_round'] for x in sub),3)}
            for n in (6,10) for p in ('next_round','next_turn')
            for sub in [[x for x in cases if x['players']==n and x['dublin_policy_experimental']==p]]
        ]
    }
    (output/'resumen_dublin_v2.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    return summary


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--semillas',type=int,default=50)
    parser.add_argument('--out',type=Path,default=Path('resultados/fase4'))
    args=parser.parse_args()
    print(json.dumps(compare(runs=args.semillas,output=args.out),indent=2,ensure_ascii=False))


if __name__=='__main__':main()