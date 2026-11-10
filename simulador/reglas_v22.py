"""Adaptaciones mecánicas v2.2 respecto del motor v2.1 auditado.

Únicas modificaciones de reglas v2.2:
- Juventud no genera recursos por casillero (ni por paso ni por destino);
  Universidad/Trámite conservan adjudicaciones y Dublín.
- Adultez activa solo Casa, Perfil y Casamiento; celdas ordinarias vacías.
Se conservan los demás procedimientos de v2.1.
"""
from __future__ import annotations

from simulador.reglas_v21 import EconomyV21, RoundEngineV21
from simulador.turnos_v2 import Stage, PendingRuleError
from simulador.movimiento_v22 import walk_adult_v22


class EconomyV22(EconomyV21):
    ruleset = '2.2'

    def on_step(self, engine, player, position, last):
        if player.stage == Stage.JUVENTUD:
            return  # El cruce 6→1 sí cobra Perfil, por el hook on_profile.
        return super().on_step(engine, player, position, last)

    def on_destination(self, engine, player, target):
        if player.stage == Stage.ADULTEZ and target in ('A', 'P', 'K', 'M'):
            raise AssertionError(
                'Tablero adulto v2.2 no tiene casilleros de recursos'
            )
        return super().on_destination(engine, player, target)


class RoundEngineV22(RoundEngineV21):
    ruleset = '2.2-2026-11-09'

    def play_turn(self, player_id, *, youth_choice=None, adult_choice=None,
                  childhood_die=None, utn_die=None,
                  choose_utn=False, choose_dublin=False):
        # La lógica heredada gobierna Infancia, UTN, Juventud y transiciones.
        player = self.players[player_id]
        if player.stage != Stage.ADULTEZ or (
            self.round_start_stages.get(player_id) != Stage.ADULTEZ
        ):
            return super().play_turn(
                player_id, youth_choice=youth_choice,
                adult_choice=adult_choice, childhood_die=childhood_die,
                utn_die=utn_die, choose_utn=choose_utn,
                choose_dublin=choose_dublin,
            )

        if (not self.round_no or player_id in self._played
                or self._turn_index >= len(self.turn_order)
                or player_id != self.turn_order[self._turn_index]):
            raise ValueError('Debe respetarse una activación por jugador y ronda')
        source = player.position
        situation = self._situation(player, None)
        if player.stage != Stage.ADULTEZ:
            raise PendingRuleError(
                'Cambio de etapa durante la Situación requiere política de mano'
            )
        self._renew_adult_if_empty(player)
        if adult_choice is None:
            raise ValueError('Se requiere política de movimiento adulto')
        decision = adult_choice(player, situation, player.hand)
        selected = next(
            (card for card in player.hand.cards if card.id == decision.card_id),
            None,
        )
        if selected is None:
            raise ValueError('La carta elegida no pertenece a la mano')
        distance = selected.distance(decision.letter)
        allowed = (player.partner_id is not None
                   and self.hooks.marriage_eligible(self, player))
        route = walk_adult_v22(
            player.position, distance, decision.direction,
            marriage_eligible=allowed, exit_after=decision.exit_after,
        )
        if self.adult_deck is None:
            raise PendingRuleError('Falta mazo adulto para descartes')
        _, _, player.hand = player.hand.play(selected.id, decision.letter)
        self.adult_deck.discard(selected)
        for member in self.members(player):
            member.position = route.destination
            if route.destination == Stage.CASAMIENTO.value:
                member.stage = Stage.CASAMIENTO
        target = route.activation
        if target == 'Perfil':
            for member in self.members(player):
                self.hooks.on_profile(self, member, 'caida_perfil_adultez')
        for member in self.members(player):
            self.hooks.on_destination(self, member, target)
        self._event(
            'adult_route_v22', player=player.id, visited=[
                (pos.row, pos.col) for pos in route.visited],
            destination=str(route.destination), activation=target,
            consumed=route.consumed, discarded=route.discarded,
            reflections=list(route.reflections),
        )
        return self._finish_v21(
            player, situation, source, distance, target,
            movement_card=selected.id, letter=decision.letter,
        )
