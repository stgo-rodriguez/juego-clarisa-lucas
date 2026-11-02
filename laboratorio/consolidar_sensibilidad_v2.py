"""Consolida lotes de Fase 8 y verifica 1 combinación por cada semilla."""
from __future__ import annotations
import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from laboratorio.sensibilidad_v2 import SCENARIOS, summarize, paired_differences


def merge(inputs: list[Path], output: Path):
    rows=[]
    for file in inputs:
        with file.open(encoding='utf-8',newline='') as f:
            for row in csv.DictReader(f):
                cast={
                    'size':int,'seed':int,'hand_size':int,'max_rounds':int,
                    'rounds':int,'turns_executed':int,'turns_without_durable_progress':int,
                    'titles_awarded':int,'passports_awarded':int,'final_titles':int,
                    'final_passports':int,'adults_final':int,'pair_formations':int,
                    'house_purchases':int,'house_transfers':int,'duels':int,
                    'duels_hito':int,'duels_perfil':int,'duels_ordinarios':int,
                    'auctions':int,'bids':int,'auctions_awarded':int,
                    'free_resources_lost':int,'pair_breaks':int,
                    'extra_loss':int,'adult_square_amount':int,
                    'situation_yield':float,'profile_yield':float,
                    'loss_fraction':float,'no_progress_ratio':float,
                }
                for key,func in cast.items():row[key]=func(row[key])
                for key in ('won','competition','first_pair_won','first_pair_formed','synthetic_scenarios'):
                    if row[key] not in ('True','False'):raise ValueError(f'Booleano inválido {key}')
                    row[key]=row[key]=='True'
                row['first_adult_round']=int(row['first_adult_round']) if row['first_adult_round'] else None
                rows.append(row)
    index={(r['size'],r['seed'],r['policy'],r['competition'],r['scenario']) for r in rows}
    if len(index)!=len(rows):raise ValueError('Alguna combinación se duplicó')
    keys={(r['size'],r['seed'],r['policy'],r['competition']) for r in rows}
    expected={s.id for s in SCENARIOS}
    for size,seed,policy,competition in keys:
        present={r['scenario'] for r in rows if (r['size'],r['seed'],r['policy'],r['competition'])==(size,seed,policy,competition)}
        if present != expected:raise ValueError('Falta una o más condiciones por semilla')
    seeds={r['seed'] for r in rows}
    if len(rows)!=len(seeds)*2*2*2*len(SCENARIOS):
        raise ValueError('Matriz no balanceada entre tamaños, bots, competencia y escenarios')
    if any(r['stop'] not in ('round_limit','marriage') for r in rows):
        raise ValueError('Estado terminal no clasificado')
    rows.sort(key=lambda r:(r['size'],r['seed'],r['policy'],r['competition'],r['scenario']))
    output.mkdir(parents=True,exist_ok=True)
    with (output/'partidas_sensibilidad_v2.csv').open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    report={
        'advertencia':'ECONOMÍA SINTÉTICA EXPERIMENTAL; no se infiere balance definitivo de Clarisa & Lucas v2.0',
        'casos':len(rows),'semillas':len(seeds),'rondas_max':max(r['max_rounds'] for r in rows),
        'escenarios':[s.__dict__ for s in SCENARIOS],
        'terminaciones':dict(Counter(r['stop'] for r in rows)),
        'resultados':summarize(rows),
        'deltas_pareados':paired_differences(rows),
    }
    (output/'resumen_sensibilidad_v2.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--inputs',nargs='+',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    report=merge(args.inputs,args.out)
    print(json.dumps({'casos':report['casos'],'terminaciones':report['terminaciones']},indent=2,ensure_ascii=False))


if __name__=='__main__':main()
