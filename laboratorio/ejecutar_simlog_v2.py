"""Exportar partidas completas a SIMLOG v2.0 con identificadores estables.

Ejemplo:
python -m laboratorio.ejecutar_simlog_v2 --semillas 1 --rondas 80 --out resultados/simlog_v2
Produce subcarpetas por partida con Turnos, Eventos, Estados, Hitos y A/B,
y consolida preferencias sin confundir la opción social con el Movimiento.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
import csv
import hashlib
from itertools import product
import json
from pathlib import Path

from laboratorio.calibracion_cartas_v2 import variants
from laboratorio.experimento_mazos_propuestos_v2 import run_proposal
from simulador.mazos_propuestos_v2 import BalanceVariant
from simulador.simlog_v2 import SCHEMA_VERSION


def _read_csv(path:Path) -> list[dict]:
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))


def aggregate_ab(root:Path, runs:list[dict]) -> list[dict]:
    group=defaultdict(lambda: {'A':0,'B':0,'OTRO':0,'partidas':set()})
    for run in runs:
        for typ,filename in (('situacion','preferencias_situaciones.csv'),
                             ('movimiento','preferencias_movimientos.csv')):
            for item in _read_csv(root / run['run_id'] / filename):
                key=(typ,item['Rol'],item['Etapa'],item['Carta_ID'],item['Carta_fuente_ID'],run['policy'])
                x=group[key]
                for letter,col in [('A','Elecciones_A'),('B','Elecciones_B'),('OTRO','Otras_resoluciones')]:
                    x[letter]+=int(item[col])
                x['partidas'].add(run['run_id'])
    rows=[]
    for (typ,role,stage,card,source,policy),v in sorted(group.items()):
        a,b,other=v['A'],v['B'],v['OTRO']
        rows.append({'Tipo':typ,'Rol':role,'Etapa':stage,'Carta_ID':card,'Carta_fuente_ID':source,
                     'Politica':policy,'Partidas_con_carta':len(v['partidas']),
                     'Veces_resuelta':a+b+other,'Elecciones_A':a,'Elecciones_B':b,
                     'Otras_resoluciones':other,
                     'Porcentaje_A_sobre_AB':round(100*a/(a+b),2) if a+b else None,
                     'Porcentaje_B_sobre_AB':round(100*b/(a+b),2) if a+b else None})
    return rows


def write_csv(path:Path,rows:list[dict]):
    if not rows:raise ValueError('No hay datos para exportación')
    with path.open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def execute(*,out:Path,seeds:tuple[int,...],rounds:int,sizes:tuple[int,...],
            policies:tuple[str,...],competitions:tuple[bool,...],scenario:str,
            hand_size:int=3):
    if not seeds or any(type(s) is not int or s<1 for s in seeds):
        raise ValueError('Las semillas deben ser enteros positivos')
    if rounds<1 or any(n not in (6,10) for n in sizes) or any(p not in ('aleatorio','planificador') for p in policies):
        raise ValueError('Parámetros de simulación inválidos')
    if scenario=='original':
        balance=BalanceVariant()
    else:
        balance=variants()[scenario]  # ValueError/KeyError para escenarios no definidos
    out.mkdir(parents=True,exist_ok=True)
    runs=[]
    for size,seed,policy,competition in product(sizes,seeds,policies,competitions):
        run_id=f'simlog2_{scenario}_n{size}_s{seed}_{policy}_c{int(competition)}_h{hand_size}'
        report=run_proposal(size,seed,policy,competition,
                            rounds=rounds,hand_size=hand_size,balance=balance,
                            simlog_dir=out/run_id,simlog_run_id=run_id)
        manifest=json.loads((out/run_id/'manifest.json').read_text(encoding='utf-8'))
        assert manifest['counts']['turnos.csv']==report['turns_executed']
        runs.append({'run_id':run_id,'size':size,'seed':seed,'policy':policy,
                     'competition':competition,'rounds':report['rounds'],
                     'won':report['won'],'stop':report['stop'],
                     'turns':report['turns_executed'],
                     'events':manifest['counts']['eventos.csv'],
                     'source':'propuestas_documentadas_NO_APROBADAS'})
    write_csv(out/'partidas.csv',runs)
    prefs=aggregate_ab(out,runs)
    write_csv(out/'preferencias_por_carta.csv',prefs)
    index={'schema':SCHEMA_VERSION,'status':'EXPERIMENTAL_NO_APROBADO',
           'round_limit':rounds,'scenario':scenario,'hand_size':hand_size,
           'n_games':len(runs),'turns':sum(x['turns'] for x in runs),
           'events':sum(x['events'] for x in runs),
           'source_dataset':'Fase 10 - 78 cartas históricas y 30 propuestas adultas',
           'file_hashes':{f:hashlib.sha256((out/f).read_bytes()).hexdigest()
                          for f in ('partidas.csv','preferencias_por_carta.csv')}}
    (out/'indice_simlog.json').write_text(json.dumps(index,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return index


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=Path('resultados/simlog_v2'))
    parser.add_argument('--semillas',type=int,default=1)
    parser.add_argument('--rondas',type=int,default=100)
    parser.add_argument('--mesas',nargs='+',type=int,choices=(6,10),default=(6,10))
    parser.add_argument('--agentes',nargs='+',choices=('aleatorio','planificador'),default=('aleatorio','planificador'))
    parser.add_argument('--competencia',choices=('si','no','ambas'),default='si')
    parser.add_argument('--escenario',choices=('original',*variants().keys()),default='original')
    parser.add_argument('--mano',type=int,choices=(3,4),default=3)
    args=parser.parse_args()
    competitions={'si':(True,),'no':(False,),'ambas':(False,True)}[args.competencia]
    result=execute(out=args.out,seeds=tuple(range(1,args.semillas+1)),rounds=args.rondas,
                   sizes=tuple(args.mesas),policies=tuple(args.agentes),
                   competitions=competitions,scenario=args.escenario,hand_size=args.mano)
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()