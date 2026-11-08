"""Reglas de movimiento e ingreso UTN de la especificación integral 08-11-2026.

Implementación v2.1 aislada: el motor v2.0 se conserva para trazas históricas.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from simulador.economia_v2 import EconomyV2
from simulador.mazos_vigentes_v2 import CurrentResolver
from simulador.movimiento_v2 import walk_circuit, Coord
from simulador.transiciones_v2 import transition_hooks
from simulador.turnos_v2 import (
    RoundEngine, RuleHooks, Stage, TurnOutcome, PendingRuleError,
)


INFANCIA_DESTINOS = {
    1: ('A', 3), 2: ('P', 2), 3: ('A', 3),
    4: ('P', 2), 5: ('K', 1), 6: ('A', 3),
}


class EconomyV21(EconomyV2):
    """Infancia cobra exclusivamente al terminar en un casillero."""

    progressive_house_against_owner = True  # mismo escalado para banca y propietarios

    def ordinary_loss(self, player, resource, amount, interactions):
        """Pérdidas de Situación: libres → reservas A/P, sin deuda ni inversiones.

        La ruptura adulta sin posición legal de retorno no se inventa: se
        detiene ANTES de modificar saldos, mediante PendingRuleError.
        """
        if resource not in ('A', 'P', 'K', 'M') or type(amount) is not int or amount < 0:
            raise ValueError('Pérdida ordinaria inválida')
        if amount == 0:
            return
        ac = self.accounts[player.id]
        free_loss = min(amount, ac.free[resource])
        missing = amount - free_loss
        pair_loss = min(missing, ac.pair_a) if resource == 'A' else 0
        house_loss = min(missing - pair_loss, ac.house_a) if resource == 'A' else (
            min(missing, ac.house_p) if resource == 'P' else 0
        )
        if pair_loss and player.partner_id is not None:
            partner_free = self.accounts[player.partner_id].free['A']
            if player.stage == Stage.ADULTEZ and partner_free < pair_loss:
                raise PendingRuleError(
                    'Ruptura por pérdida ordinaria en Adultez: posición juvenil '
                    'de retorno pendiente de especificación'
                )
        if free_loss:
            self.spend(player.id, resource, free_loss, 'situacion_vigente_perdida')
        if pair_loss:
            ac.pair_a -= pair_loss
            self.burned['A'] += pair_loss
            self.events.append({
                'action': 'reserve_loss', 'player': player.id,
                'resource': 'A', 'amount': pair_loss,
                'reserve': 'Pareja', 'source': 'situacion_vigente_perdida',
            })
        if house_loss:
            if resource == 'A':
                ac.house_a -= house_loss
            else:
                ac.house_p -= house_loss
            self.burned[resource] += house_loss
            self.events.append({
                'action': 'reserve_loss', 'player': player.id,
                'resource': resource, 'amount': house_loss,
                'reserve': 'Casa', 'source': 'situacion_vigente_perdida',
            })
        self.audit()

        if pair_loss and player.partner_id is not None:
            missing_pair = 5 - ac.pair_a
            partner = self.accounts[player.partner_id]
            if missing_pair > 0 and partner.free['A'] >= missing_pair:
                self.transfer(player.partner_id, player.id, 'A', missing_pair)
                ac.free['A'] -= missing_pair
                ac.pair_a += missing_pair
                self.events.append({
                    'action': 'pair_reserve_repaired', 'player': player.id,
                    'from_player': player.partner_id,
                    'amount': missing_pair, 'source': 'situacion_vigente_perdida',
                })
                self.audit()
            elif missing_pair > 0:
                if interactions is None:
                    raise PendingRuleError('Ruptura de pareja requiere interacciones')
                interactions.break_pair(player.id)
        # La Casa se pierde al quedar incompletas sus reservas (sin
        # inventar ventanas especiales de reconstitución de Casa).
        if (self.house_owner is not None and player.id in self.house_owner
                and (ac.house_a < 8 or ac.house_p < 5)):
            if interactions is None:
                raise PendingRuleError('Pérdida de Casa requiere interacciones')
            interactions._vacate_house({player.id})
            self.audit()


    def on_step(self, engine, player, position, last):
        if player.stage == Stage.INFANCIA:
            return
        return super().on_step(engine, player, position, last)

    def on_destination(self, engine, player, target):
        if player.stage == Stage.INFANCIA and target == 'casillero_infancia':
            resource, amount = INFANCIA_DESTINOS[player.position]
            self.issue(player.id, resource, amount,
                       f'infancia_destino_{player.position}')
            return
        return super().on_destination(engine, player, target)


def transition_hooks_v21(eco, profiles):
    hooks = transition_hooks(eco, profiles)
    hooks.utn_eligible = lambda engine, p: (
        p.stage in (Stage.INFANCIA, Stage.UTN)
        and not p.utn_passed
        and eco.accounts[p.id].free['P'] >= 2
        and eco.accounts[p.id].free['K'] >= 1
    )
    return hooks


class RoundEngineV21(RoundEngine):
    """Una Situación por etapa+rol+ronda, asignada al inicio de la ronda."""

    ruleset = 'v21-2026-11-08'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.round_assignments = {}
        self.round_start_stages = {}

    @staticmethod
    def _situation_stage(stage):
        return Stage.INFANCIA if stage == Stage.UTN else stage

    def start_round(self):
        super().start_round()
        self.round_start_stages = {
            pid: p.stage for pid, p in self.players.items()
        }
        childhood_roles = {
            p.role for p in self.players.values()
            if p.stage in (Stage.INFANCIA, Stage.UTN)
        }
        for role in sorted(childhood_roles):
            self._ensure_shared_situation(Stage.INFANCIA, role)
        self.round_assignments = {}
        for pid, p in self.players.items():
            stage = self._situation_stage(p.stage)
            key = (stage, p.role)
            self.round_assignments[pid] = (
                key if key in self._revealed else None
            )
        self._event('situation_assignment_locked', assignments={
            str(pid): (
                {'stage': key[0].value, 'role': key[1],
                 'card': self._revealed[key].id}
                if key is not None else None
            )
            for pid, key in self.round_assignments.items()
        })

    def _situation(self, player, choice):
        key = self.round_assignments.get(player.id)
        if key is None:
            raise PendingRuleError('Sin Situación asignada al comienzo de la ronda')
        card = self._revealed.get(key)
        if card is None:
            raise PendingRuleError('Falta la carta fijada al inicio de ronda')
        self.hooks.apply_situation(self, player, card, choice)
        self._event('situation_resolved', player=player.id,
                    card=card.id, choice=choice,
                    stage=key[0].value, role=key[1])
        return card

    def _finish_v21(self, player, card, source, distance, target, *,
                    movement_card=None, letter=None):
        out = TurnOutcome(self.round_no, player.id,
                          card.id if card is not None else None,
                          letter, movement_card, distance, source,
                          player.position, target)
        self._played.add(player.id)
        self._turn_index += 1
        self._event('movement', player=player.id, card=movement_card,
                    choice=letter, distance=distance, origin=str(source),
                    destination=str(player.position), target=target)
        self.hooks.after_turn(self, player, out)
        self.validate()
        return out

    def _childhood_v21(self, player, *, childhood_die, utn_die, choose_utn):
        source = player.position
        arrived = False
        distance = None
        visited = []
        discarded = 0
        returned = False

        if player.stage == Stage.UTN and not player.utn_return_pending:
            # En UTN se resuelve Situación, luego requisitos y por último examen.
            card = self._situation(player, None)
            if not self.hooks.utn_eligible(self, player):
                player.utn_return_pending = True
                self._event('utn_requirements_missing', player=player.id,
                            next_turn='return_to_circuit')
            else:
                self._attempt_utn(player, utn_die)
            self._event('childhood_route', player=player.id, visited=[],
                        consumed=0, discarded=0, destination='UTN',
                        kind='utn_exam_or_wait', die=None)
            return self._finish_v21(player, card, source, None, 'UTN')

        if player.stage == Stage.UTN and player.utn_return_pending:
            returned = True
            player.stage = Stage.INFANCIA
            player.position = 4  # primer paso desde el nodo exterior lleva al 5
            player.utn_return_pending = False

        distance = childhood_die if childhood_die is not None else self.rng_dice.randint(1, 6)
        if type(distance) is not int or not 1 <= distance <= 6:
            raise ValueError('D6 infancia debe ser 1..6')
        route = walk_circuit(player.position, distance)
        for i, pos in enumerate(route.visited):
            for member in self.members(player):
                member.position = pos
                self.hooks.on_step(self, member, pos, i == distance - 1)
            visited.append(pos)
            # Bifurcación solo cuando se llega a 5 con un paso adicional.
            if not returned and choose_utn and pos == 5 and i + 1 < distance:
                player.stage, player.position = Stage.UTN, Stage.UTN.value
                arrived = True
                discarded = distance - i - 2
                self._event('enter_utn', player=player.id,
                            consumed=i + 2, discarded=discarded)
                break

        target = 'UTN' if arrived else 'casillero_infancia'
        if not arrived:
            for member in self.members(player):
                self.hooks.on_destination(self, member, target)
        card = self._situation(player, None)
        if arrived:
            if not self.hooks.utn_eligible(self, player):
                player.utn_return_pending = True
                self._event('utn_requirements_missing', player=player.id,
                            next_turn='return_to_circuit')
            else:
                self._event('utn_arrival_eligible', player=player.id,
                            exam='next_turn')
        self._event('childhood_route', player=player.id, visited=visited,
                    consumed=(len(visited) + 1 if arrived else len(visited)),
                    discarded=discarded, destination=target,
                    kind=('utn_return' if returned else
                          'utn_entry' if arrived else 'circuit'),
                    die=distance)
        return self._finish_v21(player, card, source, distance, target)

    def _youth_v21(self, player, *, youth_choice, choose_dublin):
        source = player.position
        if youth_choice is None:
            raise ValueError('Falta elección juvenil A/B')
        card = self._revealed[self.round_assignments[player.id]]
        movement = player.youth_movement
        if movement is None:
            raise PendingRuleError('Jugador sin Carta de Movimiento juvenil')
        letter = youth_choice(player, card, movement)
        if letter not in ('A', 'B'):
            raise ValueError('Elección A/B ilegal')
        situation = self._situation(player, letter)
        distance = movement.distance(letter)
        route = walk_circuit(player.position, distance)
        visited = []
        branched = False
        discarded = 0
        for i, pos in enumerate(route.visited):
            previous = (pos - 2) % 6 + 1
            for member in self.members(player):
                member.position = pos
                if previous == 6 and pos == 1:
                    self.hooks.on_profile(self, member, 'vuelta_juventud')
                self.hooks.on_step(self, member, pos, i == distance - 1)
            visited.append(pos)
            if (choose_dublin and pos in (2, 5)
                    and i + 1 < distance and player.partner_id is not None
                    and self.hooks.dublin_exit(self, player)):
                branched = True
                discarded = distance - i - 2
                self._event('enter_dublin_from_youth', player=player.id,
                            consumed=i + 2, discarded=discarded)
                break
        if branched:
            target = Stage.DUBLIN.value
        else:
            end = route.destination
            target = ('Universidad' if end in (1, 4)
                      else 'Tramite' if end in (2, 5) else 'Vacio')
            for member in self.members(player):
                self.hooks.on_destination(self, member, target)
        self._event('youth_route', player=player.id, visited=visited,
                    consumed=(len(visited) + 1 if branched else len(visited)),
                    discarded=discarded, destination=target, die=None)
        return self._finish_v21(
            player, situation, source, distance, target,
            movement_card=movement.id, letter=letter,
        )

    def play_turn(self, player_id, *, youth_choice=None, adult_choice=None,
                  childhood_die=None, utn_die=None,
                  choose_utn=False, choose_dublin=False):
        if (not self.round_no or player_id in self._played
                or self._turn_index >= len(self.turn_order)
                or player_id != self.turn_order[self._turn_index]):
            raise ValueError('Debe respetarse una activación por jugador y ronda')
        player = self.players[player_id]
        if utn_die is not None and (type(utn_die) is not int or not 1 <= utn_die <= 6):
            raise ValueError('D6 UTN debe ser 1..6')

        initial = self.round_start_stages[player_id]
        # Una transición ajena al turno no concede un segundo movimiento.
        if initial == Stage.DUBLIN:
            source = player.position
            if player.stage == Stage.DUBLIN:
                self._land_dublin(player)
            self._event('stage_transition_hold', player=player.id,
                        origin='Vuelo a Dublín', target='Cobrar perfil')
            return self._finish_v21(player, None, source, None, 'Cobrar perfil')

        if player.stage == Stage.DUBLIN:
            source = player.position
            card = self._situation(player, None) if self.round_assignments[player_id] else None
            self._event('stage_transition_hold', player=player.id,
                        origin=initial.value, target='Vuelo a Dublín')
            return self._finish_v21(player, card, source, None, Stage.DUBLIN.value)

        if player.stage in (Stage.INFANCIA, Stage.UTN):
            return self._childhood_v21(
                player, childhood_die=childhood_die, utn_die=utn_die,
                choose_utn=choose_utn,
            )
        if player.stage == Stage.JUVENTUD:
            if initial != Stage.JUVENTUD:
                raise PendingRuleError('Cambio a Juventud durante ronda sin reparto juvenil')
            return self._youth_v21(
                player, youth_choice=youth_choice,
                choose_dublin=choose_dublin,
            )
        if player.stage == Stage.ADULTEZ:
            if initial != Stage.ADULTEZ:
                card = (self._situation(player, None)
                        if self.round_assignments[player_id] else None)
                self._event('stage_transition_hold', player=player.id,
                            origin=initial.value, target='Adultez')
                return self._finish_v21(player, card, player.position, None, 'Adultez')
            return super().play_turn(
                player_id, youth_choice=youth_choice, adult_choice=adult_choice,
                childhood_die=childhood_die, utn_die=utn_die,
                choose_utn=choose_utn, choose_dublin=choose_dublin,
            )
        raise PendingRuleError(f'Etapa no implementada: {player.stage}')


class CurrentResolverV21(CurrentResolver):
    """Resolver de cartas con pérdidas contables sobre reservas vigentes."""

    def __init__(self, eco, interactions, policy='planificador',
                 seed=0, affinity_weight=8.0):
        super().__init__(eco, policy, seed, affinity_weight)
        self.interactions = interactions

    def _score(self, player, effects, choice):
        score = super()._score(player, effects, choice)
        account = self.eco.accounts[player.id]
        for resource, weight in (('A', 1.8), ('P', 1.8)):
            amount = max(0, -effects.get(resource, 0))
            over_free = max(0, amount - account.free[resource])
            reserved = (account.pair_a + account.house_a
                        if resource == 'A' else account.house_p)
            score -= weight * min(over_free, reserved)
            if resource == 'A' and account.pair_a:
                if over_free > 0:
                    score -= 8
            if (account.house_a or account.house_p) and over_free > 0:
                score -= 5
        return score

    def _apply(self, player, effects):
        for resource, amount in effects.items():
            if amount < 0:
                self.eco.ordinary_loss(player, resource, -amount,
                                       self.interactions)
        for resource, amount in effects.items():
            if amount > 0:
                self.eco.issue(player.id, resource, amount,
                               'situacion_vigente_premio')
