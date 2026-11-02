"""Fase 9: experimento factorial 2^3 apareado sobre economia SINTETICA v2.

No sustituye las seis barajas definitivas ni aprueba valores de balance.
Los cambios son: Situaciones 100%/60%, Perfil 100%/60%, casilla 2/1.
El resultado principal es rondas hasta Casamiento CAPADAS en max_rounds.
"""
from __future__ import annotations
import argparse
import csv
import itertools
import json
import statistics
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from laboratorio.sensibilidad_v2 import StressScenario, run_game

FACTORS=('situation','profile','square')
LEVELS={'situation': (1.0,.6),'profile':(1.0,.6),'square':(2,1)}


def treatment(bits: tuple[int,int,int]) -> StressScenario:
    if len(bits)!=3 or any(v not in (0,1) for v in bits):
        raise ValueError('Se requieren tres factores binarios')
    si,pr,sq=bits
    return StressScenario('F'+''.join(map(str,bits)), LEVELS['situation'][si],
                         adult_square_amount=LEVELS['square'][sq],
                         profile_yield=LEVELS['profile'][pr])


def treatments():
    return tuple((bits,treatment(bits)) for bits in itertools.product((0,1),repeat=3))


def make_runs(*,seeds:int=12,start_seed:int=1,rounds:int=100,
              policies=('planificador','aleatorio'),competitions=(False,True),hand_size=3):
    if seeds<1 or start_seed<1 or rounds<1 or hand_size not in (3,4):
        raise ValueError('Configuración inválida')
    result=[]
    for size in (6,10):
        for seed in range(start_seed,start_seed+seeds):
            for policy in policies:
                for competition in competitions:
                    for bits,scenario in treatments():
                        row=run_game(size,seed,policy,competition,scenario,
                                     rounds=rounds,hand_size=hand_size)
                        row['f_situation'],row['f_profile'],row['f_square']=bits
                        result.append(row)
    return result


def grouped_summary(rows):
    groups=defaultdict(list)
    for row in rows:
        groups[(row['size'],row['policy'],row['competition'],row['scenario'])].append(row)
    out=[]
    for (size,policy,comp,scenario),v in sorted(groups.items()):
        out.append({'size':size,'policy':policy,'competition':comp,'scenario':scenario,
                    'n':len(v),'casamientos':sum(x['won'] for x in v),
                    'pct_casamiento':round(100*sum(x['won'] for x in v)/len(v),1),
                    'rondas_media_cap':round(statistics.mean(x['rounds'] for x in v),3),
                    'rondas_mediana_cap':statistics.median(x['rounds'] for x in v),
                    'sin_progreso_medio':round(statistics.mean(x['no_progress_ratio'] for x in v),4),
                    'parejas_rotas':sum(x['pair_breaks'] for x in v)})
    return out


