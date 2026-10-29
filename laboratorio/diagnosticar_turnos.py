"""Ejecuta chequeo determinista F4.4 de actividad en condiciones variadas."""
from __future__ import annotations
from collections import Counter
from dataclasses import replace
from datetime import datetime,timezone
import json
from pathlib import Path
from laboratorio.comparacion import escenario_base,ejecutar
from laboratorio.turnos import trazar_turnos
from simulador.economia import EconomyConfig


def diagnosticar(n=25):
    cases = [
        ('base_6j',6,EconomyConfig()),
        ('base_10j',10,EconomyConfig()),
        ('escasa_6j',6,EconomyConfig(perfiles_pct=50,cartas_ganancias_pct=50,cartas_perdidas_pct=150,infancia_pct=50)),
        ('escasa_10j',10,EconomyConfig(perfiles_pct=50,cartas_ganancias_pct=50,cartas_perdidas_pct=150,infancia_pct=50)),
        ('abundante_6j',6,EconomyConfig(perfiles_pct=150,cartas_ganancias_pct=150,cartas_perdidas_pct=50,infancia_pct=150)),
        ('abundante_10j',10,EconomyConfig(perfiles_pct=150,cartas_ganancias_pct=150,cartas_perdidas_pct=50,infancia_pct=150)),
    ]
    report=[]
    for name,players,econ in cases:
        cfg=replace(escenario_base(players,n),economia=econ)
        batch=ejecutar(cfg)
        traced=[trazar_turnos(cfg,i,fila) for i,fila in enumerate(batch['filas'],1)]
        errors=[{'partida':d['partida'],'errores':d['errores_auditoria']+d['errores_motor']}
                for d in traced if d['errores_auditoria'] or d['errores_motor']]
        unknown=Counter(x for d in traced for t in d['turnos_detalle'] for x in t['eventos_sin_clasificar'])
        report.append({'escenario':name,'jugadores':players,'partidas':len(traced),
                       'errores':errors,'eventos_no_clasificados':dict(unknown),
                       'turnos':sum(d['turnos'] for d in traced),
                       'turnos_con_decision':sum(d['turnos_con_decision'] for d in traced),
                       'decisiones_ejecutadas':sum(d['decisiones_ejecutadas'] for d in traced),
                       'familias_disponibles_media':round(sum(d['familias_disponibles_por_turno']*d['turnos'] for d in traced)/sum(d['turnos'] for d in traced),3),
                       'censuradas':sum(1-int(x['terminada']) for x in batch['filas'])})
    return {'reporte':'Fase 4.4 - observación pasiva','total_partidas':sum(x['partidas'] for x in report),
            'total_errores':sum(len(x['errores']) for x in report),'escenarios':report}

if __name__=='__main__':
    p=Path(__file__).resolve().parents[1]/'docs'/'DIAGNOSTICO_TURNOS_FASE4_4.json'
    d=diagnosticar()
    p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(d,ensure_ascii=False,indent=2))
    if d['total_errores']:raise SystemExit(1)
