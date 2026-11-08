"""SIMLOG v2.1 para reglas del 08-11-2026.

El SIMLOG v2.0 y las trazas históricas no se reescriben.
"""
from __future__ import annotations

from collections import Counter
import csv
import hashlib
import json
from pathlib import Path

from simulador.simlog_v2 import SIMLogV2, _json


class SIMLogV21(SIMLogV2):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.shared_rounds = []
        self.assignments_by_round = {}

    def end_round_start(self):
        super().end_round_start()
        n = self.engine.round_no
        assignments = {}
        for pid, key in self.engine.round_assignments.items():
            assignments[pid] = (
                (key[0].value, key[1], self.engine._revealed[key].id)
                if key is not None else None
            )
        self.assignments_by_round[n] = assignments
        counts = Counter((value[0], value[1], value[2])
                         for value in assignments.values() if value is not None)
        for (stage, role, card_id), number in sorted(counts.items()):
            revelation = next(
                (ev['Secuencia'] for ev in self.events
                 if ev['Fuente'] == 'motor'
                 and ev['Accion'] == 'situation_revealed'
                 and ev['Ronda'] == n
                 and json.loads(ev['Detalle_JSON']).get('card') == card_id),
                None
            )
            self.shared_rounds.append({
                'Partida': self.run_id, 'Ronda': n, 'Etapa': stage, 'Rol': role,
                'Carta_compartida_ID': card_id, 'Participantes_asignados': number,
                'Participantes_que_resolvieron': 0,
                'Elecciones_A': 0, 'Elecciones_B': 0,
                'Evento_revelacion': revelation,
            })

    def end_turn(self, outcome):
        pid = outcome.active
        n = outcome.round_no
        assignment = self.assignments_by_round[n][pid]
        related = self.events[self._event_start_idx:]
        childhood = next((json.loads(ev['Detalle_JSON']) for ev in related
                          if ev['Fuente'] == 'motor'
                          and ev['Accion'] == 'childhood_route'), None)
        context = next((json.loads(ev['Detalle_JSON']) for ev in related
                        if ev['Fuente'] == 'motor'
                        and ev['Accion'] == 'situation_context'), None)
        destination_issues = [
            json.loads(ev['Detalle_JSON'])
            for ev in related
            if ev['Fuente'] == 'economia' and ev['Accion'] == 'issue'
            and json.loads(ev['Detalle_JSON']).get('source', '').startswith('infancia_destino_')
            and json.loads(ev['Detalle_JSON']).get('player') == pid
        ]
        super().end_turn(outcome)
        row = self.turns[-1]
        row['Etapa_al_inicio_ronda'] = self.engine.round_start_stages[pid].value
        row['Rol_al_inicio_ronda'] = assignment[1] if assignment else self.engine.players[pid].role
        row['Situacion_grupo_etapa'] = assignment[0] if assignment else None
        row['Situacion_grupo_rol'] = assignment[1] if assignment else None
        row['Carta_compartida_ID'] = assignment[2] if assignment else None
        row['Recursos_antes_AB_JSON'] = _json(context.get('resources')) if context else None
        row['Posicion_antes_AB'] = context.get('position') if context else None
        row['Recursos_casillero_JSON'] = _json(destination_issues)
        row['UTN_retorno_pendiente'] = self.engine.players[pid].utn_return_pending
        if childhood is not None:
            row['Dado'] = childhood.get('die')
            row['Ruta_JSON'] = _json(childhood['visited'])
            row['Pasos_consumidos'] = childhood['consumed']
            row['Pasos_descartados'] = childhood['discarded']
            row['Tipo_movimiento_infancia'] = childhood['kind']
        else:
            row['Tipo_movimiento_infancia'] = None
        if assignment and row['Carta_ID'] is not None:
            if row['Carta_ID'] != assignment[2]:
                raise AssertionError('La situación resuelta no coincide con la asignación compartida')
            shared = next(v for v in self.shared_rounds
                          if v['Ronda'] == n and v['Etapa'] == assignment[0]
                          and v['Rol'] == assignment[1])
            shared['Participantes_que_resolvieron'] += 1
            letter = row['Desenlace_elegido']
            if letter in ('A', 'B'):
                shared[f'Elecciones_{letter}'] += 1

    def validate(self):
        super().validate()
        for row in self.turns:
            assignment = self.assignments_by_round[row['Ronda']][row['Jugador']]
            if assignment is not None:
                if row['Carta_ID'] != assignment[2]:
                    raise AssertionError('Carta A/B diferente dentro de la cohorte de ronda')
                if row['Situacion_grupo_etapa'] != assignment[0]:
                    raise AssertionError('La etapa de la situación no es la fijada al inicio')
            elif row['Carta_ID'] is not None:
                raise AssertionError('Situación resuelta sin asignación al inicio de ronda')
        for group in self.shared_rounds:
            if group['Participantes_que_resolvieron'] > group['Participantes_asignados']:
                raise AssertionError('Se resolvió una Situación más veces que participantes')
            if group['Elecciones_A'] + group['Elecciones_B'] != group['Participantes_que_resolvieron']:
                raise AssertionError('Cada participante debe seleccionar A o B')
        for row in self.turns:
            if row['Etapa_al_inicio_ronda'] != 'Infancia':
                continue
            sequence = json.loads(row['Eventos_ID_JSON'])
            ids = {e['Secuencia']: e for e in self.events if e['Secuencia'] in sequence}
            casilleros = [e for e in ids.values() if e['Fuente'] == 'economia'
                          and e['Accion'] == 'issue'
                          and json.loads(e['Detalle_JSON']).get('source', '').startswith('infancia_destino_')]
            situation = [e for e in ids.values() if e['Accion'] == 'situation_resolved']
            if len(casilleros) > 1:
                raise AssertionError('Infancia cobró varios casilleros en un turno')
            if casilleros and situation and casilleros[0]['Secuencia'] >= situation[0]['Secuencia']:
                raise AssertionError('Infancia debe cobrar antes de Situación')

    def write(self, out, *, status, summary):
        self.validate()
        manifest = super().write(out, status=status, summary=summary)
        path = Path(out) / 'situaciones_por_ronda.csv'
        with path.open('w', encoding='utf-8-sig', newline='') as f:
            columns = ['Partida', 'Ronda', 'Etapa', 'Rol', 'Carta_compartida_ID',
                       'Participantes_asignados', 'Participantes_que_resolvieron',
                       'Elecciones_A', 'Elecciones_B', 'Evento_revelacion']
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            writer.writerows(self.shared_rounds)
        manifest['schema'] = 'SIMLOG-2.1'
        manifest['ruleset'] = 'especificacion-integral-2026-11-08'
        manifest['situaciones_compartidas'] = 'una_por_etapa_rol_ronda'
        manifest['infancia'] = 'destino_exacto_1A3_2P2_3A3_4P2_5K1_6A3'
        manifest['counts'][path.name] = len(self.shared_rounds)
        manifest['file_sha256'][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        (Path(out) / 'manifest.json').write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + '\n',
            encoding='utf-8',
        )
        return manifest
