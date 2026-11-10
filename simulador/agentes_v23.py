"""Agentes adultos v2.3: la Casa se disputa donde está la pareja propietaria."""
from __future__ import annotations

from simulador.agentes_v22 import GameAgentV22
from simulador.experimento_politicas_v22 import AgentRosterV22
from simulador.movimiento_v2 import Coord
from simulador.turnos_v2 import Stage


class GameAgentV23(GameAgentV22):
    def _adult_score(self, player, route):
        owners = self.eco.house_owner
        own_pair = (tuple(sorted((player.id, player.partner_id)))
                    if player.partner_id is not None else None)
        if owners is None or owners == own_pair or route.destination == "Casamiento":
            return super()._adult_score(player, route)

        # La disputa NO se busca en CASA; se busca donde terminan los dueños.
        owner = self.eco._players[owners[0]]
        if owner.stage != Stage.ADULTEZ:
            return super()._adult_score(player, route)
        target = owner.position
        me = self.eco.accounts[player.id]
        mate = self.eco.accounts[player.partner_id]
        affordable = (
            me.free["A"] + mate.free["A"] >= 16 and
            me.free["P"] + mate.free["P"] >= 10 and
            me.free["M"] + mate.free["M"] >= 30
        )
        if route.destination == target and affordable:
            return 1200.0
        if not isinstance(route.destination, Coord):
            return 0.0
        distance = abs(route.destination.row - target.row) + abs(route.destination.col - target.col)
        # Sin fondos no se persigue al propietario a cualquier precio;
        # el Perfil se mantiene como fuente económica.
        if not affordable:
            return 11.0 if route.activation == "Perfil" else 0.0
        return 2.0 - 0.4 * distance + (11.0 if route.activation == "Perfil" else 0.0)

    def after_turn(self, engine, player, outcome):
        if player.stage != Stage.ADULTEZ:
            return super().after_turn(engine, player, outcome)
        if engine is not self.engine:
            raise ValueError("Motor distinto")
        # Después del movimiento: evalúa posición FINAL, no casilleros atravesados.
        if player.partner_id is not None and self.eco.house_encounter(player):
            if self.eco.buy_house(player, max_attempts=1):
                self._event(
                    player, "house", mate=player.partner_id,
                    location=(player.position.row, player.position.col),
                    mode="banca" if self.eco.events[-1]["prior"] is None else "propietarios",
                )
                if self.first_house_round is None:
                    self.first_house_round = engine.round_no
        self._change_affinity(player)
        self.eco.audit()


class AgentRosterV23(AgentRosterV22):
    def __init__(self, engine, eco, policy_by_player, seed, profiles):
        super().__init__(engine, eco, policy_by_player, seed, profiles)
        # Conservar el mismo generador por participante y semilla que v2.2.
        self.agents = {
            pid: GameAgentV23(
                engine, eco, self.agents[pid].config,
                seed * 7919 + pid * 127, profiles,
            )
            for pid in self.policy_by_player
        }
