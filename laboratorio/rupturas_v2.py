"""Fase 9: intervención experimental de reserva juvenil antes de mover.

Cada evento afecta explícitamente hasta 5A RESERVADOS. El compañero puede
reponer A libre inmediatamente. En Juventud una ruptura NO necesita inventar
la coordenada de retorno desde Adultez; ese caso queda sin integrar.
"""
from __future__ import annotations
import argparse
import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path
from laboratorio.sensibilidad_v2 import StressScenario,run_game

RATES=(0.0,0.15,0.35)
STRESS=StressScenario('reserva_juventud_base',1.0)


def compare(seeds=12,rounds=100,policies=('planificador','aleatorio'),competitions=(False,True)):
    if seeds<1 or rounds<1:raise ValueError('Parámetros inválidos')
    rows=[]
    for n in (6,10):
        for seed in range(1,seeds+1):
            for policy in policies:
                for competition in competitions:
                    for rate in RATES:
                        rows.append(run_game(n,seed,policy,competition,STRESS,
                            rounds=rounds, youth_reserve_loss_rate=rate,
                            youth_reserve_loss_amount=5))
    return rows


def summarize(rows):
    groups=defaultdict(list)
    for r in rows:
        groups[(r['size'],r['policy'],r['competition'],r['youth_reserve_loss_rate_experimental'])].append(r)
    result=[]
    for (size,policy,comp,rate),group in sorted(groups.items()):
        result.append({'size':size,'policy':policy,'competition':comp,
            'prob_por_situacion_de_joven_emparejado':rate,'runs':len(group),
            'casamientos':sum(r['won'] for r in group),
            'rondas_promedio_cap':round(statistics.mean(r['rounds'] for r in group),3),
            'eventos':sum(r['reserve_events'] for r in group),
            'reparaciones':sum(r['reserve_repairs'] for r in group),
            'rupturas':sum(r['reserve_breaks'] for r in group),
            'rupturas_por_partida':round(statistics.mean(r['reserve_breaks'] for r in group),3),
            'duelos_por_partida':round(statistics.mean(r['duels'] for r in group),3)})
    return result


def paired(rows):
    indexed={(r['size'],r['seed'],r['policy'],r['competition'],r['youth_reserve_loss_rate_experimental']):r for r in rows}
    if len(indexed)!=len(rows):raise ValueError('Registros duplicados')
    result=[]
    for rate in RATES[1:]:
        for size in (6,10):
            for policy in ('aleatorio','planificador'):
                for comp in (False,True):
                    deltas=[];wdelta=[]
                    for seed in sorted({r['seed'] for r in rows}):
                        k=(size,seed,policy,comp)
                        if (*k,0.0) not in indexed or (*k,rate) not in indexed:
                            raise ValueError('Semilla emparejada faltante')
                        a,b=indexed[(*k,0.0)],indexed[(*k,rate)]
                        deltas.append(b['rounds']-a['rounds'])
                        wdelta.append(int(b['won'])-int(a['won']))
                    result.append({'size':size,'policy':policy,'competition':comp,'rate':rate,
                        'paired_seeds':len(deltas),'delta_rondas_cap':round(statistics.mean(deltas),3),
                        'delta_victorias':sum(wdelta)})
    return result


def save(rows,path:Path):
    path.mkdir(parents=True,exist_ok=True)
    with (path/'partidas_reservas_v2.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    report={'nota':'Situaciones de pérdida de reserva SINTÉTICAS exclusivamente juveniles; ninguna es carta oficial.',
        'partidas':len(rows),'summary':summarize(rows),'paired':paired(rows)}
    (path/'resumen_reservas_v2.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--semillas',type=int,default=12)
    p.add_argument('--rondas',type=int,default=100)
    p.add_argument('--out',type=Path,default=Path('resultados/fase9_reservas'))
    a=p.parse_args()
    rows=compare(a.semillas,a.rondas)
    report=save(rows,a.out)
    print(json.dumps({'partidas':report['partidas'],'resumen':report['summary']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
