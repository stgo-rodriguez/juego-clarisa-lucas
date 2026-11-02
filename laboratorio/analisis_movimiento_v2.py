"""Auditoría exhaustiva (sin Monte Carlo) de movimiento interno adulto v2.0.

Genera CSV de todas las trayectorias para las 25 posiciones, distancias 1..6
 y direcciones iniciales válidas, más resumen JSON. No simula recursos, mazos
 ni probabilidades; enumera alternativas legales con igual unidad de conteo.
"""
from __future__ import annotations

from collections import Counter
import argparse
import csv
import json
from pathlib import Path

from simulador.movimiento_v2 import Coord, cell_at, valid_directions, walk_adult


def generar_transiciones() -> list[dict]:
    rows = []
    for r in range(1, 6):
        for c in range(1, 6):
            origin = Coord(r, c)
            for distance in range(1, 7):
                for direction in valid_directions(origin):
                    result = walk_adult(origin, distance, direction)
                    rows.append({
                        'origen_fila': r, 'origen_columna': c,
                        'distancia': distance, 'direccion': direction,
                        'destino_fila': result.destination.row,
                        'destino_columna': result.destination.col,
                        'activacion': result.activation,
                        'rebotes': len(result.reflections),
                        'pasos_consumidos': result.consumed,
                        'recorrido': ';'.join(f'{p.row},{p.col}' for p in result.visited),
                    })
    assert len(rows) == 864, f'Número inesperado de trayectorias: {len(rows)}'
    return rows


def resumen(rows: list[dict], ingreso: Coord = Coord(5, 3)) -> dict:
    entry = [r for r in rows if r['origen_fila'] == ingreso.row and r['origen_columna'] == ingreso.col]
    reachable = {(r['destino_fila'], r['destino_columna']) for r in entry}
    central = [
        {'distancia': r['distancia'], 'direccion': r['direccion']}
        for r in entry if r['activacion'] == 'Casa'
    ]
    return {
        'tipo': 'enumeracion_geometrica_sin_azar',
        'total_origenes': 25,
        'distancias_probadas': [1, 2, 3, 4, 5, 6],
        'total_trayectorias': len(rows),
        'ingreso': {'fila': ingreso.row, 'columna': ingreso.col},
        'movimientos_desde_ingreso': len(entry),
        'casilleros_distintos_desde_ingreso': len(reachable),
        'activaciones_desde_ingreso': dict(sorted(Counter(r['activacion'] for r in entry).items())),
        'rutas_ingreso_a_casa': central,
        'sin_incluir': ['situaciones', 'manos', 'recursos', 'victorias', 'requisitos de Casa/Casamiento'],
    }


def guardar(output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = generar_transiciones()
    report = resumen(rows)
    with (output_dir / 'transiciones_adultez_v2.csv').open('w', encoding='utf-8', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (output_dir / 'resumen_geometria_v2.json').write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=Path('resultados/movimiento_v2'))
    args = parser.parse_args()
    print(json.dumps(guardar(args.out), ensure_ascii=False, indent=2))
