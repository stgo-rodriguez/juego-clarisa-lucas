"""Experimento v2.2: canje bancario 2:1 y políticas por participante.

Las políticas (planificador/aleatorio) son heurísticas experimentales,
no componentes del reglamento. Se preservan la geometría y las cartas v2.2.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from simulador.reglas_v22 import EconomyV22, RoundEngineV22
from simulador.reglas_v21 import CurrentResolverV21
from simulador.agentes_v2 import AgentConfig
from simulador.agentes_v22 import GameAgentV22
from simulador.simlog_v22 import SIMLogV22
from simulador.turnos_v2 import Stage

CHAIN = ('A', 'P', 'K', 'M')
POLICIES = frozenset(('planificador', 'aleatorio'))


def assign_policies(players, policy: str, seed: int) -> dict[int, str]:
    """Mitad planificadores en mesa mixta; alterna sesgo entre roles por semilla."""
    if policy in POLICIES:
        return {p.id: policy for p in players}
    if policy != 'mixto':
        raise ValueError(f'Política no reconocida: {policy}')
    roles = {
        role: [p.id for p in players if p.role == role]
        for role in ('Clarisa', 'Lucas')
    }
    rng = random.Random(seed * 13 + 29017)
    for ids in roles.values():
        rng.shuffle(ids)
    # 6 = 3+3 y 10 = 5+5; alterna cuál rol aporta la plaza adicional.
    c = len(roles['Clarisa']) // 2 + (len(roles['Clarisa']) % 2 and seed % 2 == 0)
    l = len(players)//2 - c
    plan = set(roles['Clarisa'][:c] + roles['Lucas'][:l])
    result = {p.id: ('planificador' if p.id in plan else 'aleatorio') for p in players}
    assert list(result.values()).count('planificador') == len(players)//2
    return result


class EconomyBankV22(EconomyV22):
    """Una operación 2:1 por jugador y ronda; solo dos recursos adyacentes."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bank_used: set[tuple[int, int]] = set()

    def convert(self, player_id: int, source: str, target: str, pairs: int, round_no: int):
        if source not in CHAIN or target not in CHAIN or abs(CHAIN.index(source)-CHAIN.index(target)) != 1:
            raise ValueError('Canje solo entre A-P, P-K o K-M en ambas direcciones')
        if type(pairs) is not int or pairs <= 0:
            raise ValueError('Canje requiere múltiplos enteros positivos')
        if type(round_no) is not int or round_no <= 0:
            raise ValueError('Ronda inválida')
        if (round_no, player_id) in self.bank_used:
            raise ValueError('Solo una operación bancaria por jugador y turno')
        if self.accounts[player_id].free[source] < 2*pairs:
            raise ValueError('Canje no permite usar reservas ni saldos inexistentes')
        self.bank_used.add((round_no, player_id))
        self.spend(player_id, source, 2*pairs, 'conversion_bancaria')
        self.issue(player_id, target, pairs, 'conversion_bancaria')
        self.events.append({
            'action': 'conversion_bancaria',
            'player': player_id, 'round': round_no,
            'from': source, 'to': target, 'spent': 2*pairs,
            'received': pairs, 'pairs': pairs,
        })
        self.audit()

    def choose_conversion(self, player, policy: str, round_no: int, rng: random.Random):
        if (round_no, player.id) in self.bank_used:
            return None
        account = self.accounts[player.id]
        free = account.free
        if policy == 'aleatorio':
            if rng.random() >= .35:
                return None
            options = [(a, b) for a in CHAIN for b in CHAIN
                       if abs(CHAIN.index(a)-CHAIN.index(b))==1 and free[a]>=2]
            return (lambda pair: (pair[0], pair[1], 1))(rng.choice(options)) if options else None
        if policy != 'planificador':
            raise ValueError('Política bancaria desconocida')
        if player.stage in (Stage.INFANCIA, Stage.UTN):
            priorities = [('A','P',8,2), ('P','K',6,1)]
        elif player.stage == Stage.JUVENTUD:
            priorities = [('K','M',8,7), ('A','P',13,5),
                          ('P','K',10,6), ('M','K',14,6)]
        else:
            priorities = [('K','M',5,24), ('K','P',8,12),
                          ('P','A',12,16), ('A','P',20,12),
                          ('M','K',26,5)]
        for src, dst, preserve, desired in priorities:
            if free[dst] >= desired or free[src] < preserve + 2:
                continue
            pairs = min(3, (free[src]-preserve)//2, desired-free[dst])
            if pairs >= 1:
                return src, dst, pairs
        return None


class CurrentResolverPoliciesV22(CurrentResolverV21):
    def __init__(self, eco, interactions, policy_by_player, seed=0, affinity_weight=8.0):
        super().__init__(eco, interactions, 'planificador', seed, affinity_weight)
        self.policy_by_player = dict(policy_by_player)

    def resolve(self, engine, player, card, letter):
        self.policy = self.policy_by_player[player.id]
        super().resolve(engine, player, card, letter)
        chosen = self.events[-1]['result']
        if chosen not in ('A', 'B'):
            raise AssertionError('Situación sin elección A/B')
        return chosen


class RoundEngineAuditV22(RoundEngineV22):
    """El evento registra la elección real emitida por el resolutor, no None."""

    def _situation(self, player, choice):
        key = self.round_assignments.get(player.id)
        if key is None or key not in self._revealed:
            raise ValueError('Sin Situación compartida asignada en la ronda')
        card = self._revealed[key]
        selected = self.hooks.apply_situation(self, player, card, choice)
        if selected not in ('A', 'B'):
            raise AssertionError('El resolutor debe devolver la elección A/B')
        self._event('situation_resolved', player=player.id,
                    card=card.id, choice=selected,
                    stage=key[0].value, role=key[1])
        return card


class AgentRosterV22:
    """Un agente autónomo por jugador, con acciones y RNG propios."""

    def __init__(self, engine, eco, policy_by_player, seed, profiles):
        self.policy_by_player = dict(policy_by_player)
        self.agents = {
            pid: GameAgentV22(engine, eco, AgentConfig(policy),
                              seed*7919 + pid*127, profiles)
            for pid, policy in self.policy_by_player.items()
        }
        self._active_pid = min(self.agents)
        self.actions = []
        self.first_pair_round = None
        self.first_house_round = None

    def policy_for(self, pid):
        return self.policy_by_player[pid]

    @property
    def config(self):
        # Usado por el controlador de duelos para el jugador activo.
        return self.agents[self._active_pid].config

    def choose_youth(self, player, situation, movement):
        self._active_pid = player.id
        return self.agents[player.id].choose_youth(player, situation, movement)

    def choose_adult(self, player, situation, hand):
        self._active_pid = player.id
        return self.agents[player.id].choose_adult(player, situation, hand)

    def after_turn(self, engine, player, outcome):
        self._active_pid = player.id
        agent = self.agents[player.id]
        start = len(agent.actions)
        agent.after_turn(engine, player, outcome)
        self.actions.extend(agent.actions[start:])
        if self.first_pair_round is None and agent.first_pair_round is not None:
            self.first_pair_round = agent.first_pair_round
        if self.first_house_round is None and agent.first_house_round is not None:
            self.first_house_round = agent.first_house_round


class SIMLogAuditV22(SIMLogV22):
    def __init__(self, *args, policy_by_player, hand_size, bank_enabled=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.policy_by_player = dict(policy_by_player)
        self.hand_size_variant = hand_size
        self.bank_enabled = bool(bank_enabled)

    def end_turn(self, outcome):
        related = self.events[self._event_start_idx:]
        super().end_turn(outcome)
        self.turns[-1]['Politica'] = self.policy_by_player[outcome.active]
        self.turns[-1]['Politica_partida'] = self.policy
        canjes = []
        for event in related:
            if event['Fuente'] == 'economia' and event['Accion'] == 'conversion_bancaria':
                import json
                detail = json.loads(event['Detalle_JSON'])
                canjes.append(f"{detail['spent']} {detail['from']} → {detail['received']} {detail['to']}")
        self.turns[-1]['Canje'] = '; '.join(canjes)

    def validate(self):
        super().validate()
        for row in self.turns:
            if row['Politica'] != self.policy_by_player[row['Jugador']]:
                raise AssertionError('Política individual no coincide con la traza')
            related_ids = set(__import__('json').loads(row['Eventos_ID_JSON']))
            choices = [
                __import__('json').loads(e['Detalle_JSON'])
                for e in self.events
                if e['Secuencia'] in related_ids
                and e['Fuente'] == 'motor'
                and e['Accion'] == 'situation_resolved'
            ]
            if row['Carta_ID'] and (len(choices)!=1 or choices[0].get('choice') != row['Desenlace_elegido']):
                raise AssertionError('El evento situation_resolved debe conservar A/B efectivo')
            canjes = [
                e for e in self.events
                if e['Secuencia'] in related_ids and e['Accion']=='conversion_bancaria'
            ]
            if len(canjes) > 1:
                raise AssertionError('Más de una conversión en el turno')

    def write(self, out, *, status, summary):
        import json
        from pathlib import Path
        manifest = super().write(out, status=status, summary=summary)
        manifest['experimental_variant'] = 'v22-bank-mixed-policy'
        manifest['policies_by_player'] = {str(k):v for k,v in self.policy_by_player.items()}
        manifest['adult_hand_size'] = self.hand_size_variant
        manifest['bank_conversion_enabled'] = self.bank_enabled
        Path(out, 'manifest.json').write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8',
        )
        return manifest
