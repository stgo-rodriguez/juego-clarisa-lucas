"""Fase 7: bots con subastas y duelos; reglas pendientes como parámetros.

IMPORTANTE: las preferencias de puja, los montos y las políticas de los bots
son hipótesis de simulación, no nuevas reglas oficiales de v2.0.
"""
from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Callable

from simulador.agentes_v2 import GameAgent
from simulador.economia_v2 import EconomyV2, PASSPORT_KIND, RESOURCES
from simulador.interacciones_v2 import AuctionCard, Bid, InteractionV2, SocialAuctionsV2
from simulador.turnos_v2 import PlayerState, RoundEngine, SituationCard, Stage, TurnOutcome


@dataclass(frozen=True)
class CompetitionConfig:
    enabled: bool = True
    order_policy: str = 'global'  # EXPERIMENTAL; reglamento aún sin ordenar pujas
    youth_return_pos: int | None = None  # No se adivina el casillero de retorno
    ordinary_stake: int = 2
    bid_ceiling: int = 3

    def __post_init__(self):
        if self.order_policy != 'global':
            raise ValueError('Solo existe orden global EXPERIMENTAL en este prototipo')
        if not isinstance(self.enabled, bool):
            raise ValueError('enabled debe ser booleano')
        if not isinstance(self.ordinary_stake, int) or self.ordinary_stake < 1:
            raise ValueError('Apuesta inválida')
        if not isinstance(self.bid_ceiling, int) or self.bid_ceiling < 1:
            raise ValueError('Límite de puja inválido')
        if self.youth_return_pos is not None and (type(self.youth_return_pos) is not int or not 1 <= self.youth_return_pos <= 6):
            raise ValueError('La posición de regreso a Juventud requiere 1..6')


