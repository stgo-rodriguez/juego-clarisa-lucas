"""Fase 10: seis mazos de Situación bajo dos FUENTES NO APROBADAS.

I/J: 24 cartas históricas v0.1 duplicadas por rol (48+48) para prototipo.
A: 15 cartas de multiverso v0.2 por rol (30) con efectos JSON originales.
Ni las cantidades ni los efectos de ambos orígenes están aprobados para v2.0.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
import json
import math
from pathlib import Path
import random
from typing import Callable

from simulador.turnos_v2 import CardPool, PendingRuleError, PlayerState, RoundEngine, SituationCard, Stage
from simulador.economia_v2 import EconomyV2, RESOURCES
from simulador.interacciones_v2 import AuctionCard

CATALOG_PATH = Path(__file__).resolve().parent.parent / 'docs/datos_fase10/catalogo_fuentes_situaciones_v2.json'
ROLES = ('Clarisa', 'Lucas')
STAGES = (Stage.INFANCIA, Stage.JUVENTUD, Stage.ADULTEZ)


def load_catalog(path: str | Path = CATALOG_PATH) -> dict:
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if data.get('schema') != 'clarisa-lucas-situaciones-experimentales-v2.0':
        raise ValueError('Esquema de catálogo incompatible')
    historic, adult = data['historical_78'], data['adult_proposals_30']
    if (len(historic), len(adult)) != (78, 30):
        raise ValueError('Se requieren 78 cartas históricas y 30 propuestas adultas')
    if len({x['id'] for x in historic}) != 78 or len({x['id'] for x in adult}) != 30:
        raise ValueError('IDs de carta duplicados')
    for prefix, count in (('I', 24), ('J', 24), ('A', 30)):
        if sum(x['id'].startswith(prefix) for x in historic) != count:
            raise ValueError('Distribución histórica inválida')
    for role, prefix in (('Clarisa', 'AD-C-'), ('Lucas', 'AD-L-')):
        subset = [x for x in adult if x['role'] == role]
        if len(subset) != 15 or {x['id'] for x in subset} != {f'{prefix}{i:02}' for i in range(1, 16)}:
            raise ValueError('Mazo adulto incompleto')
    cards = {x['id']: x for x in adult}
    for item in adult:
        mirror = cards.get(item['mirror_id'])
        if mirror is None or mirror['mirror_id'] != item['id'] or mirror['mechanics'] != item['mechanics']:
            raise ValueError('Pares espejo sin simetría mecánica')
        if item.get('approval') != 'PROPUESTA_NO_APROBADA':
            raise ValueError('No ocultar el carácter experimental de la carta')
    for item in historic:
        if set(item['effects']) != {'A','B'}:
            raise ValueError('Cada carta histórica requiere A y B')
        if any(resource not in RESOURCES or type(delta) is not int
               for values in item['effects'].values() for resource,delta in values.items()):
            raise ValueError('Efectos históricos inválidos')
    return data


def build_decks(catalog: dict, seed: int, *, recycle: bool = True):
    """Crea seis mazos SIN nombrar sus contenidos como definitivamente aprobados."""
    by_stage = {Stage.INFANCIA:[],Stage.JUVENTUD:[]}
    for historic in catalog['historical_78']:
        if historic['stage']=='Infancia':by_stage[Stage.INFANCIA].append(historic)
        if historic['stage']=='Juventud':by_stage[Stage.JUVENTUD].append(historic)
    adult=catalog['adult_proposals_30']
    result={}
    for k,(stage,role) in enumerate((s,r) for s in STAGES for r in ROLES):
        if stage==Stage.ADULTEZ:
            cards=[SituationCard(x['id'],stage,role,{'origin':'adult_proposal',**x})
                   for x in adult if x['role']==role]
        else:
            prefix='C' if role=='Clarisa' else 'L'
            cards=[SituationCard(f'{stage.value[0]}-{prefix}-{x["id"]}',stage,role,
                                 {'origin':'historical_copy','source_id':x['id'],
                                  'effects':x['effects'],'title':x['title']})
                   for x in by_stage[stage]]
        expected=15 if stage==Stage.ADULTEZ else 24
        if len(cards)!=expected:raise ValueError('Faltan cartas en el mazo experimental')
        result[(stage,role)]=CardPool(cards,random.Random(seed + 17*k),recycle=recycle)
    return result


@dataclass(frozen=True)
class BalanceVariant:
    """Solo para simulaciones; nunca altera los JSON originales de las cartas."""
    early_gain: float = 1.0  # Infancia + Juventud
    adult_gain: float = 1.0  # Adultez, incluyendo premios de subasta
    loss_multiplier: float = 1.0  # Pérdidas explícitas, no costos voluntarios

    def __post_init__(self):
        for x in (self.early_gain, self.adult_gain, self.loss_multiplier):
            if type(x) not in (int, float) or not math.isfinite(x) or not 0 < x <= 3:
                raise ValueError('Factor de calibración debe estar en (0,3]')


@dataclass
class ProposedResolver:
    """Bot experimental: decisión propia de situación separada del movimiento.

    La letra juvenil SIEMPRE la proporciona la carta A/B de movimiento.
    """
    eco: EconomyV2
    policy: str = 'planificador'
    competition_controller: object | None = None
    rng: random.Random = field(default_factory=lambda:random.Random(7))
    events: list[dict] = field(default_factory=list)
    balance: BalanceVariant = field(default_factory=BalanceVariant)
    _current_stage: Stage | None = field(default=None, init=False, repr=False)

    @staticmethod
    def _scale(n: int, factor: float) -> int:
        """Redondeo decimal fijo; sin dados adicionales ni cambios al RNG del bot."""
        return int(n * factor + 0.5)

    def _gain_factor(self) -> float:
        return self.balance.adult_gain if self._current_stage == Stage.ADULTEZ else self.balance.early_gain

    def _scaled_gains(self, values: dict | None) -> dict:
        return {r:self._scale(n,self._gain_factor()) for r,n in (values or {}).items()}

    def _scaled_losses(self, values: dict | None) -> dict:
        return {r:self._scale(n,self.balance.loss_multiplier) for r,n in (values or {}).items()}

    def __post_init__(self):
        if self.policy not in ('planificador','aleatorio'):
            raise ValueError('Política de bot desconocida')

    def _weight(self, pid: int, resource: str) -> float:
        free=self.eco.accounts[pid].free[resource]
        minimum={'A':15,'P':12,'K':8,'M':12}[resource]
        return 1.8 if free<minimum else .7

    def _score(self,pid:int,gain:dict|None=None,cost:dict|None=None) -> float:
        return sum(n*self._weight(pid,r) for r,n in (gain or {}).items())-sum(
            n*self._weight(pid,r) for r,n in (cost or {}).items())

    def _can_pay(self, pid: int, cost: dict | None) -> bool:
        return all(self.eco.accounts[pid].free[r]>=amount for r,amount in (cost or {}).items())

    def _apply(self,pid:int, gains:dict|None=None, costs:dict|None=None,
               losses:dict|None=None, *, source:str='propuesta_situacion'):
        if not self._can_pay(pid,costs):raise ValueError('Opción no financiable')
        for r, n in (costs or {}).items():
            if n:self.eco.spend(pid,r,n,source+'_costo')
        for r, n in self._scaled_losses(losses).items():
            amount=min(n,self.eco.accounts[pid].free[r])
            if amount:self.eco.spend(pid,r,amount,source+'_perdida_libre')
        for r, n in self._scaled_gains(gains).items():
            if n:self.eco.issue(pid,r,n,source+'_premio')

    def _pick(self,choices:list[tuple[int,dict,dict]], pid:int)->int:
        eligible=[(idx,gain,cost) for idx,gain,cost in choices if self._can_pay(pid,cost)]
        if not eligible:raise PendingRuleError('Carta sin opciones financiables ni alternativa')
        if self.policy=='aleatorio':return self.rng.choice(eligible)[0]
        return max(eligible,key=lambda it:(self._score(pid,self._scaled_gains(it[1]),it[2]),-it[0]))[0]

    def _targets(self,engine:RoundEngine,p:PlayerState,mode:str)->list[PlayerState]:
        if mode not in ('same_role_any_stage','same_role_youth_or_adult'):
            raise PendingRuleError('Selector social de versiones desconocido')
        return [engine.players[i] for i in engine.turn_order
                if i not in (p.id,p.partner_id) and engine.players[i].role==p.role
                and (mode=='same_role_any_stage' or engine.players[i].stage in
                     (Stage.JUVENTUD,Stage.ADULTEZ))]

    def resolve(self,engine:RoundEngine,p:PlayerState,card:SituationCard,letter:str|None):
        self._current_stage=card.stage
        payload=card.payload
        origin=payload.get('origin')
        result=''
        if origin=='historical_copy':
            if p.stage==Stage.JUVENTUD:
                if letter not in ('A','B'):raise ValueError('La Situación juvenil requiere la misma letra A/B del movimiento')
                choice=letter
            elif p.stage==Stage.INFANCIA:
                possible=[(i,payload['effects'][s],{}) for i,s in enumerate(('A','B'))]
                choice=('A','B')[self._pick(possible,p.id)]
            else:raise ValueError('Carta histórica en etapa incompatible')
            delta=payload['effects'][choice]
            self._apply(p.id,{r:n for r,n in delta.items() if n>0},
                        losses={r:-n for r,n in delta.items() if n<0})
            result=choice
        elif origin=='adult_proposal':
            if p.stage!=Stage.ADULTEZ:raise ValueError('Propuesta adulta en etapa incompatible')
            mechanic=payload['mechanics'];kind=mechanic['type']
            if kind=='choice':
                options=mechanic['options']
                choices=[(i,opt.get('gain',{}),opt.get('cost',{})) for i,opt in enumerate(options)]
                idx=self._pick(choices,p.id);opt=options[idx]
                self._apply(p.id,opt.get('gain'),opt.get('cost'))
                result=f'choice_{idx}'
            elif kind=='choice_target':
                targets=self._targets(engine,p,mechanic['target'])
                if not targets:
                    self._apply(p.id,mechanic['no_target'].get('active_gain'))
                    result='no_target'
                else:
                    target=targets[0] if self.policy=='planificador' else self.rng.choice(targets)
                    options=mechanic['options']
                    allowed=[(i,opt.get('active_gain',{}),opt.get('active_cost',{}))
                             for i,opt in enumerate(options)]
                    idx=self._pick(allowed,p.id);opt=options[idx]
                    self._apply(p.id,opt.get('active_gain'),opt.get('active_cost'))
                    self._apply(target.id,opt.get('target_gain'),losses=opt.get('target_loss'))
                    result=f'choice_target_{idx}'
            elif kind=='coop':
                targets=self._targets(engine,p,mechanic['target'])
                valid=[q for q in targets if self._can_pay(q.id,mechanic['target_cost'])]
                if not valid or not self._can_pay(p.id,mechanic['active_cost']) or (
                     self.policy=='aleatorio' and self.rng.randrange(4)==0):
                    self._apply(p.id,mechanic['no_accept'].get('active_gain'))
                    result='coop_not_accepted'
                else:
                    target=valid[0] if self.policy=='planificador' else self.rng.choice(valid)
                    self._apply(p.id,mechanic['active_gain'],mechanic['active_cost'])
                    self._apply(target.id,mechanic['target_gain'],mechanic['target_cost'])
                    result='coop_accepted'
            elif kind=='auction':
                if self.competition_controller is None:
                    raise PendingRuleError('Subasta exige controlador con política de puja explícita')
                total=mechanic['benefit'];winner=mechanic['winner'];remain=mechanic['active']
                if not(len(total)==len(winner)==len(remain)==1):raise ValueError('Beneficio social requiere un recurso')
                resource,n=next(iter(total.items()))
                if winner.get(resource,0)+remain.get(resource,0)!=n:
                    raise ValueError('Distribución de beneficio social inconsistente')
                if 'bid' in mechanic:mode='fixed';currencies=(mechanic['bid'],)
                elif 'bid_choice' in mechanic:mode='active_choice';currencies=tuple(mechanic['bid_choice'])
                elif 'bid_any' in mechanic:mode='heterogeneous';currencies=tuple(mechanic['bid_any'])
                else:raise PendingRuleError('Modalidad de puja no documentada')
                reject=not mechanic['mandatory']
                scaled_total=self._scale(n,self.balance.adult_gain)
                scaled_winner=self._scale(scaled_total*winner[resource]/n,1.0)
                card_auction=AuctionCard(card.id,resource,scaled_total,scaled_winner,mode,currencies,
                      eligible_roles=(p.role,),allow_reject=reject,no_bid_effect='full',reject_effect='full')
                as_card=SituationCard(card.id,Stage.ADULTEZ,p.role,card_auction)
                self.competition_controller.resolve_social_situation(
                    engine,p,as_card,lambda e,q,c,letter:None,None)
                result='auction'
            else:raise PendingRuleError('Tipo de situación sin intérprete: '+str(kind))
        else:raise PendingRuleError('Origen de carta no aprobado ni documentado')
        self.events.append({'action':'proposed_situation','round':engine.round_no,
                            'player':p.id,'card':card.id,'stage':card.stage.value,
                            'family':payload.get('family','historical'),
                            'result':result,'source':origin,
                            'early_gain':self.balance.early_gain,
                            'adult_gain':self.balance.adult_gain,
                            'loss_multiplier':self.balance.loss_multiplier})
        self.eco.audit()