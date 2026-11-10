"""Auditar generación de recursos y diversidad en resultados SIMLOG v2.1."""
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import Counter
from pathlib import Path

RESOURCES = ('A', 'P', 'K', 'M')
STAGES = ('Infancia', 'Juventud', 'Adultez')
TARGET = {'Infancia': [50, 30, 20, 0], 'Juventud': [17, 25, 42, 17],
          'Adultez': [27, 18, 9, 45]}


def read(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        yield from csv.DictReader(stream)


def write(path, rows):
    if not rows:
        return
    with Path(path).open('w', encoding='utf-8-sig', newline='') as stream:
        w = csv.DictWriter(stream, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def classify(source, turn):
    if source.startswith('infancia_destino_'):
        return 'Infancia', 'Casilleros'
    if source in ('juventud_universidad', 'juventud_tramite'):
        return 'Juventud', 'Casilleros'
    if source == 'vuelta_juventud':
        return 'Juventud', 'Perfil'
    if source in ('colocacion_inicial_dublin', 'caida_perfil_adultez'):
        return 'Adultez', 'Perfil'
    if source == 'adultez_casillero':
        return 'Adultez', 'Casilleros'
    if source == 'situacion_vigente_premio':
        return (turn['Etapa_situacion'] if turn else None), 'Cartas'
    return (turn['Etapa_situacion'] if turn else None), f'Otras: {source}'


def main(root):
    games = list(read(root / 'partidas.csv'))
    generated = Counter()
    turns_by_stage = Counter()
    unknown = []
    for game in games:
        folder = root / 'trazas' / f"n{game['size']}_s{game['seed']}"
        if not (folder/'turnos.csv').exists():
            if game['stop'] != 'rule_pending':
                raise AssertionError(f'Falta traza de la partida {game["seed"]}')
            continue
        turn_map = {int(row['Turno_global']): row for row in read(folder / 'turnos.csv')}
        for row in turn_map.values():
            if row['Etapa_situacion'] in STAGES:
                turns_by_stage[row['Etapa_situacion']] += 1
        for row in read(folder / 'eventos.csv'):
            if row['Accion'] != 'issue':
                continue
            detail = json.loads(row['Detalle_JSON'])
            if detail['source'] == 'conversion_bancaria':
                continue
            turn = turn_map.get(int(row['Turno_global'])) if row['Turno_global'] else None
            stage, mechanism = classify(detail['source'], turn)
            if stage not in STAGES or detail['resource'] not in RESOURCES:
                unknown.append((stage, detail['source'], detail['resource']))
                continue
            generated[stage, mechanism, detail['resource']] += detail['amount']
    if unknown:
        raise AssertionError(f"Producciones sin clasificar: {len(unknown)}, ejemplos {unknown[:5]}")
    totals = Counter()
    source_totals = Counter()
    for (stage, mechanism, resource), n in generated.items():
        totals[stage, resource] += n
        source_totals[stage, mechanism] += n
    economy = []
    for stage in STAGES:
        all_stage = sum(totals[stage, r] for r in RESOURCES)
        for i, r in enumerate(RESOURCES):
            amount = totals[stage, r]
            economy.append({
                'Etapa': stage, 'Recurso': r, 'Generado': amount,
                'Porcentaje': round(100 * amount / all_stage, 2) if all_stage else 0,
                'Objetivo_pct': TARGET[stage][i],
                'Por_turno': round(amount / turns_by_stage[stage], 3) if turns_by_stage[stage] else 0,
                'Total_etapa': all_stage,
            })
    breakdown = []
    for stage in STAGES:
        total = sum(totals[stage, r] for r in RESOURCES)
        for mechanism in sorted({k for s, k in source_totals if s == stage}):
            quantities = [generated[stage, mechanism, r] for r in RESOURCES]
            breakdown.append({
                'Etapa': stage, 'Mecanismo': mechanism,
                'Amor': quantities[0], 'Personalidad': quantities[1],
                'Conocimiento': quantities[2], 'Dinero': quantities[3],
                'Total': sum(quantities),
                'Participacion_pct': round(100 * sum(quantities) / total, 2) if total else 0,
            })
    write(root / 'balance_por_etapa.csv', economy)
    write(root / 'balance_por_mecanismo.csv', breakdown)
    groups = (list(read(root / 'diversidad_decisiones_por_grupo.csv'))
              if (root / 'diversidad_decisiones_por_grupo.csv').is_file() else [])
    first = []
    for size in sorted({int(g['size']) for g in games}):
        selected = [g for g in groups if int(g['size']) == size and
                    g['etapa'] == 'Infancia' and int(g['ronda']) == 1 and
                    int(g['participantes']) >= 2]
        first.append({
            'Mesa': size, 'Grupos': len(selected),
            'Contextos_distintos': sum(int(g['recursos_diversos']) for g in selected),
            'Ambas_AB': sum(int(g['ambas_opciones']) for g in selected),
            'Ambas_AB_pct': (round(100 * sum(int(g['ambas_opciones']) for g in selected) / len(selected), 2)
                                  if selected else None),
        })
    write(root / 'primera_ronda_por_mesa.csv', first)
    durations = []
    for size in sorted({int(g['size']) for g in games}):
        selected=[g for g in games if int(g['size'])==size]
        cohort = [int(g['rounds']) for g in selected if g['stop']=='marriage']
        ordered = sorted(cohort)
        durations.append({
            'Mesa': size, 'Partidas': len(selected),
            'Casamientos':len(cohort),
            'Bloqueadas_por_regla':sum(g['stop']=='rule_pending' for g in selected),
            'Limite_rondas':sum(g['stop']=='round_limit' for g in selected),
            'Mediana_rondas': statistics.median(cohort) if cohort else None,
            'P80_rondas': ordered[math.ceil(len(ordered) * .8) - 1] if cohort else None,
            'Media_rondas': round(statistics.mean(cohort), 2) if cohort else None,
        })
    write(root / 'duracion_por_mesa.csv', durations)
    output = {'duracion': durations, 'primera_ronda': first,
              'economia_por_etapa': economy, 'fuentes': breakdown}
    (root / 'auditoria_economica.json').write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('AUDITORIA_SIMLOG_V21_INICIO')
    print(json.dumps(output, ensure_ascii=False, indent=2))
    print('AUDITORIA_SIMLOG_V21_FIN')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    main(parser.parse_args().out)
