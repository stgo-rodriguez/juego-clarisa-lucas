"""Resumen reproducible de un escenario de sensibilidad SIMLOG v2.2."""
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import Counter
from pathlib import Path


def read_csv(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def median(values):
    return statistics.median(values) if values else None


def percentile(values, q):
    return sorted(values)[max(0, math.ceil(q*len(values))-1)] if values else None


def main(folder):
    folder=Path(folder)
    games=read_csv(folder/'partidas.csv')
    if not games:
        raise ValueError('Sin partidas en resultados')
    sizes={int(row['size']) for row in games}
    policies={row['policy'] for row in games}
    hands={int(row['hand_size']) for row in games}
    if len(sizes)!=1 or len(policies)!=1 or len(hands)!=1:
        raise AssertionError('La corrida debe corresponder a un único escenario')
    for row in games:
        if int(row['turns'])<=0 or int(row['rounds'])<=0:
            raise AssertionError('Turnos/rondas inválidos')
        mapping=json.loads(row['policies_by_player'])
        if len(mapping)!=int(row['size']):
            raise AssertionError('No se asignaron políticas a todos los jugadores')
        if int(row['choices_A'])+int(row['choices_B']) != int(row['situations_resolved']):
            raise AssertionError('Recuento de decisiones incompleto')
    won=[g for g in games if g['won'].lower() in ('true','1')]
    blocked=[g for g in games if g['stop']=='rule_pending']
    limit=[g for g in games if g['stop']=='round_limit']
    durations=[int(g['rounds']) for g in won]
    observed=[int(g['rounds']) for g in games]
    turns=[int(g['turns']) for g in games]
    diversity=(read_csv(folder/'diversidad_decisiones_por_grupo.csv')
               if (folder/'diversidad_decisiones_por_grupo.csv').is_file() else [])
    first=[g for g in diversity if g['etapa']=='Infancia'
           and int(g['ronda'])==1 and int(g['participantes'])>=2]
    winner_policy=Counter()
    for g in won:
        policies_by_id=json.loads(g['policies_by_player'])
        for pid in json.loads(g['winning_pair']):
            winner_policy[policies_by_id[str(pid)]] += 1
    bank=sum(int(g['bank_conversions']) for g in games)
    a=sum(int(g['choices_A']) for g in games)
    b=sum(int(g['choices_B']) for g in games)
    summary={
        'scenario':f"{next(iter(policies))}_h{next(iter(hands))}",
        'size':next(iter(sizes)),
        'policy':next(iter(policies)),
        'hand_size':next(iter(hands)),
        'games':len(games),
        'marriages':len(won),
        'marriages_pct':round(100*len(won)/len(games),2),
        'blocked_pending_rule':len(blocked),
        'blocked_pending_rule_pct':round(100*len(blocked)/len(games),2),
        'round_limit_cases':len(limit),
        'median_rounds':median(durations),
        'p80_rounds':percentile(durations,.8),
        'mean_rounds':round(statistics.mean(durations),2) if durations else None,
        'max_rounds':max(durations) if durations else None,
        'median_observed_rounds_including_censored':median(observed),
        'turns_total':sum(turns),
        'choices_a':a,
        'choices_b':b,
        'choices_a_pct':round(100*a/(a+b),2) if a+b else None,
        'bank_conversions':bank,
        'bank_per_100_turns':round(100*bank/sum(turns),2),
        'first_round_groups':len(first),
        'first_round_groups_heterogeneous_ab':sum(int(g['ambas_opciones']) for g in first),
        'first_round_ab_diversity_pct':round(
            100*sum(int(g['ambas_opciones']) for g in first)/len(first),2
        ) if first else None,
        'winning_individuals_planificador':winner_policy['planificador'],
        'winning_individuals_aleatorio':winner_policy['aleatorio'],
        'planner_winner_share_pct':round(
            100*winner_policy['planificador']/(2*len(won)),2
        ) if won else None,
        'seeds_min':min(int(g['seed']) for g in games),
        'seeds_max':max(int(g['seed']) for g in games),
    }
    (folder/'resumen_experimento.json').write_text(
        json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    with (folder/'resumen_experimento.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(summary))
        writer.writeheader();writer.writerow(summary)
    print('RESULTADO_EXPERIMENTO_V22', json.dumps(summary,ensure_ascii=False))


if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--out',type=Path,required=True)
    main(ap.parse_args().out)
