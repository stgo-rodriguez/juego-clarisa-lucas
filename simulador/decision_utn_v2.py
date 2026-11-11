"""Intención de ingreso a UTN de los agentes, sin alterar el reglamento.

El nodo UTN admite reglamentariamente el ingreso sin los requisitos:
después de la Situación A/B se comprueba 2 P + 1 K y, si falta,
en el siguiente turno se vuelve al circuito. Esta política experimental
evita que los bots elijan voluntariamente ese recorrido improductivo.
"""
from __future__ import annotations

from simulador.turnos_v2 import Stage


def choose_utn_entry(player, economy) -> bool:
    """Solo intentar la bifurcación si YA hay 2 P + 1 K libres.

    Decisión anterior al movimiento y a la Situación; los recursos no se
    pagan ni se reservan. Una Situación posterior puede quitarlos, por lo
    que el motor sigue comprobando el requisito después de la carta.
    """
    if player.stage != Stage.INFANCIA or player.utn_passed:
        return False
    free = economy.accounts[player.id].free
    return free["P"] >= 2 and free["K"] >= 1


def record_utn_intent(engine, economy, player) -> bool:
    decision = choose_utn_entry(player, economy)
    if player.stage == Stage.INFANCIA:
        free = economy.accounts[player.id].free
        engine._event(
            "utn_entry_intent",
            player=player.id,
            role=player.role,
            free_P=free["P"], free_K=free["K"],
            choose=decision,
            policy="bot_requires_2P_1K_before_moving",
        )
    return decision
