"""Orquestador v2.0 aislado: ronda, seis mazos, A/B y pareja (sin economía)."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
import random
from typing import Callable, Generic, Iterable, TypeVar
from simulador.movimiento_v2 import AdultHand, Coord, MovementCard, walk_adult, walk_circuit


class PendingRuleError(RuntimeError):
    """Una regla de transición o de mazo todavía no está definida."""


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
    payload: object = None  # Efectos externos, no inventar cartas v2.0

    def __post_init__(self):
        if not self.id or self.stage not in SITUATION_STAGES or self.role not in ROLES:
            raise ValueError('Situación sin ID, etapa o personaje válidos')


T = TypeVar('T')


class CardPool(Generic[T]):
    """Robo sin reemplazo. Reciclado configurable EXPERIMENTAL, no oficial."""
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
        if not self.can_draw(n):
            raise PendingRuleError('Mazo insuficiente: se requiere política explícita')
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
            raise ValueError('Solo se descarta una carta retenida')
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
    """Puertos a reglas económicas y sociales futuras; NO efectúan pagos."""
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


class RoundEngine:
    def __init__(self, players: Iterable[PlayerState], situation_decks: dict,
                 youth_deck: CardPool[MovementCard],
                 adult_deck: CardPool[MovementCard] | None = None, *,
                 hand_size: int = 3,
                 rng_dice: random.Random | None = None,
                 hooks: RuleHooks | None = None):
        players = list(players)
        if hand_size not in (3, 4):
            raise ValueError('Mano adulta experimental de 3 o 4')
        if len(players) != len({p.id for p in players}):
            raise ValueError('ID duplicado')
        if set(situation_decks) != {(s, r) for s in SITUATION_STAGES for r in ROLES}:
            raise ValueError('Se requieren exactamente seis mazos de Situación')
        self.players = {p.id: p for p in players}
        self.turn_order = tuple(p.id for p in players)
        self.situation_decks = situation_decks
        self.youth_deck = youth_deck
        self.adult_deck = adult_deck
        self.hand_size = hand_size
        self.rng_dice = rng_dice or random.Random(1)
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
            elif p.stage in (Stage.DUBLIN, Stage.UTN, Stage.CASAMIENTO) and p.position != p.stage.value:
                raise ValueError('Posición de nodo exterior inválida')
            if p.partner_id is not None:
                mate = self.players.get(p.partner_id)
                if mate is None or mate.partner_id != p.id:
                    raise ValueError('Pareja no recíproca')
                if mate.stage != p.stage or mate.position != p.position:
                    raise ValueError('Pareja no comparte etapa y posición')
                if mate.role == p.role:
                    raise ValueError('Pareja solo Clarisa + Lucas')

    def members(self, active: PlayerState) -> list[PlayerState]:
        return [active] + ([self.players[active.partner_id]] if active.partner_id else [])

    def _event(self, action: str, **fields):
        self.events.append({'round': self.round_no, 'action': action, **fields})

    def start_round(self):
        if self.round_no and len(self._played) != len(self.players):
            raise ValueError('Ronda anterior no finalizada')
        for p in self.players.values():
            if p.youth_movement is not None:
                self.youth_deck.discard(p.youth_movement)
                p.youth_movement = None
        for card in self._revealed.values():
            self.situation_decks[(card.stage, card.role)].discard(card)
        self._revealed = {}
        self._cohort = {(p.stage, p.role) for p in self.players.values()
                        if p.stage in (Stage.JUVENTUD, Stage.ADULTEZ)}
        youth = sorted((p for p in self.players.values() if p.stage == Stage.JUVENTUD),
                       key=lambda p: p.id)
        if not self.youth_deck.can_draw(len(youth)):
            raise PendingRuleError('No hay cartas juveniles suficientes para la ronda')
        for key in self._cohort:
            if not self.situation_decks[key].can_draw(1):
                raise PendingRuleError(f'Mazo de Situación agotado: {key}')
        self.round_no += 1
        cards = self.youth_deck.draw(len(youth)) if youth else ()
        for p, card in zip(youth, cards):
            p.youth_movement = card
            self._event('youth_dealt', player=p.id, card=card.id)
        for key in sorted(self._cohort, key=lambda k: (k[0].value, k[1])):
            card, = self.situation_decks[key].draw()
            self._revealed[key] = card
            self._event('situation_revealed', stage=key[0].value,
                        role=key[1], card=card.id)
        self._played = set()
        self._turn_index = 0
        self._event('round_start', cohorts=len(self._cohort))

    def _situation(self, p: PlayerState, choice: str | None):
        if p.stage == Stage.UTN:
            raise PendingRuleError('Reintento UTN: tratamiento de Situación pendiente')
        if p.stage == Stage.DUBLIN:
            raise PendingRuleError('Dublín: transición de ronda pendiente')
        if p.stage == Stage.INFANCIA:
            deck = self.situation_decks[(p.stage, p.role)]
            card, = deck.draw()
        else:
            card = self._revealed.get((p.stage, p.role))
            if card is None:
                raise PendingRuleError('Etapa/personaje sin Situación revelada en la ronda')
            deck = None
        before = p.stage
        try:
            self.hooks.apply_situation(self, p, card, choice)
        finally:
            if deck is not None:
                deck.discard(card)
        self._event('situation_resolved', player=p.id, card=card.id, choice=choice)
        if p.stage != before:
            if p.stage == Stage.JUVENTUD and p.youth_movement is None:
                raise PendingRuleError('Cambio a Juventud: falta política de reparto')
            if p.stage == Stage.ADULTEZ and self.adult_deck is None:
                raise PendingRuleError('Entrada adulta sin mazo')
        return card

    def _renew_adult_if_empty(self, p: PlayerState):
        if p.hand.exhausted:
            if self.adult_deck is None:
                raise PendingRuleError('Composición del mazo adulto no definida')
            p.hand = p.hand.renew(self.adult_deck.draw(self.hand_size))
            self._event('hand_renewed', player=p.id, cards=[c.id for c in p.hand.cards])

    def play_turn(self, player_id: int, *,
                  youth_choice: Callable[[PlayerState, SituationCard, MovementCard], str] | None = None,
                  adult_choice: Callable[[PlayerState, SituationCard, AdultHand], AdultChoice] | None = None,
                  childhood_die: int | None = None) -> TurnOutcome:
        if not self.round_no or player_id in self._played or self._turn_index >= len(self.turn_order):
            raise ValueError('Ronda no iniciada o turno repetido')
        if player_id != self.turn_order[self._turn_index]:
            raise ValueError('Debe respetarse el orden global de turnos')
        p = self.players[player_id]
        if p.stage in (Stage.UTN, Stage.DUBLIN):
            raise PendingRuleError('Turno en nodo especial: transición aún no definida')
        stage, source = p.stage, p.position
        movement_card_id, distance, letter = None, None, None
        if stage == Stage.JUVENTUD:
            card = self._revealed.get((stage, p.role))
            if card is None or p.youth_movement is None:
                raise PendingRuleError('Jugador juvenil sin carta repartida')
            if youth_choice is None:
                raise ValueError('Falta política de elección juvenil')
            letter = youth_choice(p, card, p.youth_movement)
            if letter not in ('A', 'B'):
                raise ValueError('Elección A/B ilegal')
        elif stage == Stage.INFANCIA and childhood_die is not None:
            if type(childhood_die) is not int or not 1 <= childhood_die <= 6:
                raise ValueError('D6 fuera de 1..6')
        situation = self._situation(p, letter)
        if p.stage != stage:
            raise PendingRuleError('Cambio de etapa por Situación: política pendiente')
        members = self.members(p)
        if stage == Stage.INFANCIA:
            distance = childhood_die if childhood_die is not None else self.rng_dice.randint(1, 6)
            route = walk_circuit(p.position, distance)
            for i, pos in enumerate(route.visited):
                for member in members:
                    member.position = pos
                    self.hooks.on_step(self, member, pos, i == len(route.visited)-1)
            target = 'casillero_infancia'
            for member in members:
                self.hooks.on_destination(self, member, target)
        elif stage == Stage.JUVENTUD:
            movement_card_id = p.youth_movement.id
            distance = p.youth_movement.distance(letter)
            route = walk_circuit(p.position, distance)
            for i, pos in enumerate(route.visited):
                previous = (pos - 2) % 6 + 1
                for member in members:
                    member.position = pos
                    if previous == 6 and pos == 1:
                        self.hooks.on_profile(self, member, 'vuelta_juventud')
                    self.hooks.on_step(self, member, pos, i == len(route.visited)-1)
            target = 'Universidad' if route.destination in (1,4) else (
                'Tramite' if route.destination in (2,5) else 'Vacio')
            for member in members:
                self.hooks.on_destination(self, member, target)
        elif stage == Stage.ADULTEZ:
            self._renew_adult_if_empty(p)
            if adult_choice is None:
                raise ValueError('Falta elección adulta')
            decision = adult_choice(p, situation, p.hand)
            selected = next((c for c in p.hand.cards if c.id == decision.card_id), None)
            if selected is None:
                raise ValueError('Carta fuera de mano')
            distance = selected.distance(decision.letter)
            route = walk_adult(p.position, distance, decision.direction,
                               marriage_eligible=(p.partner_id is not None and self.hooks.marriage_eligible(self,p)),
                               exit_after=decision.exit_after)
            movement_card_id, letter = selected.id, decision.letter
            if self.adult_deck is None:
                raise PendingRuleError('Mazo adulto necesario para el descarte')
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
            raise PendingRuleError(f'Etapa no implementada: {stage}')
        result = TurnOutcome(self.round_no, p.id, situation.id, letter,
                             movement_card_id, distance, source, p.position, target)
        self._played.add(p.id)
        self._turn_index += 1
        self._event('movement', player=p.id, card=movement_card_id, choice=letter,
                    distance=distance, origin=str(source),
                    destination=str(p.position), target=target)
        self.hooks.after_turn(self, p, result)
        self.validate()
        return result
