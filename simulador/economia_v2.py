"""Reglas económicas v2.0: adaptador verificable para RoundEngine.

Ningún efecto de las Situaciones, magnitud adulta ni transición a UTN
se presupone. Los escenarios neutrales son exclusivamente EXPERIMENTALES.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import random
from typing import Mapping

from simulador.movimiento_v2 import Coord
from simulador.turnos_v2 import PendingRuleError, PlayerState, RoundEngine, RuleHooks, Stage, SituationCard, TurnOutcome

RESOURCES = ('A', 'P', 'K', 'M')
PROJECT_COSTS = {
    'Titulo': (('K', 1), ('K', 2), ('K', 3)),
    'Italia': (('P', 2), ('P', 3), ('M', 2)),
    'Polonia': (('P', 2), ('P', 3), ('M', 2)),
}
PASSPORT_KIND = {'Clarisa': 'Italia', 'Lucas': 'Polonia'}
PROFILE_PRODUCTIONS = {
    'Clarisa': ((2,1,2,1), (2,1,1,2), (1,1,1,3), (1,0,1,4)),
    'Lucas': ((2,2,1,1), (2,1,1,2), (1,1,1,3), (1,0,1,4)),
}


def _zero() -> dict[str,int]:
    return {r:0 for r in RESOURCES}


@dataclass
class Account:
    free: dict[str,int] = field(default_factory=_zero)
    pair_a: int = 0
    house_a: int = 0
    house_p: int = 0
    title: bool = False
    passport: str | None = None
    profile_production: tuple[int,int,int,int] | None = None
    affinity: int | None = None


@dataclass
class Project:
    id: str
    kind: str
    receipts: list[str] = field(default_factory=list)
    winner: int | None = None
    complete: bool = False


@dataclass
class Receipt:
    id: str
    project_id: str
    subhito: int
    owner: int
    resource: str
    amount: int


@dataclass(frozen=True)
class EconomyScenario:
    adult_square_amounts: Mapping[str,int] | None = None
    neutral_situations: bool = False
    # Para pruebas: no atribuye efectos económicos a las Situaciones.

    def __post_init__(self):
        if self.adult_square_amounts is not None:
            if set(self.adult_square_amounts) != set(RESOURCES):
                raise ValueError('Debés indicar los cuatro montos A/P/K/M de Adultez')
            if any(type(x) is not int or x < 0 for x in self.adult_square_amounts.values()):
                raise ValueError('Montos de casilleros adultos deben ser enteros >= 0')


class EconomyV2:
    def __init__(self, players: list[PlayerState], *, scenario: EconomyScenario | None = None,
                 rng: random.Random | None = None):
        self.accounts = {p.id: Account() for p in players}
        self.scenario = scenario or EconomyScenario()
        self.rng = rng or random.Random(17)
        self.issued = _zero()
        self.burned = _zero()
        self.projects: dict[str,Project] = {}
        self.receipts: dict[str,Receipt] = {}
        self.invested: dict[str,int] = _zero()
        self.house_owner: tuple[int,int] | None = None
        self.married: tuple[int,int] | None = None
        self.events: list[dict] = []
        self._funded_turn: set[tuple[int,int,str]] = set()
        self._players = {p.id:p for p in players}

    def _account(self, pid: int) -> Account:
        return self.accounts[pid]

    @staticmethod
    def _check_resource(resource: str, n: int):
        if resource not in RESOURCES or type(n) is not int or n < 0:
            raise ValueError('Recurso o importe inválido')

    def issue(self, pid: int, resource: str, n: int, source: str):
        self._check_resource(resource,n)
        self._account(pid).free[resource] += n
        self.issued[resource] += n
        self.events.append(dict(action='issue',player=pid,resource=resource,amount=n,source=source))
        self.audit()

    def spend(self, pid: int, resource: str, n: int, source: str):
        self._check_resource(resource,n)
        a = self._account(pid)
        if a.free[resource] < n:
            raise ValueError('Saldo libre insuficiente')
        a.free[resource] -= n
        self.burned[resource] += n
        self.events.append(dict(action='spend',player=pid,resource=resource,amount=n,source=source))
        self.audit()

    def transfer(self, from_pid: int, to_pid: int, resource: str, n: int):
        self._check_resource(resource,n)
        if from_pid == to_pid:
            raise ValueError('Transferencia requiere dos jugadores')
        src, dst = self._account(from_pid), self._account(to_pid)
        if src.free[resource] < n:
            raise ValueError('Transferencia no puede utilizar reservas')
        src.free[resource] -= n
        dst.free[resource] += n
        self.events.append(dict(action='transfer',source=from_pid,dest=to_pid,resource=resource,amount=n))
        self.audit()

    def audit(self):
        for a in self.accounts.values():
            if any(type(v) is not int or v < 0 for v in a.free.values()):
                raise AssertionError('Saldos libres inválidos')
            if min(a.pair_a,a.house_a,a.house_p) < 0:
                raise AssertionError('Reserva negativa')
        for r in RESOURCES:
            free=sum(a.free[r] for a in self.accounts.values())
            held=sum((a.pair_a+a.house_a if r=='A' else a.house_p if r=='P' else 0)
                     for a in self.accounts.values())
            expected=self.issued[r]-self.burned[r]
            if free+held+self.invested[r] != expected:
                raise AssertionError(f'Balance contable {r}: {free}+{held}+{self.invested[r]} != {expected}')
        return True

    def _pool_to_quota(self, x: int, y: int, quotas: Mapping[str,int]):
        """Redistribución legal de saldos libres, nunca reservas."""
        ax, ay = self._account(x), self._account(y)
        for r,n in quotas.items():
            self._check_resource(r,n)
            if ax.free[r]+ay.free[r] < 2*n:
                return False
        for r,n in quotas.items():
            if ax.free[r] < n:self.transfer(y,x,r,n-ax.free[r])
            if ay.free[r] < n:self.transfer(x,y,r,n-ay.free[r])
        return True

    def form_pair(self, a: PlayerState, b: PlayerState):
        if a.id==b.id or a.role == b.role or a.stage != b.stage or a.position != b.position:
            raise ValueError('Pareja requiere encuentro exacto Clarisa+Lucas')
        if a.partner_id is not None or b.partner_id is not None:
            raise PendingRuleError('Reemplazo de pareja requiere protocolo de ruptura')
        if a.stage not in (Stage.JUVENTUD,Stage.ADULTEZ):
            raise ValueError('Pareja no disponible en esta etapa')
        if not self._pool_to_quota(a.id,b.id,{'A':5}):return False
        for p in (a,b):
            ac=self._account(p.id)
            ac.free['A']-=5
            ac.pair_a+=5
        a.partner_id,b.partner_id=b.id,a.id
        self.audit()
        self.events.append(dict(action='pair',players=sorted([a.id,b.id])))
        return True

    def _pair(self, p: PlayerState) -> tuple[PlayerState, PlayerState]:
        if p.partner_id is None:raise ValueError('Requiere pareja vigente')
        mate=self._players[p.partner_id]
        if mate.partner_id!=p.id or mate.position != p.position or mate.stage!=p.stage:
            raise ValueError('Pareja no comparte estado')
        return p,mate

    def set_profile(self, pid: int, tier: int, *, affinity: int | None = None):
        p=self._players[pid]
        if type(tier) is not int or not 0 <= tier <= 3:
            raise ValueError('Nivel de Perfil inválido')
        if affinity is not None and (type(affinity) is not int or not 0 <= affinity <= 3):
            raise ValueError('Afinidad inválida')
        self.accounts[pid].profile_production=PROFILE_PRODUCTIONS[p.role][tier]
        self.accounts[pid].affinity=affinity

    def profile(self, pid: int, reason: str):
        production=self._account(pid).profile_production
        if production is None:
            raise PendingRuleError('Jugador sin Perfil asignado (UTN/mercado pendientes)')
        for r,n in zip(RESOURCES,production):
            if n:self.issue(pid,r,n,reason)

    def on_step(self, engine: RoundEngine, p: PlayerState, pos: int, last: bool):
        if p.stage == Stage.INFANCIA:
            if pos == 2:self.issue(p.id,'A',3,'infancia_paso_2')
            elif pos == 5:self.issue(p.id,'P',2,'infancia_paso_5')
        elif p.stage == Stage.JUVENTUD:
            if pos in (1,4):self.issue(p.id,'K',2 if last else 1,'juventud_universidad')
            elif pos in (2,5):self.issue(p.id,'P',2 if last else 1,'juventud_tramite')

    def on_destination(self, engine: RoundEngine, p: PlayerState, target: str):
        if p.stage==Stage.ADULTEZ and target in RESOURCES:
            if self.scenario.adult_square_amounts is None:
                raise PendingRuleError('Cantidad de recursos 5x5 no definida')
            amount=self.scenario.adult_square_amounts[target]
            if amount:self.issue(p.id,target,amount,'adultez_casillero')
        if target=='Casamiento' and p.id==min(p.id,p.partner_id or p.id):
            self.marry(p)

    def on_situation(self, engine: RoundEngine, p: PlayerState, card: SituationCard, choice: str | None):
        if not self.scenario.neutral_situations:
            raise PendingRuleError('Faltan efectos aprobados de seis mazos: no simular como si fueran neutros')
        self.events.append(dict(action='situation_neutral_EXPERIMENTAL',card=card.id,player=p.id,choice=choice))

    def hooks(self) -> RuleHooks:
        return RuleHooks(apply_situation=self.on_situation,
                         on_step=self.on_step,
                         on_profile=lambda e,p,cause:self.profile(p.id,cause),
                         on_destination=self.on_destination,
                         after_turn=lambda e,p,out:self.audit(),
                         marriage_eligible=lambda e,p:self.marriage_eligible(p))

    def new_project(self, project_id: str, kind: str):
        if not project_id or project_id in self.projects or kind not in PROJECT_COSTS:
            raise ValueError('Proyecto inválido o duplicado')
        self.projects[project_id]=Project(project_id,kind)

    def invest(self, p: PlayerState, project_id: str, round_no: int, turn_no: int):
        project=self.projects[project_id]
        if project.complete or len(project.receipts)>=3 or project.winner is not None:
            raise ValueError('Proyecto no admite nuevas inversiones')
        if (p.id,turn_no,project_id) in self._funded_turn:
            raise ValueError('Máximo un subhito por proyecto y turno')
        r,n=PROJECT_COSTS[project.kind][len(project.receipts)]
        if project.kind in ('Italia','Polonia') and len(project.receipts)<2:
            if PASSPORT_KIND[p.role] != project.kind:
                raise ValueError('Personalidad solo de personaje elegible para su Pasaporte')
        ac=self._account(p.id)
        if ac.free[r]<n: return None
        ac.free[r]-=n
        self.invested[r]+=n
        rid=f'{project_id}-S{len(project.receipts)+1}'
        self.receipts[rid]=Receipt(rid,project_id,len(project.receipts)+1,p.id,r,n)
        project.receipts.append(rid)
        project.complete=len(project.receipts)==3
        self._funded_turn.add((p.id,turn_no,project_id))
        self.events.append(dict(action='invest',player=p.id,project=project_id,receipt=rid))
        self.audit()
        return rid

    def transfer_receipt(self, receipt_id: str, source: int, target: int):
        rec=self.receipts[receipt_id]
        if rec.owner!=source or source==target or target not in self.accounts:
            raise ValueError('Transferencia de comprobante inválida')
        rec.owner=target
        self.events.append(dict(action='receipt_transfer',receipt=receipt_id,source=source,dest=target))

    def adjudicate(self, p: PlayerState, project_id: str, payment: int, *, die: int | None = None):
        project=self.projects[project_id]
        if not project.complete or project.winner is not None or not any(
            self.receipts[rid].owner==p.id for rid in project.receipts):
            raise ValueError('Sin derecho vigente de adjudicación')
        if p.stage!=Stage.JUVENTUD or p.position not in ((1,4) if project.kind=='Titulo' else (2,5)):
            raise ValueError('Adjudicación requiere caída exacta en objetivo')
        ac=self._account(p.id)
        if project.kind=='Titulo' and ac.title:
            raise ValueError('Ya posee Título')
        if project.kind!='Titulo' and (ac.passport is not None or project.kind!=PASSPORT_KIND[p.role]):
            raise ValueError('Pasaporte incompatible o ya adquirido')
        if type(payment) is not int or not 1<=payment<=6:
            raise ValueError('Pago de adjudicación debe ser 1..6')
        r='K' if project.kind=='Titulo' else 'P'
        if die is not None and (type(die) is not int or not 1<=die<=6):
            raise ValueError('Dado inválido')
        if self._account(p.id).free[r] < payment:
            raise ValueError('Sin recursos para adjudicar')
        self.spend(p.id,r,payment,'intento_adjudicacion')
        actual_die = die if die is not None else self.rng.randint(1,6)
        if type(actual_die) is not int or not 1<=actual_die<=6:
            raise ValueError('Dado inválido')
        won=actual_die >= 7-payment
        if won:
            project.winner=p.id
            if project.kind=='Titulo':ac.title=True
            else:ac.passport=project.kind
            for rid in project.receipts:
                rec=self.receipts[rid]
                self.invested[rec.resource]-=rec.amount
                self.burned[rec.resource]+=rec.amount
        self.events.append(dict(action='adjudicate',player=p.id,project=project_id,
                                won=won,die=actual_die,payment=payment))
        self.audit()
        return won

    def enter_dublin(self, p: PlayerState):
        a,b=self._pair(p)
        if p.stage!=Stage.JUVENTUD or p.position not in (2,5):return False
        for q in (a,b):
            ac=self._account(q.id)
            if not (ac.title and ac.passport==PASSPORT_KIND[q.role] and ac.pair_a>=5):
                return False
        if not self._pool_to_quota(a.id,b.id,{'K':5,'M':5}):return False
        for q in (a,b):q.stage=Stage.DUBLIN;q.position=Stage.DUBLIN.value
        self.events.append(dict(action='enter_dublin',players=(a.id,b.id)))
        return True

    def land_from_dublin(self, p: PlayerState):
        a,b=self._pair(p)
        if p.stage!=Stage.DUBLIN:raise ValueError('La pareja no está en Dublín')
        for q in (a,b):
            if self._account(q.id).profile_production is None:
                raise PendingRuleError('No se puede cobrar perfil no asignado')
        for q in (a,b):q.stage=Stage.ADULTEZ;q.position=Coord(5,3)
        for q in (a,b):self.profile(q.id,'colocacion_inicial_dublin')
        self.events.append(dict(action='land_dublin',players=(a.id,b.id),position=(5,3)))
        return True

    def buy_house(self, p: PlayerState, *, dice: list[tuple[int,int]] | None = None,
                  max_attempts: int = 1):
        a,b=self._pair(p)
        if p.stage!=Stage.ADULTEZ or p.position!=Coord(3,3):raise ValueError('Casa solo en (3,3)')
        owners=tuple(sorted((a.id,b.id)))
        if owners==self.house_owner:return False
        if not self._pool_to_quota(a.id,b.id,{'A':8,'P':5}):return False
        if self.house_owner is not None and max_attempts!=1:
            raise ValueError('Reintentos escalados solo contra banca')
        if type(max_attempts) is not int or max_attempts<1:
            raise ValueError('Cantidad de intentos inválida')
        for attempt in range(max_attempts):
            price=15+(5*attempt if self.house_owner is None else 0)
            if not self._pool_to_quota(a.id,b.id,{'M':price}):return False
            if dice is not None:
                if attempt>=len(dice):raise ValueError('Faltan dados para la prueba')
                buy_roll,sell_roll=dice[attempt]
                if type(buy_roll) is not int or type(sell_roll) is not int or not 2<=buy_roll<=12 or not 2<=sell_roll<=12:
                    raise ValueError('Los valores 2D6 deben estar entre 2 y 12')
            else:
                buy_roll=sum(self.rng.randint(1,6) for _ in range(2))
                sell_roll=sum(self.rng.randint(1,6) for _ in range(2))
            self.events.append(dict(action='house_attempt',price_per_player=price,won=buy_roll>sell_roll))
            if buy_roll<=sell_roll:continue
            old=self.house_owner
            if old is not None:
                # Liberar las reservas antiguas, precio transferido sin creación de dinero.
                for oid in old:
                    oa=self._account(oid)
                    oa.free['A']+=oa.house_a;oa.house_a=0
                    oa.free['P']+=oa.house_p;oa.house_p=0
                for source,receiver in zip((a.id,b.id),old):
                    self.transfer(source,receiver,'M',price)
            else:
                for q in (a,b):self.spend(q.id,'M',price,'casa_banca')
            for q in (a,b):
                ac=self._account(q.id)
                ac.free['A']-=8;ac.house_a=8
                ac.free['P']-=5;ac.house_p=5
            self.house_owner=owners
            self.events.append(dict(action='house_bought',owners=owners,prior=old))
            self.audit()
            return True
        return False

    def marriage_eligible(self, p: PlayerState) -> bool:
        if p.partner_id is None or p.stage!=Stage.ADULTEZ:return False
        a,b=self._pair(p)
        if self.house_owner!=tuple(sorted((a.id,b.id))):return False
        for q in (a,b):
            ac=self._account(q.id)
            if not (ac.title and ac.passport==PASSPORT_KIND[q.role] and
                    ac.pair_a>=5 and ac.house_a>=8 and ac.house_p>=5):return False
        if self._account(a.id).affinity is None or self._account(a.id).affinity!=self._account(b.id).affinity:
            return False
        return all(sum(self._account(q.id).free[r] for q in (a,b))>=2*n
                   for r,n in {'A':12,'P':10,'M':5}.items())

    def marry(self, p: PlayerState):
        if self.married is not None: return False
        # La entrada al nodo debe haber sido autorizada ANTES por marriage_eligible.
        a,b=self._pair(p)
        if p.stage!=Stage.CASAMIENTO or p.position!=Stage.CASAMIENTO.value:
            raise ValueError('Casamiento requiere entrada al nodo exterior')
        if self.house_owner!=tuple(sorted((a.id,b.id))):raise ValueError('Sin Casa')
        for q in (a,b):
            ac=self._account(q.id)
            if not (ac.title and ac.passport==PASSPORT_KIND[q.role] and
                    ac.pair_a>=5 and ac.house_a>=8 and ac.house_p>=5):
                raise ValueError('Requisitos individuales incompletos')
        if self._account(a.id).affinity is None or self._account(a.id).affinity!=self._account(b.id).affinity:
            raise ValueError('Afinidad incompatible')
        if not self._pool_to_quota(a.id,b.id,{'A':12,'P':10,'M':5}):
            raise ValueError('No alcanzan recursos libres para Casamiento')
        for q in (a,b):
            for r,n in {'A':12,'P':10,'M':5}.items():
                self.spend(q.id,r,n,'casamiento')
        self.married=tuple(sorted((a.id,b.id)))
        self.events.append(dict(action='married',players=self.married))
        self.audit()
        return True