"""Interacciones v2.0 aisladas y auditables (Fase 6).

Duelos ordinarios, de Perfil y de hito; subastas sociales de apropiación,
rupturas y pérdida de Casa. No crea cartas oficiales ni fija parámetros
pendientes. Ejecutar desde la fase de acciones del turno activo.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
import random
from typing import Callable

from simulador.economia_v2 import EconomyV2, PASSPORT_KIND, RESOURCES
from simulador.turnos_v2 import PendingRuleError, PlayerState, RoundEngine, RuleHooks, Stage, SituationCard
from simulador.movimiento_v2 import AdultHand
from simulador.transiciones_v2 import ProfileDecksV2


@dataclass(frozen=True)
class DuelResult:
    kind: str
    challenger: int
    defender: int
    defender_die: int
    challenger_die: int | None
    result: str  # retirada / victoria / derrota / empate
    cost: int
    resource: str | None


class InteractionV2:
    """Ejecución sincronizada con el turno, no es un agente."""

    def __init__(self, engine: RoundEngine, economy: EconomyV2,
                 profiles: ProfileDecksV2 | None = None,
                 *, rng: random.Random | None = None):
        self.engine, self.eco, self.profiles = engine, economy, profiles
        self.rng = rng or random.Random(6)
        self.used: set[tuple[int, int]] = set()
        self.events: list[dict] = []

    def _turn(self, challenger: PlayerState, defender: PlayerState) -> tuple[int, int]:
        e = self.engine
        if not e.round_no or e._turn_index == 0 or e.turn_order[e._turn_index - 1] != challenger.id:
            raise ValueError('Solo el jugador activo puede iniciar un duelo después de su movimiento')
        token = (e.round_no, challenger.id)
        if token in self.used:
            raise ValueError('Máximo un duelo iniciado por jugador y turno')
        if challenger.id == defender.id or defender.id not in e.players:
            raise ValueError('Defensor inválido')
        if challenger.partner_id == defender.id:
            raise ValueError('No se disputa con el propio compañero')
        if challenger.stage != defender.stage or challenger.position != defender.position:
            raise ValueError('Un duelo requiere coincidencia exacta de etapa y casillero')
        return token

    @staticmethod
    def _dice(value: int | None, rng: random.Random) -> int:
        if value is None:
            return rng.randint(1, 6)
        if type(value) is not int or not 1 <= value <= 6:
            raise ValueError('Dado debe estar entre 1 y 6')
        return value

    def duel(self, challenger_id: int, defender_id: int, kind: str,
             *, stake_resource: str | None = None, stake: int = 0,
             project_id: str | None = None,
             decide: Callable[[int], str] | None = None,
             defender_die: int | None = None, challenger_die: int | None = None,
             return_youth_pos: int | None = None) -> DuelResult:
        """Defensor lanza primero; decide(defensor_d6) -> retirada / lanzar.

        En hito, derrota consume 5 K o 5 P; empate no consume la apuesta.
        En Perfil, victoria intercambia las DOS cartas activas reales.
        Un desplazamiento de hito de una persona adulta requiere coordenada
        de regreso juvenil EXPRESA y dispara el regreso de su pareja.
        """
        p, d = self.engine.players[challenger_id], self.engine.players[defender_id]
        token = self._turn(p, d)
        if kind not in ('ordinario', 'perfil', 'hito'):
            raise ValueError('Clase de duelo inválida')
        account = self.eco.accounts[p.id]
        d_account = self.eco.accounts[d.id]
        resource = None
        loss = 0
        project = None
        if kind == 'ordinario':
            if p.role != d.role:
                raise ValueError('Duelo ordinario requiere jugadores del mismo rol')
            if stake_resource not in RESOURCES or type(stake) is not int or stake < 1:
                raise ValueError('Recurso y apuesta libre obligatorios')
            resource, loss = stake_resource, stake
            # Se exige solvencia a ambos: evita transferir recursos inexistentes.
            if min(account.free[resource], d_account.free[resource]) < loss:
                raise ValueError('Ambos deben poder pagar la apuesta del duelo ordinario')
        elif kind == 'perfil':
            if self.profiles is None or p.role != d.role:
                raise ValueError('Disputa de Perfil: mismo personaje, mazo disponible')
            if p.id not in self.profiles.active or d.id not in self.profiles.active:
                raise ValueError('Ambos deben tener Perfil activo')
        else:
            if project_id is None or project_id not in self.eco.projects:
                raise ValueError('Proyecto inexistente')
            project = self.eco.projects[project_id]
            if project.winner != d.id or p.id == d.id:
                raise ValueError('El desafiado debe ser propietario del hito')
            if not any(self.eco.receipts[rid].owner == p.id for rid in project.receipts):
                raise ValueError('Solo los inversores con comprobante vigente pueden disputar')
            if project.kind != 'Titulo' and PASSPORT_KIND[p.role] != project.kind:
                raise ValueError('Comprobante de Pasaporte incompatible')
            if project.kind == 'Titulo' and account.title:
                raise ValueError('No disputa un Título quien ya lo posee')
            if project.kind != 'Titulo' and account.passport is not None:
                raise ValueError('No disputa Pasaporte quien ya lo posee')
            resource = 'K' if project.kind == 'Titulo' else 'P'
            loss = 5
            if d.stage == Stage.ADULTEZ:
                affected=[d] + ([self.engine.players[d.partner_id]] if d.partner_id else [])
                self._preflight_youth(affected,return_youth_pos)
        if account.free['P'] < 1:
            raise ValueError('Retirada potencial exige disponer de 1 Personalidad libre')
        if resource is not None and account.free[resource] < loss:
            raise ValueError('La apuesta potencial debe poder pagarse con recursos libres')
        defense = self._dice(defender_die, self.rng)
        choice = decide(defense) if decide is not None else 'lanzar'
        if choice not in ('retirada', 'lanzar'):
            raise ValueError('Decisión de retirada inválida')
        attack = None if choice == 'retirada' else self._dice(challenger_die, self.rng)
        self.used.add(token)
        if choice == 'retirada':
            self.eco.transfer(p.id, d.id, 'P', 1)
            outcome = 'retirada'
            paid = 1
            paid_resource = 'P'
        else:
            outcome = 'victoria' if attack > defense else 'derrota' if attack < defense else 'empate'
            paid, paid_resource = 0, resource
            if kind == 'ordinario':
                if outcome == 'victoria':
                    self.eco.transfer(d.id, p.id, resource, loss)
                    paid = loss
                elif outcome == 'derrota':
                    self.eco.transfer(p.id, d.id, resource, loss)
                    paid = loss
            elif kind == 'perfil' and outcome == 'victoria':
                active = self.profiles.active
                active[p.id], active[d.id] = active[d.id], active[p.id]
                for pid in (p.id, d.id):
                    card = active[pid]
                    self.eco.set_profile(pid, card.tier, affinity=card.affinity)
            elif kind == 'hito':
                if outcome == 'victoria':
                    assert project is not None
                    if project.kind == 'Titulo':
                        d_account.title, account.title = False, True
                    else:
                        d_account.passport, account.passport = None, project.kind
                    project.winner = p.id
                    if d.stage == Stage.ADULTEZ:
                        self.return_after_milestone_loss(d, return_youth_pos)
                elif outcome == 'derrota':
                    self.eco.spend(p.id, resource, loss, 'derrota_disputa_hito')
                    paid = loss
        self.eco.audit()
        result = DuelResult(kind, p.id, d.id, defense, attack, outcome, paid, paid_resource)
        self.events.append({'action':'duel', **result.__dict__, 'project':project_id,
                            'challenger_role':p.role, 'defender_role':d.role,
                            'same_role':p.role == d.role})
        return result

    def _vacate_house(self, owners: set[int]) -> bool:
        if self.eco.house_owner is None or not owners.intersection(self.eco.house_owner):
            return False
        for pid in self.eco.house_owner:
            ac = self.eco.accounts[pid]
            ac.free['A'] += ac.house_a
            ac.free['P'] += ac.house_p
            ac.house_a = ac.house_p = 0
        self.eco.house_owner = None
        self.events.append({'action':'house_lost','reason':'ruptura_o_hito'})
        return True

    def _preflight_youth(self, players: list[PlayerState], youth_pos: int):
        """Verifica cartas y descartes ANTES de tocar hitos o reservas."""
        if type(youth_pos) is not int or not 1 <= youth_pos <= 6:
            raise PendingRuleError('Posición juvenil de regreso pendiente 1..6')
        for p in players:
            if p.stage == Stage.ADULTEZ and p.hand.cards and self.engine.adult_deck is None:
                raise PendingRuleError('No existe mazo para devolver cartas adultas')
        need=sum(p.id not in self.engine._played and p.youth_movement is None for p in players)
        if need and not self.engine.youth_deck.can_draw(need):
            raise PendingRuleError('Faltan cartas de Juventud para regresar dentro de la ronda')
        for role in {p.role for p in players if p.id not in self.engine._played}:
            key=(Stage.JUVENTUD,role)
            if key not in self.engine._revealed and not self.engine.situation_decks[key].can_draw(1):
                raise PendingRuleError('Falta carta Situación del nuevo personaje juvenil')

    def _return_to_youth(self, players: list[PlayerState], youth_pos: int):
        self._preflight_youth(players, youth_pos)
        for p in players:
            if p.stage == Stage.ADULTEZ:
                for card in p.hand.cards:
                    self.engine.adult_deck.discard(card)
                p.hand = AdultHand(())
            p.stage, p.position = Stage.JUVENTUD, youth_pos
        # Personas que aún deben jugar esta ronda necesitan carta juvenil.
        for p in players:
            if p.id not in self.engine._played:
                if p.youth_movement is None:
                    self.engine._ensure_shared_situation(Stage.JUVENTUD, p.role)
                    (p.youth_movement,) = self.engine.youth_deck.draw()
        self.engine.validate()

    def return_after_milestone_loss(self, owner: PlayerState, youth_pos: int | None):
        if owner.stage != Stage.ADULTEZ:
            return
        if youth_pos is None:
            raise PendingRuleError('Falta convención de regreso juvenil')
        affected = [owner] + ([self.engine.players[owner.partner_id]] if owner.partner_id else [])
        self._vacate_house({q.id for q in affected})
        self._return_to_youth(affected, youth_pos)
        self.events.append({'action':'return_youth_after_hito','players':[q.id for q in affected],
                            'position':youth_pos, 'pair_preserved':True})
        self.eco.audit()

    def affect_pair_reserve(self, player_id: int, loss: int, *,
                            allow_partner_help: bool = True,
                            return_youth_pos: int | None = None) -> bool:
        """Efecto explícito sobre reserva de Pareja, seguido de ayuda inmediata.

        Devuelve True si la pareja sobrevive, False si se rompe. No se aplica
        a pérdidas ordinarias de saldo libre. El origen de este efecto debe
        ser una carta o disputa que afecte EXPRESSAMENTE recursos reservados.
        """
        p = self.engine.players[player_id]
        if p.partner_id is None:
            raise ValueError('No existe reserva de pareja sin compañero')
        mate = self.engine.players[p.partner_id]
        a = self.eco.accounts[p.id]
        b = self.eco.accounts[mate.id]
        if type(loss) is not int or not 0 < loss <= a.pair_a:
            raise ValueError('Pérdida de reserva inválida')
        deficit = 5 - (a.pair_a - loss)
        possible_help = a.free['A'] + (b.free['A'] if allow_partner_help else 0)
        if possible_help < deficit and p.stage == Stage.ADULTEZ:
            self._preflight_youth([p,mate],return_youth_pos)
        a.pair_a -= loss
        self.eco.burned['A'] += loss
        if possible_help >= deficit:
            donated = max(0, deficit - a.free['A'])
            if donated:
                self.eco.transfer(mate.id, p.id, 'A', donated)
            a.free['A'] -= deficit
            a.pair_a += deficit
            self.events.append({'action':'pair_reserve_repaired','player':p.id,
                                'lost':loss,'support_from_companion':donated})
            self.eco.audit()
            return True
        self.events.append({'action':'pair_reserve_not_repaired','player':p.id,'lost':loss})
        self.break_pair(p.id,return_youth_pos=return_youth_pos)
        return False

    def break_pair(self, player_id: int, *, return_youth_pos: int | None = None) -> bool:
        """Ruptura y liberación de reservas; no exige pérdida previa de amor.

        Debe invocarse cuando el orquestador de Situación confirma que una ayuda
        legal inmediata no restauró la reserva. Para pareja adulta, requiere
        casillero juvenil explícito y se separan las dos figuras al regresar.
        """
        p = self.engine.players[player_id]
        if p.partner_id is None:
            return False
        a,b = p, self.engine.players[p.partner_id]
        if a.stage == Stage.ADULTEZ:
            self._preflight_youth([a,b],return_youth_pos)
        self._vacate_house({a.id,b.id})
        for q in (a,b):
            ac = self.eco.accounts[q.id]
            ac.free['A'] += ac.pair_a
            ac.pair_a = 0
        if a.stage == Stage.ADULTEZ:
            self._return_to_youth([a,b], return_youth_pos)
        a.partner_id = b.partner_id = None
        self.eco.events.append({'action':'pair_broken','players':(a.id,b.id)})
        self.eco.audit()
        self.engine.validate()
        return True


@dataclass(frozen=True)
class AuctionCard:
    """Cartas de ejemplo/escenario: valores y elegibilidad los define cada carta."""
    id: str
    benefit_resource: str
    total: int
    appropriable: int
    mode: str  # fixed, heterogeneous, active_choice
    bid_resources: tuple[str,...]
    bid_order: tuple[int,...] | None = None  # fixture opcional de una ejecución, NO ID de carta física
    eligible_stages: tuple[Stage,...] = (Stage.INFANCIA, Stage.UTN, Stage.JUVENTUD, Stage.DUBLIN, Stage.ADULTEZ)
    eligible_roles: tuple[str,...] = ('Clarisa','Lucas')
    allow_reject: bool = False
    no_bid_effect: str = 'UNDEFINED'  # full / none, obligatorio definir por carta
    reject_effect: str = 'UNDEFINED'

    def __post_init__(self):
        if not self.id or self.benefit_resource not in RESOURCES:
            raise ValueError('ID y recurso de beneficio obligatorios')
        if type(self.total) is not int or type(self.appropriable) is not int or not 0 < self.appropriable <= self.total:
            raise ValueError('El beneficio apropiable debe ser positivo y <= total')
        if self.mode not in ('fixed','heterogeneous','active_choice'):
            raise ValueError('Modo de puja inválido')
        if len(set(self.bid_resources)) != len(self.bid_resources) or not self.bid_resources or any(x not in RESOURCES for x in self.bid_resources):
            raise ValueError('Recursos de puja inválidos')
        if (self.mode == 'fixed' and len(self.bid_resources) != 1) or (self.mode == 'active_choice' and len(self.bid_resources) != 2):
            raise ValueError('Cantidad de recursos incompatible con modalidad')
        if self.bid_order is not None and len(set(self.bid_order)) != len(self.bid_order):
            raise ValueError('Orden con jugadores duplicados')
        if self.no_bid_effect not in ('full','none') or self.reject_effect not in ('full','none'):
            raise PendingRuleError('Carta debe definir qué ocurre sin ofertas y tras rechazo')


@dataclass(frozen=True)
class Bid:
    player_id: int
    resource: str
    quantity: int


@dataclass(frozen=True)
class AuctionResult:
    active: int
    card_id: str
    winner: int | None
    best_bid: Bid | None
    bids: tuple[Bid, ...]
    passed: tuple[int, ...]
    credited_active: int
    credited_winner: int
    reason: str


class SocialAuctionsV2:
    """Sin segunda vuelta. Comparador heterogéneo expresado por el activo."""
    def __init__(self, economy: EconomyV2, engine: RoundEngine):
        self.eco, self.engine = economy, engine
        self.events: list[dict] = []
        self.used: set[tuple[int,int,str]] = set()

    def run(self, active_id: int, card: AuctionCard, *,
            bid_for: Callable[[PlayerState, Bid | None], Bid | None],
            select_winner: Callable[[tuple[Bid,...]], int | None],
            chosen_currency: str | None = None,
            bid_order: tuple[int, ...] | None = None,
            compare_heterogeneous: Callable[[Bid, Bid], int] | None = None) -> AuctionResult:
        p = self.engine.players[active_id]
        if p.stage != Stage.ADULTEZ:
            raise ValueError('Las subastas sociales son Situaciones de Adultez')
        token=(self.engine.round_no,active_id,card.id)
        if token in self.used:
            raise ValueError('Una Situación social solo puede ejecutarse una vez por jugador y ronda')
        allowed = {q.id for q in self.engine.players.values()
                   if q.id not in (p.id,p.partner_id)
                   and q.stage in card.eligible_stages and q.role in card.eligible_roles}
        order = bid_order if bid_order is not None else card.bid_order
        if order is None or len(order) != len(allowed) or set(order) != allowed:
            raise PendingRuleError('Orden de ejecución debe incluir cada participante elegible una vez')
        if card.mode == 'active_choice':
            if chosen_currency not in card.bid_resources:
                raise ValueError('El activo debe elegir entre los dos recursos ANTES de ofertar')
            allowed_resources = (chosen_currency,)
        else:
            allowed_resources = card.bid_resources
        if card.mode == 'heterogeneous' and compare_heterogeneous is None:
            raise PendingRuleError('Ofertas heterogéneas necesitan comparación subjetiva del activo')
        high: Bid | None = None
        tied: list[Bid] = []
        valid: list[Bid] = []
        passed: list[int] = []
        for pid in order:
            participant = self.engine.players[pid]
            bid = bid_for(participant, high)
            if bid is None:
                passed.append(pid)
                continue
            if (type(bid.quantity) is not int or bid.quantity < 1 or bid.player_id != pid
                or bid.resource not in allowed_resources):
                raise ValueError('Oferta inválida')
            if self.eco.accounts[pid].free[bid.resource] < bid.quantity:
                raise ValueError('Oferta no solvente (reservas no son libres)')
            comparison = 1 if high is None else (compare_heterogeneous(bid, high) if card.mode=='heterogeneous' else
                        (1 if bid.quantity > high.quantity else 0 if bid.quantity==high.quantity else -1))
            if type(comparison) is not int or comparison not in (-1,0,1):
                raise ValueError('Comparador debe devolver -1, 0 o 1')
            if comparison < 0:
                passed.append(pid)  # Si no iguala o mejora, pasa definitivamente.
                continue
            valid.append(bid)
            if comparison == 1:
                high, tied = bid, [bid]
            else:
                tied.append(bid)
        winner = None
        reason = 'no_bids' if not valid else 'awarded'
        bid_winner = None
        if valid:
            chosen = select_winner(tuple(tied))
            if chosen is None:
                if not card.allow_reject:
                    raise ValueError('La carta obliga adjudicar cuando hay oferta válida')
                reason = 'rejected'
            elif chosen not in [b.player_id for b in tied]:
                raise ValueError('El activo solo puede elegir entre las mejores ofertas')
            else:
                winner = chosen
                bid_winner = next(b for b in tied if b.player_id == chosen)
        if winner is not None:
            self.eco.transfer(winner, p.id, bid_winner.resource, bid_winner.quantity)
            active_amount = card.total - card.appropriable
            winner_amount = card.appropriable
            if active_amount:self.eco.issue(p.id,card.benefit_resource,active_amount,'subasta_remanente')
            self.eco.issue(winner,card.benefit_resource,winner_amount,'subasta_apropiacion')
        else:
            effect = card.no_bid_effect if reason == 'no_bids' else card.reject_effect
            active_amount = card.total if effect == 'full' else 0
            winner_amount = 0
            if active_amount:self.eco.issue(p.id,card.benefit_resource,active_amount,'subasta_sin_adjudicatario')
        self.eco.audit()
        result = AuctionResult(p.id,card.id,winner,bid_winner,tuple(valid),tuple(passed),active_amount,winner_amount,reason)
        self.used.add(token)
        self.events.append({'action':'social_auction',**result.__dict__,'offers_considered':len(order)})
        return result


def attach_social_situations(base: RuleHooks, auctions: SocialAuctionsV2,
                             *, bid_for: Callable[[PlayerState,Bid | None],Bid | None],
                             select_winner: Callable[[tuple[Bid,...]],int | None],
                             choose_currency: Callable[[PlayerState,AuctionCard],str] | None = None,
                             order_for: Callable[[PlayerState,AuctionCard,tuple[int,...]],tuple[int,...]] | None = None,
                             compare_heterogeneous: Callable[[Bid,Bid],int] | None = None) -> RuleHooks:
    """Conecta solo cartas expresamente tipadas AuctionCard; demás efectos intactos."""
    prior = base.apply_situation
    def resolver(engine:RoundEngine,p:PlayerState,card:SituationCard,letter:str | None):
        payload = card.payload
        if isinstance(payload,AuctionCard):
            if p.stage != Stage.ADULTEZ or card.stage != Stage.ADULTEZ:
                raise ValueError('Subasta social solo Adultez')
            eligible = tuple(q.id for q in engine.players.values()
                             if q.id not in (p.id,p.partner_id)
                             and q.stage in payload.eligible_stages and q.role in payload.eligible_roles)
            order = order_for(p,payload,eligible) if order_for is not None else payload.bid_order
            auctions.run(p.id,payload,bid_for=bid_for,select_winner=select_winner,
                         bid_order=order,
                         chosen_currency=(choose_currency(p,payload) if choose_currency else None),
                         compare_heterogeneous=compare_heterogeneous)
        else:
            prior(engine,p,card,letter)
    return replace(base,apply_situation=resolver)