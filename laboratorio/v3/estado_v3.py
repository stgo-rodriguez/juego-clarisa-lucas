"""Contabilidad transaccional del simulador experimental v3.0.

Cada cambio monetario es un asiento inmutable registrado; ni las reservas
ni las inversiones son consumos. Todas las cifras deben venir del escenario.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

RECURSOS = ("A", "P", "K", "M")
BOLSAS = ("libre", "reserva_pareja", "reserva_casa", "invertido")


class EstadoInvalido(ValueError):
    pass


@dataclass
class Personaje:
    id: str
    rol: str
    falso: bool = False
    secreto_revelado: bool = False
    afinidad_recurso: str = "A"
    afinidad_cantidad: int = 0
    afinidad_revelada: bool = False
    etapa: str = "Infancia"
    posicion: object = 1
    zona: int = 0
    pareja: Optional[str] = None
    titulo: bool = False
    pasaporte: bool = False
    perfil: str = ""
    examen_aprobado: bool = False
    utm_regreso: bool = False
    examenes: int = 0
    mano: list = field(default_factory=list)
    recursos: dict = field(default_factory=lambda: {
        r: {b: 0 for b in BOLSAS} for r in RECURSOS
    })

    def libre(self, recurso):
        return self.recursos[recurso]["libre"]


class LibroMayor:
    def __init__(self, personas: dict[str, Personaje]):
        self.personas = personas
        self.eventos = []
        self.total_emitido = {r: 0 for r in RECURSOS}
        self.total_consumido = {r: 0 for r in RECURSOS}

    def asiento(self, ronda: int, causa: str, recurso: str, cantidad: int,
                origen=None, destino=None, parametro=None, extra=None):
        if recurso not in RECURSOS or type(cantidad) is not int or cantidad < 0:
            raise EstadoInvalido("Cantidad o recurso inválido")
        if origen is None and destino is None:
            raise EstadoInvalido("El asiento debe tener un extremo")
        for extremo in (origen, destino):
            if extremo is not None:
                actor, bolsa = extremo
                if actor not in self.personas or bolsa not in BOLSAS:
                    raise EstadoInvalido("Cuenta inexistente")
        if origen is not None:
            actor, bolsa = origen
            if self.personas[actor].recursos[recurso][bolsa] < cantidad:
                raise EstadoInvalido(
                    f"Saldo insuficiente {actor}/{recurso}/{bolsa}"
                )
            self.personas[actor].recursos[recurso][bolsa] -= cantidad
        if destino is not None:
            actor, bolsa = destino
            self.personas[actor].recursos[recurso][bolsa] += cantidad
        if origen is None:
            self.total_emitido[recurso] += cantidad
        elif destino is None:
            self.total_consumido[recurso] += cantidad
        event = {
            "tipo": "transaccion",
            "ronda": ronda, "causa": causa, "parametro": parametro,
            "recurso": recurso, "cantidad": cantidad,
            "origen": list(origen) if origen else None,
            "destino": list(destino) if destino else None,
        }
        if extra:
            event.update(extra)
        self.eventos.append(event)
        return event

    def emitir(self, ronda, causa, jugador, recurso, cantidad, parametro):
        return self.asiento(ronda, causa, recurso, cantidad,
                            destino=(jugador, "libre"), parametro=parametro)

    def consumir(self, ronda, causa, jugador, recurso, cantidad, parametro):
        return self.asiento(ronda, causa, recurso, cantidad,
                            origen=(jugador, "libre"), parametro=parametro)

    def reservar(self, ronda, jugador, recurso, cantidad, bolsa, parametro):
        if bolsa not in ("reserva_pareja", "reserva_casa", "invertido"):
            raise EstadoInvalido("Bolsa de reserva/inversión inválida")
        return self.asiento(
            ronda, "inmovilizacion", recurso, cantidad,
            origen=(jugador, "libre"), destino=(jugador, bolsa),
            parametro=parametro
        )

    def liberar(self, ronda, jugador, recurso, bolsa, parametro):
        cantidad = self.personas[jugador].recursos[recurso][bolsa]
        if cantidad:
            self.asiento(ronda, "liberacion", recurso, cantidad,
                         origen=(jugador, bolsa), destino=(jugador, "libre"),
                         parametro=parametro)
        return cantidad

    def transferir(self, ronda, causa, de, a, recurso, cantidad, parametro):
        return self.asiento(
            ronda, causa, recurso, cantidad,
            origen=(de, "libre"), destino=(a, "libre"), parametro=parametro
        )

    def perder(self, ronda, jugador, recurso, nominal, parametro):
        if type(nominal) is not int or nominal < 0:
            raise EstadoInvalido("Pérdida nominal inválida")
        bolsas = ("libre", "reserva_pareja", "reserva_casa") if recurso == "A" else (
            ("libre", "reserva_casa") if recurso == "P" else ("libre",)
        )
        remaining = nominal
        for bolsa in bolsas:
            take = min(remaining, self.personas[jugador].recursos[recurso][bolsa])
            if take:
                self.asiento(
                    ronda, "perdida_efectiva", recurso, take,
                    origen=(jugador, bolsa), parametro=parametro,
                    extra={"perdida_nominal": nominal}
                )
                remaining -= take
        return nominal - remaining

    def comprobar(self):
        for jugador, p in self.personas.items():
            for recurso, bolsas in p.recursos.items():
                for bolsa, cantidad in bolsas.items():
                    if type(cantidad) is not int or cantidad < 0:
                        raise EstadoInvalido(
                            f"Saldo negativo o no entero: {jugador} {recurso} {bolsa}"
                        )
        for r in RECURSOS:
            existing = sum(
                sum(p.recursos[r].values()) for p in self.personas.values()
            )
            if existing != self.total_emitido[r] - self.total_consumido[r]:
                raise EstadoInvalido(
                    f"Mayor no conciliado: {r} existente={existing} "
                    f"emitido={self.total_emitido[r]} consumido={self.total_consumido[r]}"
                )
        return True
