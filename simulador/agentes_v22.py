"""Políticas de jugadores adaptadas al tablero v2.2.

No se incentiva perseguir casilleros de recursos que ya no existen.
Las decisiones de cartas A/B siguen siendo independientes por jugador.
"""
from __future__ import annotations

from simulador.agentes_v2 import GameAgent
from simulador.movimiento_v2 import walk_circuit
from simulador.movimiento_v22 import adult_options_v22
from simulador.turnos_v2 import AdultChoice
from simulador.afinidad_v2 import shift, zone


class GameAgentV22(GameAgent):
    def choose_youth(self, player, situation, card):
        if self.config.policy == 'aleatorio':
            return self.rng.choice(('A', 'B'))
        target = self._target_youth(player)
        account = self.eco.accounts[player.id]
        scores = []
        for letter in ('A', 'B'):
            route = walk_circuit(player.position, card.distance(letter))
            score = 0.0
            if route.destination in target:
                score += 80
            # Universidad/Trámite mantienen exclusivamente sus acciones.
            if route.destination in (1, 4):
                score += 2.5 if not account.title else 0.15
            if route.destination in (2, 5):
                score += 2.5 if account.passport is None else 0.15
            # El cruce 6→1 sigue cobrando Perfil; no hay premios por paso.
            score += route.lap_crossings * 3.0
            payload = situation.payload or {}
            effects = payload.get(letter, {}) if isinstance(payload, dict) else {}
            score += sum(
                float(amount) * {'K': 2.5, 'P': 1.8, 'M': 1.8, 'A': 1.6}.get(res, 1)
                for res, amount in effects.items()
            )
            if player.partner_id is not None and hasattr(self.eco, 'dynamic_affinity'):
                current = self.eco.dynamic_affinity[player.id] + shift(letter)
                mate = self.eco.dynamic_affinity[player.partner_id]
                if zone(current) == zone(mate):
                    score += 8
            scores.append((score, letter))
        return max(scores, key=lambda item: (item[0], item[1] == 'A'))[1]

    def choose_adult(self, player, situation, hand):
        eligible = (player.partner_id is not None
                    and self.eco.marriage_eligible(player))
        candidates = []
        for card in hand.cards:
            for letter in ('A', 'B'):
                for route in adult_options_v22(
                    player.position, card.distance(letter),
                    marriage_eligible=eligible,
                ):
                    choice = AdultChoice(
                        card.id, letter, route.direction,
                        route.consumed - 1
                        if route.destination == 'Casamiento' else None,
                    )
                    candidates.append((route, choice))
        if not candidates:
            raise RuntimeError('No existe movimiento adulto legal')
        if self.config.policy == 'aleatorio':
            return self.rng.choice(candidates)[1]
        scored = [
            (self._adult_score(player, route), i, choice)
            for i, (route, choice) in enumerate(candidates)
        ]
        return max(scored, key=lambda item: (item[0], -item[1]))[2]
