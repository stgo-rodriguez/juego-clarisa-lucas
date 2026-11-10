"""Regla v2.3 de Casa: compra inicial en (3,3), disputa en posición del dueño.

Conserva todas las reglas económicas v2.2 (incluido banco 2:1);
no modifica el motor de movimiento, ni los recursos, ni P4 pendiente.
"""
from __future__ import annotations

from simulador.experimento_politicas_v22 import EconomyBankV22, RoundEngineAuditV22
from simulador.movimiento_v2 import Coord
from simulador.turnos_v2 import PlayerState, Stage


class EconomyV23(EconomyBankV22):
    ruleset = "2.3-2026-11-10"

    def house_encounter(self, player: PlayerState) -> bool:
        """Verdadero si esta pareja puede iniciar una compra/disputa aquí.

        Si no hay propietarios: únicamente CASA (3,3). Si los hay:
        únicamente la posición ACTUAL de los dos propietarios en Adultez,
        aunque sea un casillero vacío o Perfil. Pasar por ahí no alcanza.
        """
        if player.stage != Stage.ADULTEZ or player.partner_id is None:
            return False
        mate = self._players.get(player.partner_id)
        if (mate is None or mate.partner_id != player.id or
                mate.stage != Stage.ADULTEZ or mate.position != player.position):
            return False
        buyers = tuple(sorted((player.id, mate.id)))
        if buyers == self.house_owner:
            return False
        if self.house_owner is None:
            return player.position == Coord(3, 3)
        sellers = [self._players[oid] for oid in self.house_owner]
        if any(p.stage != Stage.ADULTEZ for p in sellers):
            return False
        if sellers[0].position != sellers[1].position:
            raise AssertionError("Propietarios no comparten posición")
        return player.position == sellers[0].position

    def buy_house(self, player: PlayerState, *, dice: list[tuple[int, int]] | None = None,
                  max_attempts: int = 1):
        if player.stage != Stage.ADULTEZ:
            raise ValueError("La Casa se compra o disputa únicamente en Adultez")
        if type(max_attempts) is not int or max_attempts < 1:
            raise ValueError("Cantidad de intentos inválida")
        a, b = self._pair(player)
        if not self.house_encounter(player):
            if self.house_owner is None:
                raise ValueError("Compra inicial requiere terminar en CASA (3,3)")
            raise ValueError("Disputa requiere terminar en la posición de los propietarios")
        buyers = tuple(sorted((a.id, b.id)))
        prior = self.house_owner
        location = (player.position.row, player.position.col)
        mode = "banca" if prior is None else "propietarios"
        if prior is not None:
            self.events.append(dict(
                action="house_encounter", buyers=buyers, owners=prior,
                location=location, owner_position=location, mode=mode,
            ))
        if not self._pool_to_quota(a.id, b.id, {"A": 8, "P": 5}):
            return False
        for attempt in range(max_attempts):
            price = 15 + 5 * attempt
            if not self._pool_to_quota(a.id, b.id, {"M": price}):
                return False
            if dice is not None:
                if attempt >= len(dice):
                    raise ValueError("Faltan dados para la prueba")
                buyer_roll, seller_roll = dice[attempt]
                if (type(buyer_roll) is not int or type(seller_roll) is not int or
                        not 2 <= buyer_roll <= 12 or not 2 <= seller_roll <= 12):
                    raise ValueError("Los valores 2D6 deben estar entre 2 y 12")
            else:
                buyer_roll = sum(self.rng.randint(1, 6) for _ in range(2))
                seller_roll = sum(self.rng.randint(1, 6) for _ in range(2))
            self.events.append(dict(
                action="house_attempt", mode=mode, location=location,
                buyers=buyers, owners=prior, attempt=attempt + 1,
                price_per_player=price,
                dice_buyers=buyer_roll, dice_owners_or_bank=seller_roll,
                won=buyer_roll > seller_roll,
            ))
            if buyer_roll <= seller_roll:
                continue
            if prior is not None:
                # Revertir las reservas de Casa de los vendedores, no las de Pareja.
                for oid in prior:
                    previous = self._account(oid)
                    previous.free["A"] += previous.house_a
                    previous.free["P"] += previous.house_p
                    previous.house_a = previous.house_p = 0
                # Reparto por mitades por defecto; sin acuerdo diferente del bot.
                for buyer, seller in zip((a.id, b.id), prior):
                    self.transfer(buyer, seller, "M", price)
            else:
                for buyer in (a, b):
                    self.spend(buyer.id, "M", price, "casa_banca")
            for buyer in (a, b):
                account = self._account(buyer.id)
                account.free["A"] -= 8
                account.free["P"] -= 5
                account.house_a = 8
                account.house_p = 5
            self.house_owner = buyers
            self.events.append(dict(
                action="house_bought", owners=buyers, prior=prior,
                mode=mode, location=location, price_per_player=price,
            ))
            self.audit()
            return True
        self.audit()
        return False


class RoundEngineV23(RoundEngineAuditV22):
    """Movimiento y cartas idénticos a la rama v2.2 auditada."""
    ruleset = "2.3-2026-11-10"
