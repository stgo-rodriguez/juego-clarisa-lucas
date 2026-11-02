"""UTN, Perfil-Afinidad y Dublín con mercado físico de cartas v2.

Las dos políticas de incorporación adulta son experimentales.
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
    """16 cartas físicas por rol: mazo oculto, cima visible y cartas activas.

    Las cartas visibles quedan retenidas FUERA del montón oculto y nunca
    se roban silenciosamente. No se simulan duelos de intercambio de perfil.
    """
    def __init__(self, seed: int = 1):
        self.decks = {}
        self.active: dict[int, ProfileCard] = {}
        self.visible: dict[str,list[ProfileCard]] = {'Clarisa':[],'Lucas':[]}
        self.last_change: set[tuple[int,int]] = set()
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

    def top_visible(self,role:str)->ProfileCard | None:
        pile=self.visible[role]
        return pile[-1] if pile else None

    def change(self,eco:EconomyV2,p:PlayerState,round_no:int,*,
               take:str='hidden',discard:str='visible')->ProfileCard:
        """Cambia un Perfil, pagando 3 A+P+K+M sin consumir reservas.

        Solo permite tomar cima visible o primera tapada; abandonar
        al tope visible o al fondo tapado, una vez por turno.
        """
        if p.stage not in (Stage.JUVENTUD,Stage.ADULTEZ) or p.id not in self.active:
            raise ValueError('Cambio requiere Perfil y etapa habilitada')
        if (round_no,p.id) in self.last_change:
            raise ValueError('Máximo un cambio de Perfil por turno')
        if take not in ('hidden','visible') or discard not in ('hidden','visible'):
            raise ValueError('Opciones del mercado inválidas')
        ac=eco.accounts[p.id]
        if any(ac.free[r]<3 for r in ('A','P','K','M')):
            raise ValueError('Pago de Perfil insuficiente, no se utilizan reservas')
        deck=self.decks[p.role]
        if take=='hidden' and not deck.can_draw(1):
            raise PendingRuleError('Mazo tapado sin cartas de Perfil')
        if take=='visible' and not self.visible[p.role]:
            raise ValueError('No existe Perfil visible disponible')
        previous=self.active[p.id]
        if take=='visible':
            new=self.visible[p.role].pop()
        else:
            new,=deck.draw()
        for resource in ('A','P','K','M'):
            eco.spend(p.id,resource,3,'cambio_perfil')
        self.active[p.id]=new
        eco.set_profile(p.id,new.tier,affinity=new.affinity)
        if discard=='visible':self.visible[p.role].append(previous)
        else:deck.return_to_bottom(previous)
        self.last_change.add((round_no,p.id))
        eco.events.append({'action':'profile_changed','player':p.id,'from':previous.id,
                           'to':new.id,'take':take,'discard':discard})
        self.audit()
        return new

    def audit(self):
        active_ids=[c.id for c in self.active.values()]
        visible_ids=[c.id for pile in self.visible.values() for c in pile]
        if len(active_ids+visible_ids)!=len(set(active_ids+visible_ids)):
            raise AssertionError('Carta de Perfil duplicada entre mercado y jugadores')
        for deck in self.decks.values():deck.assert_conservation()
        for role,deck in self.decks.items():
            retained={c.id for c in self.active.values() if c.role==role}
            retained.update(c.id for c in self.visible[role])
            if len(retained)!=deck.held:
                raise AssertionError('Perfil retenido sin dueño o pila visible')
        return True


def transition_hooks(eco: EconomyV2, profiles: ProfileDecksV2) -> RuleHooks:
    """Conecta reglas aprobadas; las situaciones deben configurarse aparte."""
    hooks = eco.hooks()
    hooks.utn_eligible = lambda engine,p: (
        p.stage == Stage.INFANCIA and not p.utn_passed
        and eco.accounts[p.id].free['P'] >= 2
        and eco.accounts[p.id].free['K'] >= 1)
    hooks.utn_pass = lambda engine,p: profiles.award_utn(eco,p)
    hooks.dublin_exit = lambda engine,p: eco.enter_dublin(p)
    hooks.dublin_land = lambda engine,p: eco.land_from_dublin(p)
    return hooks