def paired_effects(rows):
    """Contrastes de efectos factoriales por bloques emparejados.

    Efecto principal: diferencia promedio high-change (1) - reference (0)
    entre cuatro configuraciones de otros factores para cada bloque.
    Interacción:  Δ_AB = Y11 - Y10 - Y01 + Y00, promediado en tercer factor.
    Tres vías: Δ_ABC = Y111-Y110-Y101-Y011+Y100+Y010+Y001-Y000.
    """
    byblock=defaultdict(dict)
    for row in rows:
        key=(row['size'],row['policy'],row['competition'],row['seed'])
        bits=(row['f_situation'],row['f_profile'],row['f_square'])
        if bits in byblock[key]:raise ValueError('Tratamiento repetido por bloque')
        byblock[key][bits]=row
    effects=defaultdict(list)
    for key,obs in byblock.items():
        if set(obs)!=set(itertools.product((0,1),repeat=3)):
            raise ValueError(f'Bloque factorial incompleto: {key}')
        for index,name in enumerate(FACTORS):
            diffs=[]; wins=[]
            for bits in itertools.product((0,1),repeat=2):
                low=list(bits);low.insert(index,0)
                high=low.copy();high[index]=1
                low,high=tuple(low),tuple(high)
                diffs.append(obs[high]['rounds']-obs[low]['rounds'])
                wins.append(int(obs[high]['won'])-int(obs[low]['won']))
            effects[(key[:3],'main',name,'rondas_cap')].append(statistics.mean(diffs))
            effects[(key[:3],'main',name,'victoria_pp')].append(100*statistics.mean(wins))
        for i,j in itertools.combinations(range(3),2):
            other=next(k for k in range(3) if k not in (i,j))
            interaction=[]
            for v in (0,1):
                def val(x,y):
                    bits=[0,0,0];bits[i]=x;bits[j]=y;bits[other]=v
                    return obs[tuple(bits)]['rounds']
                interaction.append(val(1,1)-val(1,0)-val(0,1)+val(0,0))
            effects[(key[:3],'interaction2',FACTORS[i]+'×'+FACTORS[j],'rondas_cap')].append(statistics.mean(interaction))
        def y(a,b,c):return obs[(a,b,c)]['rounds']
        tri=y(1,1,1)-y(1,1,0)-y(1,0,1)-y(0,1,1)+y(1,0,0)+y(0,1,0)+y(0,0,1)-y(0,0,0)
        effects[(key[:3],'interaction3','situation×profile×square','rondas_cap')].append(tri)
    output=[]
    for (strata,kind,name,metric),values in sorted(effects.items(),key=str):
        n=len(values)
        mean=statistics.mean(values)
        std=statistics.stdev(values) if n>1 else 0
        se=std/(n**.5)
        output.append({'size':strata[0],'policy':strata[1],'competition':strata[2],
                       'type':kind,'factor':name,'metric':metric,'blocks':n,
                       'mean':round(mean,4),'sd':round(std,4),
                       'se':round(se,4),'ci95_normal_low':round(mean-1.96*se,4),
                       'ci95_normal_high':round(mean+1.96*se,4)})
    return output


def save(rows,folder:Path,parameters:dict):
    folder.mkdir(parents=True,exist_ok=True)
    if not rows:raise ValueError('Se requieren partidas')
    with (folder/'partidas_factorial_v2.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    report={'disclaimer':'ESCENARIOS SINTÉTICOS: no son mazos oficiales ni estimaciones finales de balance.',
            'metodologia':'Diseño factorial 2^3 completo, bloqueado por semilla/mesa/agente/competencia. Contrastes de rondas limitadas a max_rounds.',
            'parametros':parameters,'runs':len(rows),'summary':grouped_summary(rows),
            'effects':paired_effects(rows)}
    (folder/'analisis_factorial_v2.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    with (folder/'efectos_factoriales_v2.csv').open('w',newline='',encoding='utf-8') as f:
        e=report['effects'];w=csv.DictWriter(f,fieldnames=list(e[0]));w.writeheader();w.writerows(e)
    return report


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--semillas',type=int,default=12)
    ap.add_argument('--desde-semilla',type=int,default=1)
    ap.add_argument('--rondas',type=int,default=100)
    ap.add_argument('--solo-planificador',action='store_true')
    ap.add_argument('--mano',type=int,choices=(3,4),default=3)
    ap.add_argument('--out',type=Path,default=Path('resultados/fase9_factorial'))
    args=ap.parse_args()
    policies=('planificador',) if args.solo_planificador else ('planificador','aleatorio')
    rows=make_runs(seeds=args.semillas,start_seed=args.desde_semilla,rounds=args.rondas,
                   policies=policies,hand_size=args.mano)
    report=save(rows,args.out,{'semillas':args.semillas,'desde_semilla':args.desde_semilla,
                                'limite_rondas':args.rondas,'mano':args.mano,'policies':policies,
                                'factors':LEVELS})
    print(json.dumps({'runs':report['runs'],'output':str(args.out),
                      'groups':len(report['summary']),'effects':len(report['effects'])},ensure_ascii=False))

if __name__=='__main__':main()
