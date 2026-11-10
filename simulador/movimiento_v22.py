"""Movimiento 5×5 de v2.2: Casa y Perfil, sin casilleros productores.

La geometría, los rebotes, los accesos a Casamiento y las manos se
reutilizan de v2.1; la activación de destino usa el tablero vigente.
"""
from __future__ import annotations

from dataclasses import dataclass
from simulador.movimiento_v2 import (
    AdultRoute, Coord, CASAMIENTO, adult_options, walk_adult,
)

BOARD_V22 = (
    ('.', '.', '.', '.', '.'),
    ('.', '.', '.', '.', '.'),
    ('.', '.', 'Casa', '.', '.'),
    ('.', '.', '.', '.', '.'),
    ('.', '.', 'Perfil', '.', '.'),
)


def cell_at_v22(coord: Coord) -> str:
    return BOARD_V22[coord.row - 1][coord.col - 1]


@dataclass(frozen=True)
class AdultRouteV22(AdultRoute):
    @property
    def activation(self) -> str:
        return (CASAMIENTO if self.destination == CASAMIENTO
                else cell_at_v22(self.destination))


def _adapt(route: AdultRoute) -> AdultRouteV22:
    return AdultRouteV22(
        route.origin, route.distance, route.direction, route.visited,
        route.destination, route.consumed, route.discarded, route.reflections,
    )


def walk_adult_v22(start: Coord, distance: int, direction: str | None, *,
                   marriage_eligible: bool = False,
                   exit_after: int | None = None) -> AdultRouteV22:
    return _adapt(walk_adult(
        start, distance, direction,
        marriage_eligible=marriage_eligible, exit_after=exit_after,
    ))


def adult_options_v22(start: Coord, distance: int, *,
                      marriage_eligible: bool = False) -> tuple[AdultRouteV22, ...]:
    return tuple(_adapt(route) for route in adult_options(
        start, distance, marriage_eligible=marriage_eligible,
    ))
