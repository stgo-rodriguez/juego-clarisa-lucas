"""Orquestador aislado de rondas y turnos v2.0, SIN economía ni cartas inventadas.

La elección A/B de Juventud enlaza Situación y Movimiento. En Adultez,
la Situación es independiente de la carta de Movimiento. Las decisiones
pendientes se expresan mediante excepciones o políticas experimentales.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import random
from typing import Callable, Generic, Iterable, TypeVar

from simulador.movimiento_v2 import (
    AdultHand, AdultRoute, Coord, MovementCard, walk_adult,
    walk_circuit, cell_at, youth_cards,
)


class PendingRuleError(RuntimeError):
    """Una situación requiere una regla no cerrada en la v2.0."""


class Stage(str, Enum):
    INFANCIA = 'Infancia'
    UTN = 'UTN'
    JUVENTUD = 'Juventud'
    DUBLIN = 'Vuelo a Dublín'
    ADULTEZ = 'Adultez'
    CASAMIENTO = 'Casamiento'


ROLES = ('Clarisa', 'Lucas')
SITUATION_STAGES = (Stage.INFANCIA, Stage.JUVENTUD, Stage.ADULTEZ)


@dataclass(frozen=True)
class SituationCard:
    id: str
    stage: Stage
    role: str
    payload: object = None  # Texto/efectos externos aún no aprobados

    def __post_init__(self):
        if not self.id or self.stage not in SITUATION_STAGES or self.role not in ROLES:
            raise ValueError('Situación sin ID, etapa o personaje válidos')


T = TypeVar('T')


class CardPool(Generic[T]):
    """Robo sin reemplazo; reciclado opcional explícito; cartas retenidas fuera.

    La política de reciclado 'recycle' es experimental, NO regla oficial.
    No es legal introducir en el descarte una carta aún retenida en otra mano.
    """
    def __init__(self, cards: Iterable[T], rng: random.Random, *, recycle: bool = False):
        cards = list(cards)
        ids = [c.id for c in cards]
        if not cards or len(set(ids)) != len(ids):
            raise ValueError('Mazo vacío o cartas duplicadas')
        self._deck = cards
        self._rng = rng
        self._rng.shuffle(self._deck)
        self._discard: list[T] = []
        self._held: dict[str, T] = {}
        self._all_ids = frozenset(ids)
        self.recycle = recycle

    @property
    def available(self) -> int:
        return len(self._deck)

    @property
    def held(self) -> int:
        return len(self._held)

    def can_draw(self, n: int) -> bool:
        return 0 <= n <= len(self._deck) + (len(self._discard) if self.recycle else 0)

    def draw(self, n: int = 1) -> tuple[T, ...]:
        if type(n) is not int or n < 1:
            raise ValueError('Cantidad de robo inválida')
        # Verificar previamente para no modificar el estado si falta stock.
        possible = len(self._deck) + (len(self._discard) if self.recycle else 0)
        if n > possible:
            raise PendingRuleError('Mazo insuficiente: completar/reciclar requiere política explícita')
        result = []
        for _ in range(n):
            if not self._deck:
                self._deck, self._discard = self._discard, []
                self._rng.shuffle(self._deck)
            card = self._deck.pop()
            if card.id in self._held:
                raise AssertionError('Carta ya retenida')
            self._held[card.id] = card
            result.append(card)
        return tuple(result)

    def discard(self, card: T) -> None:
        held = self._held.pop(card.id, None)
        if held is None or held != card:
            raise ValueError('Solo puede descartarse una carta realmente retenida')
        self._discard.append(card)

    def assert_conservation(self) -> None:
        ids = [c.id for c in self._deck] + [c.id for c in self._discard] + list(self._held)
        if len(ids) != len(set(ids)) or set(ids) != self._all_ids:
            raise AssertionError('Conservación de cartas violada')


@dataclass
class PlayerState:
    id: int
    role: str
    stage: Stage = Stage.INFANCIA
    position: int | Coord | str = 1
    partner_id: int | None = None
    hand: AdultHand = field(default_factory=lambda: AdultHand(()))
    youth_movement: MovementCard | None = None
    utn_passed: bool = False  # Aprobación permanente; pasa a Juventud en siguiente ronda.

    def __post_init__(self):
        if type(self.id) is not int or self.id < 1 or self.role not in ROLES:
            raise ValueError('Jugador inválido')


@dataclass(frozen=True)
class AdultChoice:
    card_id: str
    letter: str
    direction: str | None
    exit_after: int | None = None


@dataclass(frozen=True)
class TurnOutcome:
    round_no: int
    active: int
    situation_id: str | None
    choice: str | None
    movement_card_id: str | None
    distance: int | None
    source: object
    destination: object
    target: str | None


@dataclass
class RuleHooks:
    """Puertos del motor futuro: solo notificaciones, no economía implícita."""
    apply_situation: Callable[['RoundEngine', PlayerState, SituationCard, str | None], None] = (
        lambda engine, p, card, choice: None)
    on_step: Callable[['RoundEngine', PlayerState, int, bool], None] = (
        lambda engine, p, pos, last: None)
    on_profile: Callable[['RoundEngine', PlayerState, str], None] = (
        lambda engine, p, cause: None)
    on_destination: Callable[['RoundEngine', PlayerState, str], None] = (
        lambda engine, p, target: None)
    after_turn: Callable[['RoundEngine', PlayerState, TurnOutcome], None] = (
        lambda engine, p, outcome: None)
    marriage_eligible: Callable[['RoundEngine', PlayerState], bool] = (
        lambda engine, p: False)
    utn_eligible: Callable[['RoundEngine', PlayerState], bool] = (
        lambda engine, p: False)
    utn_pass: Callable[['RoundEngine', PlayerState], None] | None = None
    dublin_exit: Callable[['RoundEngine', PlayerState], bool] = (
        lambda engine, p: False)
    dublin_land: Callable[['RoundEngine', PlayerState], None] | None = None


class RoundEngine:
    def __init__(self, players: Iterable[PlayerState], situation_decks: dict,
                 youth_deck: CardPool[MovementCard],
                 adult_deck: CardPool[MovementCard] | None = None, *,
                 hand_size: int = 3,
                 rng_dice: random.Random | None = None,
                 hooks: RuleHooks | None = None,
                 dublin_policy: str = 'next_round'):
        players = list(players)
        if hand_size not in (3, 4):
            raise ValueError('Mano adulta experimental de 3 o 4')
        if dublin_policy not in ('next_round','next_turn'):
            raise ValueError('Política de Dublín no reconocida')
        if len(players) != len({p.id for p in players}):
            raise ValueError('ID de jugadores duplicado')
        if set(situation_decks) != {(s, r) for s in SITUATION_STAGES for r in ROLES}:
            raise ValueError('Se requieren exactamente seis mazos de Situación')
        self.players = {p.id: p for p in players}
        self.turn_order = tuple(p.id for p in players)
        self.situation_decks = situation_decks
        self.youth_deck = youth_deck
        self.adult_deck = adult_deck
        self.hand_size = hand_size
        self.dublin_policy = dublin_policy  # Ambas variantes son experimentales.        self.rng_dice = rng_dice or random.Random(1)
        self.hooks = hooks or RuleHooks()
        self.round_no = 0
        self._cohort: set[tuple[Stage, str]] = set()
        self._revealed: dict[tuple[Stage, str], SituationCard] = {}
        self._played: set[int] = set()
        self._turn_index = 0
        self.events: list[dict] = []
        self.validate()

    def validate(self):
        for p in self.players.values():
            if p.stage in (Stage.INFANCIA, Stage.JUVENTUD):
                if type(p.position) is not int or not 1 <= p.position <= 6:
                    raise ValueError('Circuito requiere posición 1..6')
            elif p.stage == Stage.ADULTEZ and not isinstance(p.position, Coord):
                raise ValueError('Adultez requiere coordenada 5x5')
            elif p.stage == Stage.DUBLIN and p.position != Stage.DUBLIN.value:
                raise ValueError('Dublín es nodo exterior')
            elif p.stage == Stage.UTN and p.position != Stage.UTN.value:
                raise ValueError('UTN es nodo exterior')
            elif p.stage == Stage.CASAMIENTO and p.position != Stage.CASAMIENTO.value:
                raise ValueError('Casamiento es nodo exterior')
            if p.partner_id is not None:
                mate = self.players.get(p.partner_id)
                if mate is None or mate.partner_id != p.id:
                    raise ValueError('Pareja no recíproca')
                if mate.stage != p.stage or mate.position != p.position:
                    raise ValueError('Pareja no comparte posición y etapa')
                if mate.role == p.role:
                    raise ValueError('Pareja solo entre Clarisa y Lucas')

    def members(self, active: PlayerState) -> list[PlayerState]:
        return [active] + ([self.players[active.partner_id]] if active.partner_id else [])

    def _event(self, action: str, **fields):
        self.events.append({'round': self.round_no, 'action': action, **fields})

    def start_round(self):
        if self.round_no and len(self._played) != len(self.players):
            raise ValueError('La ronda anterior aún no finalizó')
        # Política experimental Fase 4: transición sincronizada con la ronda.
        # El ingreso no consume un movimiento, y el Perfil de Dublín se activa
        # ANTES de repartir o revelar las cartas correspondientes a la ronda.
        for p in self.players.values():
            if p.stage == Stage.UTN and p.utn_passed:
                p.stage, p.position = Stage.JUVENTUD, 1
                self._event('utn_to_youth', player=p.id)
        if self.dublin_policy == 'next_round':
            landed: set[int] = set()
            for p in self.players.values():
                if p.stage == Stage.DUBLIN and p.id not in landed:
                    if self.hooks.dublin_land is not None:
                        other_id=p.partner_id
                        self._land_dublin(p)
                        landed.update((p.id,other_id))
        # Las cartas juveniles son de una ronda. Descartar al iniciar la siguiente.
        for p in self.players.values():
            if p.youth_movement is not None:
                self.youth_deck.discard(p.youth_movement)
                p.youth_movement = None
        for card in self._revealed.values():
            self.situation_decks[(card.stage, card.role)].discard(card)
        self._revealed = {}
        self._cohort = {(p.stage, p.role) for p in self.players.values()
                        if p.stage in (Stage.JUVENTUD, Stage.ADULTEZ)}
        # Comprobación previa de stock de todos los mazos; no se reparten
        # cartas a solo algunos si faltan cartas en otro mazo.
        youth = sorted((p for p in self.players.values() if p.stage == Stage.JUVENTUD), key=lambda p:p.id)
        if not self.youth_deck.can_draw(len(youth)):
            raise PendingRuleError('No hay cartas juveniles suficientes para toda la ronda')
        for key in self._cohort:
            if not self.situation_decks[key].can_draw(1):
                raise PendingRuleError(f'Mazo de Situación agotado: {key}')
        self.round_no += 1
        cards = self.youth_deck.draw(len(youth)) if youth else ()
        for p, card in zip(youth, cards):
            p.youth_movement = card
            self._event('youth_dealt',player=p.id,card=card.id)
        for key in sorted(self._cohort, key=lambda k:(k[0].value,k[1])):
            self._ensure_shared_situation(*key)
        self._played = set()
        self._turn_index = 0
        self._event('round_start',cohorts=len(self._cohort))

    def _situation(self, p: PlayerState, choice: str | None):
        if p.stage == Stage.UTN:
            raise PendingRuleError('Reintento UTN: tratamiento de Situación pendiente')
        if p.stage == Stage.DUBLIN:
            raise PendingRuleError('Entrada desde Dublín a mitad de ronda: regla pendiente')
        if p.stage == Stage.INFANCIA:
            deck = self.situation_decks[(p.stage, p.role)]
            card, = deck.draw()
        else:
            card = self._revealed.get((p.stage, p.role))
            if card is None:
                raise PendingRuleError('Entró a etapa/personaje sin Situación revelada en la ronda')
            deck = None
        before = p.stage
        try:
            self.hooks.apply_situation(self, p, card, choice)
        finally:
            if deck is not None:
                deck.discard(card)
        self._event('situation_resolved',player=p.id,card=card.id,choice=choice)
        if p.stage != before:
            # Regla cerrada: el cambio de etapa ocurre antes del movimiento;
            # regla pendiente: asignación de carta en nueva etapa esta ronda.
            if p.stage == Stage.JUVENTUD and p.youth_movement is None:
                raise PendingRuleError('Cambio a Juventud en el turno: falta política de reparto de Movimiento')
            if p.stage == Stage.ADULTEZ and self.adult_deck is None:
                raise PendingRuleError('Entrada a Adultez sin mazo de Movimiento')
        return card

    def _renew_adult_if_empty(self, p: PlayerState):
        if p.hand.exhausted:
            if self.adult_deck is None:
                raise PendingRuleError('Composición del mazo de Movimiento de Adultez no definida')
            p.hand = p.hand.renew(self.adult_deck.draw(self.hand_size))
            self._event('hand_renewed',player=p.id,cards=[c.id for c in p.hand.cards])

    def _land_dublin(self,p: PlayerState) -> None:
        if p.stage!=Stage.DUBLIN or p.partner_id is None:
            raise PendingRuleError('Dublín requiere pareja en el nodo exterior')
        if self.hooks.dublin_land is None:
            raise PendingRuleError('Dublín requiere política de colocación')
        other=self.players[p.partner_id]
        self.hooks.dublin_land(self,p)
        if any(q.stage!=Stage.ADULTEZ or q.position!=Coord(5,3) for q in (p,other)):
            raise AssertionError('Dublín debe colocar a los dos en (5,3)')
        self._event('dublin_to_adult',players=sorted((p.id,other.id)),
                    policy=self.dublin_policy)

    def _ensure_shared_situation(self,stage: Stage,role: str):
        key=(stage,role)
        if key in self._revealed:return self._revealed[key]
        deck=self.situation_decks[key]
        if not deck.can_draw(1):
            raise PendingRuleError(f'Mazo de Situación agotado: {key}')
        card,=deck.draw()
        self._revealed[key]=card
        self._cohort.add(key)
        self._event('situation_revealed',stage=stage.value,role=role,card=card.id)
        return card

    def _attempt_utn(self,p: PlayerState,die: int | None) -> bool:
        if self.hooks.utn_pass is None:
            raise PendingRuleError('UTN: falta asignación de Perfil-Afinidad')
        value = die if die is not None else self.rng_dice.randint(1,6)
        if not 1<=value<=6:raise ValueError('D6 UTN inválido')
        passed=value>=4
        if passed:
            if self.hooks.utn_pass is None:
                raise PendingRuleError('UTN aprobada: falta asignación de Perfil-Afinidad')
            self.hooks.utn_pass(self,p)
            p.utn_passed=True
        self._event('utn_exam',player=p.id,die=value,passed=passed)
        return passed

    def play_turn(self, player_id: int, *,
                  youth_choice: Callable[[PlayerState, SituationCard, MovementCard], str] | None = None,
                  adult_choice: Callable[[PlayerState, SituationCard, AdultHand], AdultChoice] | None = None,
                  childhood_die: int | None = None,
                  utn_die: int | None = None,
                  choose_utn: bool = False,
                  choose_dublin: bool = False) -> TurnOutcome:
        if not self.round_no or player_id in self._played or self._turn_index >= len(self.turn_order):
            raise ValueError('La ronda no empezó o el jugador ya actuó')
        if player_id != self.turn_order[self._turn_index]:
            raise ValueError('Debe respetarse el orden global de turnos')
        p = self.players[player_id]
        if p.stage==Stage.DUBLIN and self.dublin_policy=='next_turn':
            self._land_dublin(p)
            # Entrante de mitad de ronda: si no existía esa cohorte, revelar
            # UNA situación del rol, compartida con adultos posteriores.
            self._ensure_shared_situation(Stage.ADULTEZ,p.role)
        if p.stage==Stage.ADULTEZ and (Stage.ADULTEZ,p.role) not in self._revealed:
            self._ensure_shared_situation(Stage.ADULTEZ,p.role)
        if utn_die is not None and (type(utn_die) is not int or not 1 <= utn_die <= 6):
            raise ValueError('D6 UTN debe ser 1..6')
        if p.stage in (Stage.UTN,Stage.DUBLIN):
            source=p.position
            target=p.stage.value
            if p.stage==Stage.UTN:
                if p.utn_passed:
                    raise AssertionError('UTN aprobada debe avanzar al comienzo de ronda')
                self._attempt_utn(p,utn_die)
            else:
                if self.hooks.dublin_land is None:
                    raise PendingRuleError('Dublín: falta política explícita de colocación')
                self._event('dublin_wait_experimental',player=p.id)
            result=TurnOutcome(self.round_no,p.id,None,None,None,None,source,p.position,target)
            self._played.add(p.id)
            self._turn_index+=1
            self.hooks.after_turn(self,p,result)
            self.validate()
            return result
        stage = p.stage
        source = p.position
        movement_card_id, distance, letter = None, None, None
        adult_decision = None
        if stage == Stage.JUVENTUD:
            card = self._revealed.get((p.stage, p.role))
            if card is None or p.youth_movement is None:
                raise PendingRuleError('Jugador entró en Juventud sin reparto de su ronda')
            if youth_choice is None:
                raise ValueError('Se requiere política de elección A/B juvenil')
            letter = youth_choice(p, card, p.youth_movement)
            if letter not in ('A', 'B'):
                raise ValueError('Elección A/B ilegal')
        elif stage == Stage.INFANCIA and childhood_die is not None:
            if type(childhood_die) is not int or not 1 <= childhood_die <= 6:
                raise ValueError('D6 debe ser 1..6')

        situation = self._situation(p, letter)
        # Si cambió etapa, la elección de movimiento anterior ya no sirve.
        if p.stage != stage:
            raise PendingRuleError('Cambio de etapa durante Situación: política de Movimiento aún sin aprobar')
        members = self.members(p)
        if p.stage == Stage.INFANCIA:
            distance = childhood_die if childhood_die is not None else self.rng_dice.randint(1, 6)
            route = walk_circuit(p.position, distance)
            branched = False
            for i, pos in enumerate(route.visited):
                for member in members:
                    member.position=pos
                    self.hooks.on_step(self,member,pos,i==len(route.visited)-1)
                # El ingreso UTN solo puede verificarse DESPUÉS de cobrar +2 P.
                if (pos==5 and choose_utn and
                    self.hooks.utn_eligible(self,p)):
                    if self.hooks.utn_pass is None:
                        raise PendingRuleError('UTN: falta asignación de Perfil-Afinidad')
                    p.stage,p.position = Stage.UTN,Stage.UTN.value
                    self._event('enter_utn',player=p.id,discarded=distance-i-1)
                    self._attempt_utn(p,utn_die)
                    branched=True
                    break
            target=Stage.UTN.value if branched else 'casillero_infancia'
            if not branched:
                for member in members:
                    self.hooks.on_destination(self,member,target)
        elif p.stage == Stage.JUVENTUD:
            movement_card_id = p.youth_movement.id
            distance = p.youth_movement.distance(letter)
            route = walk_circuit(p.position, distance)
            for i, pos in enumerate(route.visited):
                before = (pos - 2) % 6 + 1  # inmediatamente anterior en círculo
                for member in members:
                    member.position = pos
                    if before == 6 and pos == 1:
                        self.hooks.on_profile(self, member, 'vuelta_juventud')
                    self.hooks.on_step(self, member, pos, i == len(route.visited)-1)
            target = 'Universidad' if route.destination in (1, 4) else 'Tramite' if route.destination in (2,5) else 'Vacio'
            for member in members:
                self.hooks.on_destination(self,member,target)
            if choose_dublin and target=='Tramite' and p.partner_id is not None:
                if self.hooks.dublin_exit(self,p):
                    target=Stage.DUBLIN.value
                    self._event('enter_dublin_from_youth',player=p.id)
        elif p.stage == Stage.ADULTEZ:
            self._renew_adult_if_empty(p)
            if adult_choice is None:
                raise ValueError('Se requiere política de carta/dirección adulta')
            adult_decision = adult_choice(p, situation, p.hand)
            selected = next((card for card in p.hand.cards if card.id == adult_decision.card_id), None)
            if selected is None:
                raise ValueError('Carta no pertenece a la mano')
            distance = selected.distance(adult_decision.letter)
            allowed = p.partner_id is not None and self.hooks.marriage_eligible(self, p)
            route = walk_adult(p.position, distance, adult_decision.direction,
                               marriage_eligible=allowed,exit_after=adult_decision.exit_after)
            movement_card_id = selected.id
            letter = adult_decision.letter
            if self.adult_deck is None:
                raise PendingRuleError('No hay mazo adulto para administrar descartes')
            _, _, p.hand = p.hand.play(movement_card_id, letter)
            self.adult_deck.discard(selected)
            for member in members:
                member.position = route.destination
                if route.destination == Stage.CASAMIENTO.value:
                    member.stage = Stage.CASAMIENTO
            target = route.activation
            if target == 'Perfil':
                for member in members:
                    self.hooks.on_profile(self, member, 'caida_perfil_adultez')
            for member in members:
                self.hooks.on_destination(self, member, target)
        else:
            raise PendingRuleError(f'Etapa no implementada: {p.stage}')
        result = TurnOutcome(self.round_no, p.id, situation.id, letter,
                             movement_card_id, distance, source, p.position, target)
        self._played.add(p.id)
        self._turn_index += 1
        self._event('movement',player=p.id,card=movement_card_id,choice=letter,
                    distance=distance,origin=str(source),destination=str(p.position),target=target)
        self.hooks.after_turn(self, p, result)
        self.validate()
        return result