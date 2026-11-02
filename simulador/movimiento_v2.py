"""Motor geométrico independiente del reglamento económico de Clarisa & Lucas v2.0.

Fuente: Especificación Integral v2.0 Consolidada (01-11-2026), secciones
5, 7, 11-13 y anexo. Sin efectos de Situación, dinero, IA ni supuestos
sobre tamaño/composición del mazo de Adultez.

Convención: coordenadas 1..5 (fila, columna). Rebotes *no* consumen pasos;
cada paso entra realmente en una casilla. Las rutas con salida a Casamiento
solo se habilitan cuando el motor superior verifica requisitos.
"""
from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Iterable

BOARD_SIZE = 5
CASAMIENTO = 'Casamiento'
DIRECTIONS = {
    'N': (-1, 0), 'NE': (-1, 1), 'E': (0, 1), 'SE': (1, 1),
    'S': (1, 0), 'SO': (1, -1), 'O': (0, -1), 'NO': (-1, -1),
}
MARRIAGE_GATES = frozenset((1, c) for c in (2, 3, 4))
BOARD = (
    ('K', '.', '.', '.', 'A'),
    ('M', '.', '.', '.', '.'),
    ('.', '.', 'Casa', '.', 'M'),
    ('.', 'P', '.', '.', '.'),
    ('.', 'A', 'Perfil', '.', '.'),
)


@dataclass(frozen=True, order=True)
class Coord:
    row: int
    col: int

    def __post_init__(self) -> None:
        if not (1 <= self.row <= BOARD_SIZE and 1 <= self.col <= BOARD_SIZE):
            raise ValueError(f'Coordenada fuera del tablero: {self}')


def cell_at(coord: Coord) -> str:
    """Tipo de casillero. No atribuye cantidades de recursos pendientes."""
    return BOARD[coord.row - 1][coord.col - 1]


def valid_directions(start: Coord) -> tuple[str, ...]:
    """Solo direcciones con PRIMER paso dentro: 8, 5 o 3 según origen."""
    return tuple(name for name, (dr, dc) in DIRECTIONS.items()
                 if 1 <= start.row + dr <= BOARD_SIZE
                 and 1 <= start.col + dc <= BOARD_SIZE)


@dataclass(frozen=True)
class AdultRoute:
    origin: Coord
    distance: int
    direction: str | None
    visited: tuple[Coord, ...]        # Casilleros realmente atravesados
    destination: Coord | str          # Coord o nodo exterior Casamiento
    consumed: int                    # Pasos realmente consumidos
    discarded: int                   # Restantes al entrar en Casamiento
    reflections: tuple[tuple[int, str], ...]  # (número de paso, eje reflejado)

    @property
    def activation(self) -> str:
        # Solo el destino: nunca genera activación una casilla intermedia.
        return CASAMIENTO if self.destination == CASAMIENTO else cell_at(self.destination)


def walk_adult(
    start: Coord,
    distance: int,
    direction: str | None,
    *,
    marriage_eligible: bool = False,
    exit_after: int | None = None,
) -> AdultRoute:
    """Camina una carta A/B (1..6), con rebotes y salida voluntaria opcional.

    exit_after=k: caminar k casillas interiores y luego entrar al nodo exterior
    desde una de las 3 puertas, consumiendo el paso k+1. Se descarta el resto.
    exit_after=0 permite salir directamente desde una puerta, sin dirección
    interior. El motor integral decide cuándo la pareja está habilitada.
    """
    if not isinstance(start, Coord):
        raise TypeError('start debe ser Coord')
    if type(distance) is not int or not 1 <= distance <= 6:
        raise ValueError('La distancia A/B debe estar entre 1 y 6')
    if exit_after is not None:
        if not marriage_eligible:
            raise ValueError('No puede salir a Casamiento sin requisitos verificados')
        if type(exit_after) is not int or not 0 <= exit_after < distance:
            raise ValueError('La salida consume 1 paso: k debe ser 0..distancia-1')
    steps_in_grid = distance if exit_after is None else exit_after
    if steps_in_grid > 0 or exit_after is None:
        if direction not in DIRECTIONS:
            raise ValueError('Dirección inicial inválida')
        if direction not in valid_directions(start):
            raise ValueError('No se permite apuntar fuera del tablero al empezar')
    elif direction is not None and direction not in DIRECTIONS:
        raise ValueError('Dirección inválida')

    r, c = start.row, start.col
    dr, dc = DIRECTIONS[direction] if steps_in_grid else (0, 0)
    visited: list[Coord] = []
    reflections: list[tuple[int, str]] = []
    for step in range(1, steps_in_grid + 1):
        reverse_row = not (1 <= r + dr <= BOARD_SIZE)
        reverse_col = not (1 <= c + dc <= BOARD_SIZE)
        if reverse_row:
            dr = -dr
        if reverse_col:
            dc = -dc
        if reverse_row or reverse_col:
            axis = 'ambos' if reverse_row and reverse_col else 'fila' if reverse_row else 'columna'
            reflections.append((step, axis))
        r, c = r + dr, c + dc
        visited.append(Coord(r, c))

    dest = Coord(r, c)
    if exit_after is not None:
        if (r, c) not in MARRIAGE_GATES:
            raise ValueError('Casamiento solo conecta con (1,2), (1,3) y (1,4)')
        return AdultRoute(start, distance, direction, tuple(visited), CASAMIENTO,
                          exit_after + 1, distance - exit_after - 1, tuple(reflections))
    return AdultRoute(start, distance, direction, tuple(visited), dest,
                      distance, 0, tuple(reflections))


