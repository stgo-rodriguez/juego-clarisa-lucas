"""Fase 4: adaptador explícito UTN/Perfil/Dublín para RoundEngine v2.

Convención EXPERIMENTAL pendiente de aprobación: parejas en Dublín se
incorporan juntas al comienzo de la siguiente ronda global. Si un miembro
no actuó aún cuando se tomó Vuelo a Dublín, ese turno queda documentado
como espera, sin cobrar otra Situación ni gastar carta.
"""
from __future__ import annotations
from dataclasses import dataclass
import random

from simulador.turnos_v2 import CardPool, PendingRuleError, PlayerState, RoundEngine, RuleHooks, Stage
from simulador.economia_v2 import EconomyV2, PROFILE_PRODUCTIONS


@dataclass(frozen=True)
class ProfileCard:
    id: str
    role: str
    tier: int
    affinity: int


class ProfileDecksV2:
    """16 cartas físicas por rol: 4 perfiles × 4 afinidades, barajadas.

    Conserva la carta retenida fuera del mazo. No implementa todavía cambios
    de perfil, disputas ni mercado de descartes, que requieren Fase posterior.
    """
    def __init__(self, seed: int = 1):
        self.decks = {}
        self.active: dict[int, ProfileCard] = {}
        for i,role in enumerate(('Clarisa','Lucas')):
            cards = [ProfileCard(f'{role}-P{tier}-E{element}', role, tier, element)
                     for tier in range(4) for element in range(4)]
            self.decks[role] = CardPool(cards,random.Random(seed + 100*i))

    def award_utn(self, eco: EconomyV2, p: PlayerState):
        if p.id in self.active or eco.accounts[p.id].profile_production is not None:
            raise ValueError('Cada jugador solo puede recibir Perfil UTN una vez')
        deck = self.decks[p.role]
        if not deck.can_draw(1):
            raise PendingRuleError('Se agotaron las 16 cartas de Perfil de este personaje')
        card,=deck.draw()
        self.active[p.id]=card
        eco.set_profile(p.id,card.tier,affinity=card.affinity)
        eco.events.append({'action':'utn_profile_awarded', 'player':p.id,
                           'card':card.id,'tier':card.tier,'affinity':card.affinity})
        return card

    def audit(self):
        for deck in self.decks.values():deck.assert_conservation()
        return True


def transition_hooks(eco: EconomyV2, profiles: ProfileDecksV2) -> RuleHooks:
    """Conecta reglas aprobadas; no rellena efectos de Situaciones inexistentes."""
    hooks = eco.hooks()
    hooks.utn_eligible = lambda engine,p: (
        p.stage == Stage.INFANCIA and not p.utn_passed
        and eco.accounts[p.id].free['P'] >= 2
        and eco.accounts[p.id].free['K'] >= 1)
    hooks.utn_pass = lambda engine,p: profiles.award_utn(eco,p)
    hooks.dublin_exit = lambda engine,p: eco.enter_dublin(p)
    hooks.dublin_land = lambda engine,p: eco.land_from_dublin(p)
    return hooks