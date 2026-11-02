"""Consolida bloques experimentales de calibración sin perder controles apareados."""
import argparse
import csv
from pathlib import Path
from laboratorio.calibracion_cartas_v2 import write_report, variants


def consolidate(inputs:list[Path],output:Path,*,seeds:int,rounds:int):
    rows=[]
    seen=set()
    for input_path in inputs:
        with input_path.open(encoding='utf-8',newline='') as stream:
            for row in csv.DictReader(stream):
                for col in ('size','seed','rounds','turns_executed','card_gains_units',
                            'card_losses_units','situations_resolved','situations_adult',
                            'individual_choices','conflicts','cooperations','social_auctions',
                            'auctions_awarded','bids','duels','pairs_formed','houses_bought',
                            'profile_activations','round_limit'):
                    row[col]=int(row[col])
                for col in ('won','competition','experimental'):
                    row[col]=row[col].lower()=='true'
                for col in ('early_gain_factor','adult_gain_factor','loss_multiplier','no_progress_ratio'):
                    row[col]=float(row[col])
                key=tuple(row[k] for k in ('size','seed','policy','competition','scenario'))
                if key in seen:raise ValueError('Partida duplicada '+str(key))
                seen.add(key)
                rows.append(row)
    expected=seeds*2*2*2*len(variants())
    if len(rows)!=expected:raise ValueError(f'Se esperaban {expected} registros, llegaron {len(rows)}')
    for size in (6,10):
        for seed in range(1,seeds+1):
            for policy in ('aleatorio','planificador'):
                for competition in (False,True):
                    if sum((r['size']==size and r['seed']==seed and r['policy']==policy and
                            r['competition']==competition) for r in rows)!=len(variants()):
                        raise ValueError('Bloque incompleto')
    rows.sort(key=lambda r:(r['size'],r['policy'],r['competition'],r['seed'],r['scenario']))
    return write_report(rows,output,seeds=seeds,rounds=rounds)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('inputs',nargs='+',type=Path)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--semillas',type=int,default=20)
    p.add_argument('--rondas',type=int,default=100)
    x=p.parse_args()
    r=consolidate(x.inputs,x.out,seeds=x.semillas,rounds=x.rondas)
    print({'partidas':r['total_games'],'casamientos':r['marriages'],'truncadas':r['timeouts']})

if __name__=='__main__':main()