def adult_options(start: Coord, distance: int, *, marriage_eligible: bool = False) -> tuple[AdultRoute, ...]:
    """Rutas legales: movimientos completos y, si procede, salidas en el trayecto."""
    routes: list[AdultRoute] = []
    if marriage_eligible and (start.row, start.col) in MARRIAGE_GATES:
        routes.append(walk_adult(start, distance, None, marriage_eligible=True, exit_after=0))
    for direction in valid_directions(start):
        full = walk_adult(start, distance, direction)
        routes.append(full)
        if marriage_eligible:
            for k, coord in enumerate(full.visited[:-1], start=1):
                if (coord.row, coord.col) in MARRIAGE_GATES:
                    routes.append(walk_adult(start, distance, direction,
                                             marriage_eligible=True, exit_after=k))
    return tuple(routes)


@dataclass(frozen=True)
class CircuitRoute:
    origin: int
    visited: tuple[int, ...]
    destination: int
    lap_crossings: int
    consumed: int
    discarded: int


def walk_circuit(start: int, distance: int, *, early_exit_at: int | None = None) -> CircuitRoute:
    """Circuitos de 6 posiciones (Infancia/Juventud), sin efecto económico.

    early_exit_at permite la bifurcación tras visitar ese casillero, si el
    motor de reglas verificó sus requisitos. No se activa una salida por estar
    ya parado en esa casilla: se requiere llegar durante el movimiento.
    """
    if type(start) is not int or not 1 <= start <= 6:
        raise ValueError('Origen debe ser 1..6')
    if type(distance) is not int or not 1 <= distance <= 6:
        raise ValueError('Distancia debe ser 1..6')
    if early_exit_at is not None and (type(early_exit_at) is not int or not 1 <= early_exit_at <= 6):
        raise ValueError('Destino de bifurcación debe ser 1..6')
    pos, laps, visited = start, 0, []
    for step in range(1, distance + 1):
        if pos == 6:
            laps += 1
        pos = pos % 6 + 1
        visited.append(pos)
        if early_exit_at is not None and pos == early_exit_at:
            return CircuitRoute(start, tuple(visited), pos, laps, step, distance - step)
    return CircuitRoute(start, tuple(visited), pos, laps, distance, 0)


@dataclass(frozen=True)
class MovementCard:
    id: str
    a: int
    b: int

    def __post_init__(self) -> None:
        if not self.id or any(type(x) is not int or not 1 <= x <= 6 for x in (self.a, self.b)):
            raise ValueError('Carta A/B inválida')

    def distance(self, choice: str) -> int:
        if choice not in ('A', 'B'):
            raise ValueError('Elegir A o B; no mezclar elecciones')
        return self.a if choice == 'A' else self.b


def youth_cards(*, include_equal: bool = False) -> tuple[MovementCard, ...]:
    """30 pares ordenados A!=B; variante experimental de 36 con A==B."""
    return tuple(MovementCard(f'J-{a}-{b}', a, b)
                 for a in range(1, 7) for b in range(1, 7)
                 if include_equal or a != b)


class MovementPile:
    """Mazo sin reemplazo, barajado al iniciar. Reciclado SOLO explícito.

    Las cartas en manos siguen fuera del descarte. No presupone cuántas
    cartas tendrá Adultez ni recicla silenciosamente al agotarse.
    """
    def __init__(self, cards: Iterable[MovementCard], rng: random.Random):
        original = tuple(cards)
        if len({c.id for c in original}) != len(original):
            raise ValueError('ID de cartas duplicados')
        self._rng = rng
        self._pile = list(original)
        self._rng.shuffle(self._pile)
        self._discard: list[MovementCard] = []

    @property
    def available(self) -> int:
        return len(self._pile)

    @property
    def discarded(self) -> int:
        return len(self._discard)

    def draw(self, count: int = 1) -> tuple[MovementCard, ...]:
        if type(count) is not int or count < 1 or count > len(self._pile):
            raise ValueError('No hay suficientes cartas para reparto sin reemplazo')
        return tuple(self._pile.pop() for _ in range(count))

    def discard(self, cards: Iterable[MovementCard]) -> None:
        self._discard.extend(cards)

    def recycle_discard(self) -> None:
        """Operación expresa; no incluye cartas aún en manos de jugadores."""
        if self._pile:
            raise ValueError('Reciclar solo después de agotar el montón de robo')
        if not self._discard:
            raise ValueError('No existen descartes para reciclar')
        self._pile, self._discard = self._discard, []
        self._rng.shuffle(self._pile)


@dataclass(frozen=True)
class AdultHand:
    cards: tuple[MovementCard, ...]

    @property
    def exhausted(self) -> bool:
        return not self.cards

    def play(self, card_id: str, choice: str) -> tuple[MovementCard, int, 'AdultHand']:
        for i, card in enumerate(self.cards):
            if card.id == card_id:
                return card, card.distance(choice), AdultHand(self.cards[:i] + self.cards[i + 1:])
        raise ValueError('La carta no pertenece a esta mano')

    def renew(self, cards: tuple[MovementCard, ...]) -> 'AdultHand':
        if not self.exhausted:
            raise ValueError('Se debe usar toda la mano antes de renovarla')
        if len(cards) not in (3, 4):
            raise ValueError('Variante experimental: mano de 3 o 4 cartas')
        if len({c.id for c in cards}) != len(cards):
            raise ValueError('La nueva mano contiene duplicados')
        return AdultHand(cards)


def play_paired_turn(active: AdultHand, companion: AdultHand, card_id: str, choice: str
                     ) -> tuple[MovementCard, int, AdultHand, AdultHand]:
    """Se gasta SOLO carta del activo; el acompañante mantiene su mano."""
    card, distance, remaining = active.play(card_id, choice)
    return card, distance, remaining, companion
