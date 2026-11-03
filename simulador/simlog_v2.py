"""SIMLOG v2.0: traza persistente, auditable y optativa de Clarisa & Lucas.

Sin cambiar reglas, dados ni agentes. Se instala como observador de los
registros append() existentes para preservar el ORDEN REAL entre módulos.
Las fuentes v0.1/v0.2 de cartas y los supuestos v2.x permanecen experimentales.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import asdict, is_dataclass
import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from simulador.economia_v2 import EconomyV2, RESOURCES
from simulador.movimiento_v2 import Coord, cell_at, walk_adult
from simulador.turnos_v2 import AdultChoice, PlayerState, RoundEngine, Stage, TurnOutcome

SCHEMA_VERSION = 'SIMLOG-2.0'


def _safe(value: Any) -> Any:
    if is_dataclass(value):
        return _safe(asdict(value))
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_safe(v) for v in value]
    if isinstance(value, Coord):
        return {'fila': value.row, 'columna': value.col}
    if hasattr(value, 'value') and isinstance(value.value, str):
        return value.value
    if value is None or type(value) in (int, float, bool, str):
        return value
    return str(value)


def _json(value: Any) -> str:
    return json.dumps(_safe(value), ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def _position(p: Any) -> str:
    if isinstance(p, Coord):
        return f'{p.row},{p.col}'
    return str(p)


class _ObservedList(list):
    """Lista compatible que notifica append sin reordenar ni consumir RNG."""
    def __init__(self, contents: list, observer: 'SIMLogV2', source: str):
        super().__init__(contents)
        self.observer, self.source = observer, source

    def append(self, item: Any) -> None:
        super().append(item)
        self.observer._event(self.source, item)


class SIMLogV2:
    """Observador del juego; una fila por turno y estados de TODOS los jugadores.

    Uso: attach_hooks(hooks), begin_round(), engine.start_round(),
    end_round_start(), begin_turn(pid), engine.play_turn(...), end_turn(result),
    end_round(), write(out_dir). No imprime ni modifica parámetros de partida.
    """

    def __init__(self, engine: RoundEngine, eco: EconomyV2, profiles: object,
                 resolver: object, interactions: object, auctions: object,
                 controller: object, *, run_id: str, seed: int, policy: str,
                 competition: bool, round_limit: int, catalog: dict,
                 balance: object):
        if not run_id or '/' in run_id or '\\' in run_id:
            raise ValueError('ID de partida vacío o inseguro')
        self.engine, self.eco, self.profiles = engine, eco, profiles
        self.resolver = resolver
        self.run_id, self.seed = run_id, seed
        self.policy, self.competition = policy, competition
        self.round_limit = round_limit
        self.balance = _safe(balance)
        self._title = {}
        self._option_text = {}
        for x in catalog['historical_78']:
            if x['stage'] in ('Infancia', 'Juventud'):
                for role in ('C', 'L'):
                    physical = f'{x["id"][0]}-{role}-{x["id"]}'
                    self._title[physical] = (x['id'], x['title'])
                    self._option_text[physical] = {'A':x['text_a'], 'B':x['text_b']}
        for x in catalog['adult_proposals_30']:
            self._title[x['id']] = (x['id'], x['title'])
            self._option_text[x['id']] = {'description':x['text'], 'family':x['family']}
        self._streams = {}
        for src, owner in (('motor', engine), ('economia', eco),
                           ('situacion', resolver), ('duelo', interactions),
                           ('subasta', auctions), ('competencia', controller)):
            original = owner.events
            if isinstance(original, _ObservedList):
                raise ValueError('SIMLOG no permite instrumentación duplicada')
            owner.events = _ObservedList(original, self, src)
            self._streams[src] = owner
        self.events: list[dict] = []
        self.turns: list[dict] = []
        self.states: list[dict] = []
        self.global_states: list[dict] = []
        self.milestones: list[dict] = []
        self.rounds: list[dict] = []
        self._current_turn: int | None = None
        self._active: int | None = None
        self._phase = 'initialization'
        self._before: dict | None = None
        self._world_before: dict | None = None
        self._round_before: dict | None = None
        self._movement_decision: AdultChoice | None = None
        self._route: dict | None = None
        self._event_start_idx: int = 0
        self._hook_attached = False
        self._run_finished = False
        self._audit()

    def _audit(self) -> None:
        self.eco.audit()
        self.profiles.audit()
        self.engine.validate()

    def _event(self, stream: str, payload: Any) -> None:
        p = deepcopy(payload)
        data = p if isinstance(p, dict) else {'value': p}
        self.events.append({
            'Partida': self.run_id, 'Secuencia': len(self.events)+1,
            'Ronda': self.engine.round_no if self.engine.round_no else (1 if self._phase=='round_start' else 0),
            'Turno_global': self._current_turn, 'Jugador_activo': self._active,
            'Fase': self._phase, 'Fuente': stream,
            'Accion': data.get('action') or data.get('event') or 'evento',
            'Jugador_afectado': data.get('player',data.get('active',data.get('challenger'))),
            'Detalle_JSON': _json(p),
        })

    def _note(self, action: str, **fields) -> None:
        self._event('observador', {'action': action, **fields})

    def attach_hooks(self, hooks: object) -> None:
        if self._hook_attached or hooks is not self.engine.hooks:
            raise ValueError('Hooks no pertenecen al motor o SIMLOG ya instalado')
        prior_step = hooks.on_step
        def on_step(e, p, pos, last):
            self._note('paso_por_casillero', player=p.id, stage=p.stage.value,
                       position=_position(pos), is_final=bool(last))
            return prior_step(e, p, pos, last)
        hooks.on_step = on_step
        prior_profile = hooks.on_profile
        def on_profile(e, p, reason):
            self._note('activacion_perfil', player=p.id, cause=reason)
            return prior_profile(e, p, reason)
        hooks.on_profile = on_profile
        prior_destination = hooks.on_destination
        def on_destination(e, p, target):
            self._note('casillero_activado', player=p.id, stage=p.stage.value,
                       destination=target)
            return prior_destination(e, p, target)
        hooks.on_destination = on_destination
        self._hook_attached = True

    def _player(self, p: PlayerState) -> dict:
        ac = self.eco.accounts[p.id]
        card = self.profiles.active.get(p.id)
        receipts = [r for r in self.eco.receipts.values() if r.owner == p.id]
        ongoing = [r for r in receipts if not self.eco.projects[r.project_id].complete]
        return {
            'id':p.id,'role':p.role,'stage':p.stage.value,'position':_position(p.position),
            'partner':p.partner_id,'free':dict(ac.free),
            'pair_a':ac.pair_a,'house_a':ac.house_a,'house_p':ac.house_p,
            'title':ac.title,'passport':ac.passport,'affinity':ac.affinity,
            'profile_id':card.id if card else None,
            'profile_production':list(ac.profile_production) if ac.profile_production else None,
            'hand':[(c.id,c.a,c.b) for c in p.hand.cards],
            'youth_card': (p.youth_movement.id,p.youth_movement.a,p.youth_movement.b)
                          if p.youth_movement else None,
            'utn_passed':p.utn_passed,
            'receipts': [dict(id=r.id,project=r.project_id,subhito=r.subhito,
                              resource=r.resource,amount=r.amount) for r in receipts],
            'active_investments': {key: sum(r.amount for r in ongoing if r.project_id==key)
                                   for key in sorted({r.project_id for r in ongoing})}
        }

    def _players(self) -> dict[int,dict]:
        return {pid:self._player(self.engine.players[pid]) for pid in self.engine.turn_order}

    def _world(self) -> dict:
        return {'issued':dict(self.eco.issued),'burned':dict(self.eco.burned),
                'invested':dict(self.eco.invested),
                'house_owner':self.eco.house_owner,'married':self.eco.married,
                'projects': {name:{'kind':p.kind,'winner':p.winner,
                                  'complete':p.complete,'receipts':list(p.receipts)}
                             for name,p in sorted(self.eco.projects.items())}}

    def begin_round(self) -> None:
        if self._current_turn is not None:
            raise ValueError('No iniciar ronda dentro de un turno')
        self._round_before = self._players()
        self._phase = 'round_start'

    def end_round_start(self) -> None:
        if self._phase != 'round_start' or self._round_before is None:
            raise ValueError('Falta begin_round')
        after = self._players()
        for pid in self.engine.turn_order:
            if self._round_before[pid] != after[pid]:
                self._note('transicion_inicio_ronda', player=pid,
                           before=self._round_before[pid], after=after[pid])
        self._round_before = None
        self._phase = 'between_turns'
        self._audit()

    def begin_turn(self, player_id: int) -> None:
        if self._current_turn is not None or self._phase not in ('between_turns',):
            raise ValueError('El registro de turno no se puede superponer')
        if player_id not in self.engine.players:
            raise ValueError('Jugador inexistente')
        self._current_turn = len(self.turns)+1
        self._event_start_idx = len(self.events)
        self._active = player_id
        self._phase = 'turn'
        self._before = self._players()
        self._world_before = self._world()
        self._movement_decision = None
        self._route = None
        self._note('turno_inicio', player=player_id)

    def wrap_adult_choice(self, decision_fn: Callable) -> Callable:
        def wrapped(player, situation, hand):
            choice = decision_fn(player, situation, hand)
            self._movement_decision = choice
            card = next((c for c in hand.cards if c.id==choice.card_id), None)
            if card is not None:
                distance = card.distance(choice.letter)
                eligible = player.partner_id is not None and self.engine.hooks.marriage_eligible(self.engine, player)
                route = walk_adult(player.position, distance, choice.direction,
                                   marriage_eligible=eligible, exit_after=choice.exit_after)
                self._route = {'visited':[_position(pos) for pos in route.visited],
                               'reflections':list(route.reflections),
                               'consumed':route.consumed,'discarded':route.discarded,
                               'activation':route.activation}
            self._note('decision_movimiento_adulto',player=player.id,card=choice.card_id,
                       choice=choice.letter,direction=choice.direction,
                       exit_after=choice.exit_after,route=self._route)
            return choice
        return wrapped

    def wrap_youth_choice(self, decision_fn: Callable) -> Callable:
        def wrapped(player, situation, movement):
            letter = decision_fn(player, situation, movement)
            self._note('decision_movimiento_juvenil',player=player.id,
                       card=movement.id,choice=letter,distance=movement.distance(letter))
            return letter
        return wrapped

    def _state_rows(self, stage: str, snapshots: dict[int,dict], turn:int) -> None:
        for pid in self.engine.turn_order:
            p=snapshots[pid]
            row={'Partida':self.run_id,'Ronda':self.engine.round_no,
                 'Turno_global':turn,'Momento':stage,'Jugador':pid,
                 'Rol':p['role'],'Etapa':p['stage'],'Posicion':p['position'],
                 'Pareja':p['partner'],'Perfil_ID':p['profile_id'],
                 'Afinidad_heredada':p['affinity'],'Produccion_perfil':_json(p['profile_production']),
                 'Res_pareja_A':p['pair_a'],'Res_casa_A':p['house_a'],'Res_casa_P':p['house_p'],
                 'Titulo':p['title'],'Pasaporte':p['passport'],
                 'Carta_juvenil':(p['youth_card'] or (None,))[0],
                 'Mano_adulta_JSON':_json(p['hand']),
                 'Comprobantes_JSON':_json(p['receipts']),
                 'Inversiones_JSON':_json(p['active_investments'])}
            for resource in RESOURCES:
                row[f'{resource}_libre'] = p['free'][resource]
            self.states.append(row)

    def _global_rows(self, moment: str, global_state: dict, turn: int) -> None:
        self.global_states.append({'Partida':self.run_id,'Ronda':self.engine.round_no,
             'Turno_global':turn,'Momento':moment,
             'Casa_duenios':_json(global_state['house_owner']),
             'Casamiento':_json(global_state['married']),
             'Proyectos_JSON':_json(global_state['projects']),
             **{f'{r}_emitido':global_state['issued'][r] for r in RESOURCES},
             **{f'{r}_consumido':global_state['burned'][r] for r in RESOURCES},
             **{f'{r}_invertido':global_state['invested'][r] for r in RESOURCES}})

    def _milestone_changes(self, before: dict, after: dict, world_before: dict,
                           world_after: dict, turn:int) -> None:
        keys=('stage','position','partner','title','passport','pair_a','house_a','house_p',
              'profile_id','affinity','receipts','active_investments')
        for pid in self.engine.turn_order:
            for field in keys:
                x,y=before[pid][field],after[pid][field]
                if x != y:
                    self.milestones.append({'Partida':self.run_id,'Ronda':self.engine.round_no,
                        'Turno_global':turn,'Jugador':pid,'Campo':field,
                        'Antes_JSON':_json(x),'Despues_JSON':_json(y)})
        for field in ('house_owner','married','projects'):
            x,y=world_before[field],world_after[field]
            if x!=y:self.milestones.append({'Partida':self.run_id,'Ronda':self.engine.round_no,
                  'Turno_global':turn,'Jugador':None,'Campo':field,
                  'Antes_JSON':_json(x),'Despues_JSON':_json(y)})

    def end_turn(self, outcome: TurnOutcome) -> None:
        if self._before is None or self._world_before is None or self._active != outcome.active:
            raise ValueError('Turno y resultado no coinciden')
        self._audit()
        before,after=self._before,self._players()
        world_before,world_after=self._world_before,self._world()
        pid=outcome.active
        x,y=before[pid],after[pid]
        self._note('turno_final',player=pid,result=outcome.target)
        related_events=self.events[self._event_start_idx:]
        situation_events=[e for e in related_events if e['Fuente']=='situacion'
                          and e['Accion']=='proposed_situation']
        if outcome.situation_id is not None and len(situation_events)!=1:
            raise AssertionError('Una Situación normal requiere exactamente una resolución registrada')
        if outcome.situation_id is None and situation_events:
            raise AssertionError('Se registró una Situación en turno de tránsito')
        situ=situation_events[0] if situation_events else None
        outcome_situation=json.loads(situ['Detalle_JSON']) if situ else {}
        result = outcome_situation.get('result')
        if result in ('A','B'):
            situation_letter=result
        elif result in ('choice_0','choice_target_0'):
            situation_letter='A'
        elif result in ('choice_1','choice_target_1'):
            situation_letter='B'
        else:
            situation_letter=None
        if x['stage']=='Juventud' and outcome.situation_id and situation_letter!=outcome.choice:
            raise AssertionError('Juventud: Situación A/B no coincide con Movimiento')
        title_source,title=(self._title.get(outcome.situation_id,(None,None))
                            if outcome.situation_id else (None,None))
        dice=outcome.distance if x['stage']=='Infancia' else None
        for ev in related_events:
            if ev['Accion']=='utn_exam':
                dice=json.loads(ev['Detalle_JSON']).get('die')
        economy_actions=[e for e in related_events if e['Fuente']=='economia']
        change_events=[e for e in related_events if e['Accion'] in
                       ('transfer','profile_changed','adjudicate','pair','pair_broken')]
        if self._route is not None:
            route=self._route
        elif x['stage'] in ('Infancia','Juventud'):
            steps=[]
            for e in related_events:
                if e['Fuente']=='observador' and e['Accion']=='paso_por_casillero':
                    data=json.loads(e['Detalle_JSON'])
                    if data.get('player')==pid:
                        steps.append(data['position'])
            route={'visited':steps,'reflections':[], 'consumed':len(steps),
                   'discarded':max(0,outcome.distance-len(steps)) if outcome.distance is not None else 0}
        else:
            route={}
        row={
            'Partida':self.run_id,'Ronda':outcome.round_no,'Turno_global':self._current_turn,
            'Jugador':pid,'Rol':x['role'],'Politica':self.policy,
            'Pareja_antes':x['partner'],'Pareja_despues':y['partner'],
            'Etapa_antes':x['stage'],'Pos_antes':x['position'],
            'Dado':dice,'Casillero_resuelto':outcome.target,
            'Etapa_despues':y['stage'],'Pos_despues':y['position'],
            'Carta_ID':outcome.situation_id,'Carta_fuente_ID':title_source,
            'Situacion':title,'Desenlace_elegido':situation_letter,
            'Desenlace_texto':self._option_text.get(outcome.situation_id,{}).get(situation_letter)
                              if situation_letter else None,
            'Carta_familia':self._option_text.get(outcome.situation_id,{}).get('family'),
            'Resultado_situacion':result,
            'Carta_Movimiento':outcome.movement_card_id,
            'Desenlace_movimiento':outcome.choice if x['stage'] in ('Juventud','Adultez') else None,
            'Distancia_movimiento':outcome.distance,'Direccion':self._movement_decision.direction if self._movement_decision else None,
            'Salida_despues_de':self._movement_decision.exit_after if self._movement_decision else None,
            'Ruta_JSON':_json(route.get('visited',[])) if route else None,
            'Rebotes_JSON':_json(route.get('reflections',[])) if route else None,
            'Pasos_consumidos':route.get('consumed') if route else None,
            'Pasos_descartados':route.get('discarded') if route else None,
            'Canje':'; '.join(f"{json.loads(ev['Detalle_JSON']).get('resource')} {json.loads(ev['Detalle_JSON']).get('amount')}"
                              for ev in economy_actions if json.loads(ev['Detalle_JSON']).get('source')=='conversion_bancaria'),
            'Eventos':'; '.join(e['Accion'] for e in related_events),
            'Eventos_ID_JSON':_json([e['Secuencia'] for e in related_events]),
            'Eventos_clave_JSON':_json([json.loads(e['Detalle_JSON']) for e in change_events]),
            'Eventos_cantidad':len(related_events),
            'Estado_global_inicio_fin_en':'estados_globales.csv',
            'Estados_jugadores_en':'estados_jugadores.csv',
            'Casa_duenios':_json(world_after['house_owner']),
            'Casamiento_duenios':_json(world_after['married']),
            'Perfil_ID':y['profile_id'],'Afinidad_heredada':y['affinity'],
            'Res_pareja_A':y['pair_a'],'Res_casa_A':y['house_a'],
            'Res_casa_P':y['house_p'],
            'Titulo':y['title'],'Pasaporte':y['passport'],
            'Casa':(world_after['house_owner'] is not None and pid in world_after['house_owner']),
            'Casamiento':world_after['married'] is not None,
            'Pareja_recursos_antes':_json(before.get(x['partner'],{})) if x['partner'] else None,
            'Pareja_recursos_despues':_json(after.get(y['partner'],{})) if y['partner'] else None,
        }
        for r in RESOURCES:
            row[r+'_antes']=x['free'][r]+(x['pair_a']+x['house_a'] if r=='A' else x['house_p'] if r=='P' else 0)
            row[r+'_despues']=y['free'][r]+(y['pair_a']+y['house_a'] if r=='A' else y['house_p'] if r=='P' else 0)
            row[r+'_libre_antes']=x['free'][r]
            row[r+'_libre_despues']=y['free'][r]
        self._global_rows('antes',world_before,self._current_turn)
        self._global_rows('despues',world_after,self._current_turn)
        self._state_rows('antes', before,self._current_turn)
        self._state_rows('despues',after,self._current_turn)
        self._milestone_changes(before,after,world_before,world_after,self._current_turn)
        self.turns.append(row)
        self._current_turn,self._active,self._before,self._world_before=None,None,None,None
        self._phase='between_turns'

    def end_round(self, *, ended: bool=False) -> None:
        self._audit()
        totals={r:sum(ac.free[r] for ac in self.eco.accounts.values()) for r in RESOURCES}
        self.rounds.append({'Partida':self.run_id,'Ronda':self.engine.round_no,
                            'Turnos_observados':sum(x['Ronda']==self.engine.round_no for x in self.turns),
                            'Termino_partida':ended,'Casa_duenios':_json(self.eco.house_owner),
                            'Casados':_json(self.eco.married),
                            'Activos_por_etapa_JSON':_json(dict(Counter(p.stage.value for p in self.engine.players.values()))),
                            **{r+'_libre_total':totals[r] for r in RESOURCES}})

    def _preferencias(self, key: str) -> list[dict]:
        groups=defaultdict(Counter)
        for row in self.turns:
            card=row['Carta_ID'] if key=='situacion' else row['Carta_Movimiento']
            if not card:continue
            choice=row['Desenlace_elegido'] if key=='situacion' else row['Desenlace_movimiento']
            k=(row['Rol'],row['Etapa_antes'],card,row['Carta_fuente_ID'] if key=='situacion' else None)
            groups[k][choice if choice in ('A','B') else 'OTRO']+=1
        result=[]
        for (role,stage,card,source),counter in sorted(groups.items()):
            a,b,other=(counter.get(v,0) for v in ('A','B','OTRO'))
            n=a+b+other
            result.append({'Partida':self.run_id,'Tipo':key,'Rol':role,'Etapa':stage,
                           'Carta_ID':card,'Carta_fuente_ID':source,'Veces_resuelta':n,
                           'Elecciones_A':a,'Elecciones_B':b,
                           'Otras_resoluciones':other,
                           'Porcentaje_A_sobre_AB':round(a/(a+b)*100,2) if a+b else None,
                           'Porcentaje_B_sobre_AB':round(b/(a+b)*100,2) if a+b else None})
        return result

    def validate(self) -> None:
        self._audit()
        if len(self.turns)!=len({(x['Partida'],x['Turno_global']) for x in self.turns}):
            raise AssertionError('Turnos repetidos')
        if len(self.states)!=len(self.turns)*len(self.engine.players)*2:
            raise AssertionError('Faltan estados de jugadores antes/después')
        if len(self.global_states)!=len(self.turns)*2:
            raise AssertionError('Faltan estados globales antes/después')
        if len(self.events)!=len({e['Secuencia'] for e in self.events}):
            raise AssertionError('Secuencias de evento duplicadas')
        per_turn=Counter(e['Turno_global'] for e in self.events if e['Turno_global'] is not None)
        for t in self.turns:
            if t['Eventos_cantidad']!=per_turn[t['Turno_global']]:
                raise AssertionError('Recuento de eventos de turno inconsistente')
            if t['Etapa_antes']=='Juventud' and t['Carta_ID']:
                if t['Desenlace_elegido']!=t['Desenlace_movimiento']:
                    raise AssertionError('A/B juvenil divergentes')
            if t['Etapa_antes']=='Adultez' and t['Carta_ID']:
                if t['Desenlace_movimiento'] not in ('A','B'):
                    raise AssertionError('Falta selección A/B de Movimiento adulto')
        if self._current_turn is not None:
            raise AssertionError('Hay un turno abierto')

    def write(self, out: str|Path, *, status: str, summary:dict) -> dict:
        if self._run_finished:raise ValueError('La traza ya fue exportada')
        self.validate()
        out=Path(out)
        out.mkdir(parents=True,exist_ok=True)
        formats={
            'turnos.csv':self.turns,
            'eventos.csv':self.events,
            'estados_jugadores.csv':self.states,
            'estados_globales.csv':self.global_states,
            'hitos.csv':self.milestones,
            'recursos_por_ronda.csv':self.rounds,
            'preferencias_situaciones.csv':self._preferencias('situacion'),
            'preferencias_movimientos.csv':self._preferencias('movimiento'),
        }
        manifest={'schema':SCHEMA_VERSION,'run_id':self.run_id,'seed':self.seed,
                  'player_count':len(self.engine.players),'roles':{str(pid):p.role for pid,p in self.engine.players.items()},
                  'policy':self.policy,'competition':self.competition,
                  'round_limit':self.round_limit,'balance_variant':self.balance,
                  'cards_status':'EXPERIMENTAL_NO_APROBADO','sources':{
                      'Infancia_Juventud':'78 históricas v0.1 duplicadas por personaje',
                      'Adultez':'30 propuestas multiverso v0.2 NO APROBADAS'},
                  'validation':'PASS','status':status,'summary':summary,
                  'counts':{name:len(rows) for name,rows in formats.items()},
                  'file_sha256':{}}
        # Escapar valores de texto iniciados en símbolos de fórmula para hojas de cálculo.
        for filename,rows in formats.items():
            if not rows:
                # Incluso un hito vacío tiene esquema con encabezados declarados.
                headers=['Partida','Ronda','Turno_global','Jugador','Campo','Antes_JSON','Despues_JSON'] if filename=='hitos.csv' else []
            else:
                headers=list(rows[0])
            path=out/filename
            with path.open('w',newline='',encoding='utf-8-sig') as f:
                w=csv.DictWriter(f,fieldnames=headers,extrasaction='raise')
                if headers:w.writeheader()
                for row in rows:
                    safe={k:("'"+v if isinstance(v,str) and v[:1] in ('=','+','-','@') else v)
                          for k,v in row.items()}
                    w.writerow(safe)
            manifest['file_sha256'][filename]=hashlib.sha256(path.read_bytes()).hexdigest()
        with (out/'eventos.jsonl').open('w',encoding='utf-8') as f:
            for e in self.events:f.write(_json(e)+'\n')
        manifest['counts']['eventos.jsonl']=len(self.events)
        manifest['file_sha256']['eventos.jsonl']=hashlib.sha256((out/'eventos.jsonl').read_bytes()).hexdigest()
        (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        self._run_finished = True
        return manifest