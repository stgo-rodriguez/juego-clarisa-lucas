"""Benchmark descriptivo y reproducible de la interfaz; no implica un SLA.

Uso: python -m laboratorio.benchmark_fase7 --json
Las duraciones dependen de CPU, RAM, carga del sistema y versión de Python.
"""
from __future__ import annotations
import argparse
from dataclasses import replace
import json
from time import perf_counter
from laboratorio.comparacion import ejecutar, escenario_base, comparar
from laboratorio.sensibilidad import GridConfig, ejecutar_grilla
from simulador.economia import EconomyConfig


def medir(partidas: int = 20) -> dict:
    if type(partidas) is not int or not 5 <= partidas <= 100:
        raise ValueError('El benchmark admite entre 5 y 100 partidas por escenario')
    base_cfg = escenario_base(6, partidas)
    var_cfg = replace(base_cfg, id='benchmark-90-110',
                      economia=EconomyConfig(cartas_ganancias_pct=90, cartas_perdidas_pct=110))
    start = perf_counter()
    a = ejecutar(base_cfg)
    b = ejecutar(var_cfg)
    comparar(a, b)
    ab_seconds = perf_counter() - start

    cfg = GridConfig(jugadores=6, partidas=partidas, valores_x=(90, 100, 110),
                     valores_y=(90, 100, 110), remuestreos=100)
    start = perf_counter()
    grid = ejecutar_grilla(cfg, ejecutar)
    grid_seconds = perf_counter() - start
    return {'partidas_por_escenario': partidas,
            'comparacion_ab': {'partidas_ejecutadas': partidas * 2,
                               'segundos': round(ab_seconds, 3)},
            'matriz_3x3': {'celdas': grid['n_celdas'],
                           'partidas_maximas_presupuestadas': partidas * 10,
                           'segundos': round(grid_seconds, 3)},
            'advertencia': 'Tiempos orientativos de este equipo; no equivalen a rendimiento del Mac del usuario.'}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Medición local de rendimiento')
    parser.add_argument('--partidas', type=int, default=20)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    data = medir(args.partidas)
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(f"A/B ({data['comparacion_ab']['partidas_ejecutadas']} partidas): "
              f"{data['comparacion_ab']['segundos']} s")
        print(f"Matriz 3x3: {data['matriz_3x3']['segundos']} s")
        print(data['advertencia'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
