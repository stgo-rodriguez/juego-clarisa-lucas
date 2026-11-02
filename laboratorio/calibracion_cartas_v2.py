"""Fase 11: factorial 2^3 de cartas DOCUMENTADAS NO APROBADAS.

Ajusta solo premios positivos de I/J, premios adultos, pérdidas explícitas.
Los costes voluntarios y pujas son INVARIANTES. Las 126 cartas no se editan.
8 variantes x mesas x bots x competencia x semillas apareadas.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
import csv
from dataclasses import asdict
from itertools import product
import json
import math
from pathlib import Path
import statistics
from laboratorio.experimento_mazos_propuestos_v2 import run_proposal
from simulador.mazos_propuestos_v2 import BalanceVariant, load_catalog

LEVELS = {'early_gain': (1.0, 0.60), 'adult_gain': (1.0, 0.70),
          'loss_multiplier': (1.0, 1.5)}
FACTOR_NAMES = ('early_gain', 'adult_gain', 'loss_multiplier')


def variants():
    return {f'cal_{a}{b}{c}': BalanceVariant(LEVELS['early_gain'][a],
                                            LEVELS['adult_gain'][b],
                                            LEVELS['loss_multiplier'][c])
            for a,b,c in product((0,1),repeat=3)}


def simulate(seeds=16, rounds=100, policies=('aleatorio','planificador'),
             competitions=(False,True), sizes=(6,10), scenario_ids=None):
    if type(seeds) is not int or type(rounds) is not int or min(seeds,rounds)<1:
        raise ValueError('Semillas y rondas deben ser enteros positivos')
    chosen=variants()
    if scenario_ids is not None:
        if not set(scenario_ids).issubset(chosen):raise ValueError('Variante no definida')
        chosen={id:chosen[id] for id in scenario_ids}
    catalog=load_catalog()
    rows=[]
    # Orden bloqueado: todas las variantes para una misma semilla/mesa/bot/competencia
    for size,policy,competition,seed in product(sizes,policies,competitions,range(1,seeds+1)):
        for key,balance in chosen.items():
            result=run_proposal(size,seed,policy,competition,catalog=catalog,
                                rounds=rounds,balance=balance)
            rows.append({'scenario':key,**result, 'round_limit':rounds,
                         'experimental':True})
    return rows


def _mean(xs):return round(statistics.mean(xs),3) if xs else None


def aggregate(rows):
    grouped=defaultdict(list)
    for r in rows:
        grouped[(r['scenario'],r['size'],r['policy'],r['competition'])].append(r)
    out=[]
    for (scenario,size,policy,competition),sample in sorted(grouped.items()):
        out.append({'scenario':scenario,'size':size,'policy':policy,'competition':competition,
                    'games':len(sample),'marriages':sum(r['won'] for r in sample),
                    'timeouts':sum(not r['won'] for r in sample),
                    'win_pct':round(100*statistics.mean(r['won'] for r in sample),2),
                    'mean_capped_rounds':_mean([r['rounds'] for r in sample]),
                    'median_capped_rounds':statistics.median(r['rounds'] for r in sample),
                    'mean_rounds_wins_only':_mean([r['rounds'] for r in sample if r['won']]),
                    'mean_no_progress_pct':_mean([r['no_progress_ratio']*100 for r in sample]),
                    'mean_card_issues_ex_auction':_mean([r['card_gains_units'] for r in sample]),
                    'mean_card_losses':_mean([r['card_losses_units'] for r in sample]),
                    'mean_auctions':_mean([r['social_auctions'] for r in sample]),
                    'mean_bids':_mean([r['bids'] for r in sample]),
                    'mean_duels':_mean([r['duels'] for r in sample])})
    return out


def effects(rows):
    """Diferencias apareadas por (mesa, bot, competencia, semilla, otros 2 factores)."""
    lookup={(r['size'],r['policy'],r['competition'],r['seed'],r['scenario']):r for r in rows}
    result=[]
    for size,policy,competition in product(sorted({r['size'] for r in rows}),
                                             sorted({r['policy'] for r in rows}),
                                             sorted({r['competition'] for r in rows})):
        seeds=sorted({r['seed'] for r in rows if r['size']==size})
        for factor_pos,factor in enumerate(FACTOR_NAMES):
            diffs=[];win_diffs=[];progress_diffs=[];seed_means=[]
            for seed in seeds:
                block=[]
                for bits in product((0,1),repeat=2):
                    low=list(bits);low.insert(factor_pos,0)
                    high=list(bits);high.insert(factor_pos,1)
                    ida='cal_'+''.join(map(str,low))
                    idb='cal_'+''.join(map(str,high))
                    ra=lookup.get((size,policy,competition,seed,ida))
                    rb=lookup.get((size,policy,competition,seed,idb))
                    if ra is None or rb is None:continue
                    diff=rb['rounds']-ra['rounds']
                    diffs.append(diff)
                    block.append(diff)
                    win_diffs.append(int(rb['won'])-int(ra['won']))
                    progress_diffs.append(100*(rb['no_progress_ratio']-ra['no_progress_ratio']))
                if block:seed_means.append(statistics.mean(block))
            if not diffs:continue
            # Las 4 diferencias de una semilla NO son independientes.
            # Calcular error estándar usando la media por bloque de semilla.
            sd=statistics.stdev(seed_means) if len(seed_means)>1 else 0
            se=sd/math.sqrt(len(seed_means))
            result.append({'size':size,'policy':policy,'competition':competition,
                'factor':factor,'contrast':'nivel reducido/intensificado menos referencia',
                'paired_n':len(diffs),'independent_seed_blocks':len(seed_means),
                'extra_rounds_cap':_mean(diffs),
                'ci95_normal_lo':round(statistics.mean(seed_means)-1.96*se,3),
                'ci95_normal_hi':round(statistics.mean(seed_means)+1.96*se,3),
                'extra_no_progress_pct_points':_mean(progress_diffs),
                'change_in_win_rate_pp':_mean(win_diffs)*100})
    return result


def write_report(rows, out:Path, *, seeds:int, rounds:int):
    out.mkdir(parents=True,exist_ok=True)
    with (out/'partidas_calibracion_v2.csv').open('w',newline='',encoding='utf-8') as handle:
        wr=csv.DictWriter(handle,fieldnames=list(rows[0]));wr.writeheader();wr.writerows(rows)
    summaries=aggregate(rows)
    with (out/'resumen_por_variante_v2.csv').open('w',newline='',encoding='utf-8') as handle:
        wr=csv.DictWriter(handle,fieldnames=list(summaries[0]));wr.writeheader();wr.writerows(summaries)
    marginal=effects(rows)
    with (out/'efectos_apareados_v2.csv').open('w',newline='',encoding='utf-8') as handle:
        wr=csv.DictWriter(handle,fieldnames=list(marginal[0]));wr.writeheader();wr.writerows(marginal)
    result={'status':'EXPERIMENTAL_NO_APROBADO',
        'source':'Fase 10: cartas 78 históricas + 30 propuestas adultas',
        'method':'2^3 completo con semillas apareadas. Se capan las partidas no finalizadas; reportar tasa de Casamiento.',
        'calibration_factors':LEVELS,
        'notes':['Los pagos voluntarios, requisitos y pujas no se escalan.',
                 'Se redondean premios y pérdidas a unidades enteras: int(n*factor+0.5).',
                 'Subastas: se mantiene reparto exacto y solo adjudicatario paga.',
                 'IC exploratorio 95% calculado a nivel de semilla (cuatro comparaciones internas no independientes).',
                 'Ingresos de cartas en columnas excluyen beneficios de subasta; las rondas sí los incorporan.',
                 'Cartas v0.1 y v0.2 NO aprobadas; casilleros adultos=2 y bots son experimentales.',
                 'Turno sin avance duradero no equivale a turno inútil.'],
        'seeds':seeds,'max_rounds':rounds,'total_games':len(rows),'marriages':sum(r['won'] for r in rows),
        'timeouts':sum(not r['won'] for r in rows),'summary':summaries,'marginal_effects':marginal}
    (out/'resumen_calibracion_v2.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--semillas',type=int,default=16)
    parser.add_argument('--rondas',type=int,default=100)
    parser.add_argument('--out',type=Path,default=Path('resultados/fase11'))
    parser.add_argument('--solo-planificador',action='store_true')
    parser.add_argument('--solo-competencia',action='store_true')
    parser.add_argument('--mesa',type=int,choices=(6,10))
    parser.add_argument('--agente',choices=('aleatorio','planificador'))
    parser.add_argument('--competencia',choices=('si','no'))
    args=parser.parse_args()
    rows=simulate(args.semillas,args.rondas,
        policies=(args.agente,) if args.agente else (('planificador',) if args.solo_planificador else ('aleatorio','planificador')),
        competitions=(args.competencia=='si',) if args.competencia else ((True,) if args.solo_competencia else (False,True)),
        sizes=(args.mesa,) if args.mesa else (6,10))
    report=write_report(rows,args.out,seeds=args.semillas,rounds=args.rondas)
    print(json.dumps({'partidas':report['total_games'],'casamientos':report['marriages'],
                      'limites':report['timeouts'],'escenarios':len(variants()),
                      'archivos':str(args.out)},ensure_ascii=False))


if __name__=='__main__': main()