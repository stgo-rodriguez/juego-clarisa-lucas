"""Diagnóstico de interacciones: muestras deterministas, sin alterar motor."""
from __future__ import annotations
from dataclasses import replace
from collections import Counter
from pathlib import Path
import json
from laboratorio.comparacion import escenario_base, ejecutar
from laboratorio.interacciones import trazar_interacciones
from simulador.economia import EconomyConfig


def diagnosticar(muestra=25):
    escenarios = {
        'base': EconomyConfig(),
        'restrictiva': EconomyConfig(perfiles_pct=50, cartas_ganancias_pct=50,
                                     cartas_perdidas_pct=150, infancia_pct=50),
        'abundante': EconomyConfig(perfiles_pct=150, cartas_ganancias_pct=150,
                                   cartas_perdidas_pct=50, infancia_pct=150),
    }
    lotes = []
    for j in (6,10):
        for titulo, economia in escenarios.items():
            cfg = replace(escenario_base(j,muestra), economia=economia)
            resultado = ejecutar(cfg)
            categorias = Counter()
            tipo = Counter()
            duelos = 0
            inconsistencias = []
            for n,fila in enumerate(resultado['filas'],1):
                r = trazar_interacciones(cfg,n,fila)
                inconsistencias.extend(r['errores_auditoria'])
                inconsistencias.extend(r['errores_motor'])
                duelos += r['duelos']
                for e in r['eventos']:
                    categorias[e['categoria']] += 1
                    tipo[e['evento']] += 1
            lotes.append({
                'jugadores': j, 'escenario': titulo, 'partidas': muestra,
                'finalizadas': sum(int(f['terminada']) for f in resultado['filas']),
                'duelos': duelos, 'eventos': sum(categorias.values()),
                'por_categoria': dict(categorias), 'por_evento':dict(tipo),
                'inconsistencias': inconsistencias,
            })
    return {'muestras':sum(x['partidas'] for x in lotes),'lotes':lotes,
            'inconsistencias':sum(len(x['inconsistencias']) for x in lotes)}


if __name__ == '__main__':
    result=diagnosticar(25)
    ruta=Path(__file__).resolve().parents[1]/'docs'/'DIAGNOSTICO_INTERACCIONES_FASE4_3.json'
    ruta.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({'muestras':result['muestras'],'inconsistencias':result['inconsistencias'],
          'lotes':[(x['jugadores'],x['escenario'],x['duelos'],x['eventos']) for x in result['lotes']]},ensure_ascii=False))