class CompetitiveController:
    """Se agrega al orquestador, sin alterar las cartas ocultas ni el turno.

    En cualquier momento decide solo a partir de estado público y de la mano
    propia del activo. En particular NO examina el orden futuro de los mazos.
    """
    def __init__(self, engine: RoundEngine, eco: EconomyV2,
                 core_agent: GameAgent, interactions: InteractionV2,
                 auctions: SocialAuctionsV2, config: CompetitionConfig,
                 seed: int = 1):
        self.engine, self.eco, self.core_agent = engine, eco, core_agent
        self.interactions, self.auctions, self.config = interactions, auctions, config
        self.rng = random.Random(seed)
        self.events: list[dict] = []
        self.attempts = 0
        self.duel_attempts = 0
        self.auction_invocations = 0

    def _log(self, event: str, **fields):
        self.events.append({'round': self.engine.round_no, 'event':event, **fields})

    def _value(self, player_id: int, resource: str) -> float:
        """Preferencia SUBJETIVA de un bot, nunca equivalencia global del juego."""
        account = self.eco.accounts[player_id]
        # Escasez solo afecta la preferencia de este bot en esta decisión.
        scarcity = {'A': 12, 'P': 10, 'K': 7, 'M': 12}[resource]
        return 1.0 + (1.7 if account.free[resource] < scarcity else .25)

    def _eligible_for_bid(self, card: AuctionCard, active_id: int) -> tuple[int, ...]:
        active = self.engine.players[active_id]
        return tuple(pid for pid in self.engine.turn_order
                     if pid != active_id and pid != active.partner_id
                     and self.engine.players[pid].stage in card.eligible_stages
                     and self.engine.players[pid].role in card.eligible_roles)

    def resolve_social_situation(self, engine: RoundEngine, active: PlayerState,
                                 card: SituationCard,
                                 ordinary_effect: Callable[[RoundEngine, PlayerState, SituationCard, str | None], None],
                                 letter: str | None):
        payload = card.payload
        if not isinstance(payload, AuctionCard):
            ordinary_effect(engine, active, card, letter)
            return
        if active.stage != Stage.ADULTEZ:
            raise ValueError('No ejecutar subastas fuera de Adultez')
        order = self._eligible_for_bid(payload, active.id)
        chosen = None
        if payload.mode == 'active_choice':
            chosen = max(payload.bid_resources, key=lambda r: (self._value(active.id, r), r))
        allowed = (chosen,) if payload.mode == 'active_choice' else payload.bid_resources

        def bid_for(player: PlayerState, current: Bid | None) -> Bid | None:
            if not self.config.enabled:
                return None
            account = self.eco.accounts[player.id]
            # Criterio de bot: oferta de hasta 'ceiling'; debe ser solvente.
            candidates = []
            for resource in allowed:
                ceiling = min(self.config.bid_ceiling, account.free[resource],
                              max(1, payload.appropriable - 1))
                if ceiling < 1:
                    continue
                # No hipotecar el último recurso para una apropiación incierta.
                if account.free[resource] <= 1 and self.core_agent.config.policy == 'planificador':
                    continue
                amount = min(ceiling, 1 if current is None else current.quantity + 1)
                if payload.mode == 'heterogeneous':
                    # El activo evalúa subjetivamente; aquí la cantidad propuesta
                    # es aproximación heurística, no una regla de conversión.
                    amount = min(ceiling, 2)
                candidates.append(Bid(player.id, resource, amount))
            if not candidates:
                return None
            if self.core_agent.config.policy == 'aleatorio' and self.rng.randrange(4) == 0:
                return None
            # Pujar con el recurso menos valioso para ESTE oferente.
            return min(candidates, key=lambda b: (b.quantity * self._value(player.id,b.resource), b.resource))

        def compare(a: Bid, b: Bid) -> int:
            # Juicio explícitamente SUBJETIVO del jugador activo para esta subasta.
            av = a.quantity * self._value(active.id, a.resource)
            bv = b.quantity * self._value(active.id, b.resource)
            return 1 if av > bv + 1e-9 else -1 if av < bv - 1e-9 else 0

        def choose_winner(tied: tuple[Bid, ...]) -> int | None:
            if payload.allow_reject and self.config.enabled and self.core_agent.config.policy=='planificador':
                # Experimental: rechazar solo si la puja percibida es muy baja.
                if max(b.quantity * self._value(active.id,b.resource) for b in tied) < 1.1:
                    return None
            return max(tied, key=lambda b:(b.quantity * self._value(active.id,b.resource), -b.player_id)).player_id

        result = self.auctions.run(active.id,payload,
            bid_for=bid_for,select_winner=choose_winner,
            chosen_currency=chosen,bid_order=order,
            compare_heterogeneous=compare if payload.mode=='heterogeneous' else None)
        self.auction_invocations += 1
        self._log('subasta',active=active.id,card=payload.id,mode=payload.mode,
                  winner=result.winner,bids=len(result.bids),passed=len(result.passed),
                  result=result.reason)

    def _choose_duel(self, active: PlayerState, target: PlayerState):
        a = self.eco.accounts[active.id]
        d = self.eco.accounts[target.id]
        if a.free['P'] < 1:
            return None
        # Proyecto: existe comprobante elegible vigente; sólo si no tiene hito.
        for project in self.eco.projects.values():
            if project.winner != target.id or project.kind != 'Titulo' and PASSPORT_KIND[active.role] != project.kind:
                continue
            if project.kind == 'Titulo' and a.title or project.kind != 'Titulo' and a.passport is not None:
                continue
            if not any(self.eco.receipts[rid].owner == active.id for rid in project.receipts):
                continue
            resource = 'K' if project.kind == 'Titulo' else 'P'
            if a.free[resource] < 5:
                continue
            if target.stage == Stage.ADULTEZ and self.config.youth_return_pos is None:
                # Regla pendiente: no inventar una posición para la víctima.
                continue
            return ('hito',dict(project_id=project.id,
                                return_youth_pos=self.config.youth_return_pos))
        if (active.role==target.role and
            active.id in self.interactions.profiles.active and
            target.id in self.interactions.profiles.active):
            my = self.interactions.profiles.active[active.id]
            theirs = self.interactions.profiles.active[target.id]
            if active.partner_id is not None:
                mate = self.eco.accounts[active.partner_id]
                if my.affinity != mate.affinity and theirs.affinity == mate.affinity:
                    return ('perfil',{})
            elif self.core_agent.config.policy=='aleatorio' and self.rng.randrange(3)==0:
                return ('perfil',{})
        # Solo Título puede disputarse entre Clarisa y Lucas. Un duelo
        # ordinario exige mismo rol incluso si comparten casillero.
        if active.role != target.role:
            return None
        resource = 'M'
        stake = self.config.ordinary_stake
        if min(a.free[resource], d.free[resource]) >= stake:
            if self.core_agent.config.policy=='aleatorio' or d.free['M']>a.free['M']:
                return ('ordinario',dict(stake_resource=resource,stake=stake))
        return None

    def after_turn(self, engine: RoundEngine, active: PlayerState, outcome: TurnOutcome):
        if engine is not self.engine:
            raise ValueError('Controlador asociado a otro motor')
        if not self.config.enabled or active.stage not in (Stage.JUVENTUD,Stage.ADULTEZ):
            return
        if (engine.round_no,active.id) in self.interactions.used:
            return
        candidates = [p for p in engine.players.values()
                      if p.id != active.id and p.id != active.partner_id and
                      p.stage == active.stage and p.position == active.position]
        if self.core_agent.config.policy=='aleatorio':
            self.rng.shuffle(candidates)
        else:
            candidates.sort(key=lambda q:(-self.eco.accounts[q.id].free['M'],q.id))
        for target in candidates:
            data = self._choose_duel(active,target)
            if data is None:
                continue
            kind, kws = data
            self.duel_attempts += 1
            def decide(defender_die: int) -> str:
                if self.core_agent.config.policy=='aleatorio':
                    return self.rng.choice(('lanzar','lanzar','retirada'))
                # Retirada racional con dado alto del defensor; costo fijo 1 P.
                return 'retirada' if defender_die >= 5 else 'lanzar'
            result = self.interactions.duel(active.id,target.id,kind,
                decide=decide,**kws)
            self._log('duelo',challenger=active.id,defender=target.id,kind=kind,
                      result=result.result,defender_die=result.defender_die,
                      challenger_die=result.challenger_die)
            return