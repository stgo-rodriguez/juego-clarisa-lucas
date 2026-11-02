"""Políticas reproducibles para experimento controlado v2.x.

NO constituye IA oficial del juego: compara selección legal aleatoria
contra heurística informada por posición, recursos e hitos. No usa cartas
futuras ni información oculta. Los mazos sintéticos viven en el experimento.
"""
from __future__ import annotations
from dataclasses import dataclass
import random
from typing import Callable
from simulador.economia_v2 import EconomyV2, PASSPORT_KIND, PROJECT_COSTS
from simulador.movimiento_v2 import AdultHand, AdultRoute, Coord, MovementCard, adult_options, cell_at, walk_circuit
from simulador.turnos_v2 import AdultChoice, PlayerState, RoundEngine, SituationCard, Stage, TurnOutcome
from simulador.transiciones_v2 import ProfileDecksV2


@dataclass(frozen=True)
class AgentConfig:
    policy: str = 'planificador'  # o 'aleatorio'
    adjudication_payment: int = 6

    def __post_init__(self):
        if self.policy not in ('aleatorio', 'planificador'):
            raise ValueError('Política desconocida')
        if not 1 <= self.adjudication_payment <= 6:
            raise ValueError('Pago objetivo fuera de 1..6')


class GameAgent:
    """Agente individual, con acción opcional POST-movimiento del activo."""
    def __init__(self, engine: RoundEngine, eco: EconomyV2, config: AgentConfig,
                 seed: int, profiles: ProfileDecksV2 | None = None):
        self.engine, self.eco, self.config = engine, eco, config
        self.profiles = profiles
        self.rng = random.Random(seed)
        self.actions: list[dict] = []
        self._once: set[tuple[int,int,int,str]] = set()
        self.first_pair_round: int | None = None
        self.first_house_round: int | None = None

    def _event(self, p: PlayerState, action: str, **attrs):
        self.actions.append({'round':self.engine.round_no,'turn':p.id,'action':action,**attrs})

    def _has_ready_project(self, p: PlayerState, kind: str) -> bool:
        ac=self.eco.accounts[p.id]
        if kind=='Titulo' and ac.title:return False
        if kind!='Titulo' and ac.passport is not None:return False
        for project in self.eco.projects.values():
            if project.kind!=kind or not project.complete or project.winner is not None:
                continue
            if any(self.eco.receipts[rid].owner==p.id for rid in project.receipts):
                return True
        return False

    def _target_youth(self,p:PlayerState):
        ac=self.eco.accounts[p.id]
        if p.partner_id is not None:
            mate=self.eco.accounts[p.partner_id]
            if (ac.title and mate.title and
                ac.passport==PASSPORT_KIND[p.role] and
                mate.passport==PASSPORT_KIND[self.engine.players[p.partner_id].role] and
                all(self.eco.accounts[pid].free[r]>=5 for pid in (p.id,p.partner_id) for r in ('K','M'))):
                return {2,5}
        if self._has_ready_project(p,'Titulo'):
            return {1,4}
        if self._has_ready_project(p,PASSPORT_KIND[p.role]):
            return {2,5}
        return set()

    def choose_youth(self,p: PlayerState, situation: SituationCard,card: MovementCard)->str:
        if self.config.policy=='aleatorio':return self.rng.choice(('A','B'))
        target=self._target_youth(p)
        account=self.eco.accounts[p.id]
        scores=[]
        for letter in ('A','B'):
            route=walk_circuit(p.position,card.distance(letter))
            score=0.0
            if route.destination in target:score+=80
            if route.destination in (1,4):score += (2.5 if not account.title else .15)
            if route.destination in (2,5):score += (2.5 if account.passport is None else .15)
            score += route.lap_crossings * 3.0
            score += sum(1.3 if q in (1,4) and not account.title else
                         1.2 if q in (2,5) and account.passport is None else 0
                         for q in route.visited)
            payload=situation.payload or {}
            effect=payload.get(letter,{}) if isinstance(payload,dict) else {}
            score+=sum(float(amount)*({'K':2.5,'P':1.8,'M':1.8,'A':1.6}.get(r,1))
                       for r,amount in effect.items())
            scores.append((score,letter))
        return max(scores,key=lambda x:(x[0],x[1]=='A'))[1]

    def _adult_score(self,p:PlayerState,route:AdultRoute)->float:
        if route.destination=='Casamiento':return 100000
        eco=self.eco
        account=eco.accounts[p.id]
        cell=route.activation
        if p.partner_id is None:
            return 100 if cell=='Perfil' else 9 if cell in ('A','P','M') else 0
        mate=eco.accounts[p.partner_id]
        has_house=eco.house_owner==tuple(sorted((p.id,p.partner_id)))
        if not has_house:
            missing_a=max(0,16-(account.free['A']+mate.free['A']))
            missing_p=max(0,10-(account.free['P']+mate.free['P']))
            missing_m=max(0,30-(account.free['M']+mate.free['M']))
            affordable=missing_a==missing_p==missing_m==0
            if cell=='Casa' and affordable:return 1000
            # Mantener Casa como destino cercano, sin pasar por ella sin activarla.
            near=(abs(route.destination.row-3)+abs(route.destination.col-3))
            score=2-near*0.4 if affordable else 0
            weights={'A':2+min(5,missing_a)*1.1,'P':2+min(5,missing_p)*1.1,
                     'M':2+min(8,missing_m)*.9,'K':0.2,'Perfil':11,'Casa':-1,'.':0}
            return score+weights.get(cell,0)
        missing={'A':max(0,24-(account.free['A']+mate.free['A'])),
                 'P':max(0,20-(account.free['P']+mate.free['P'])),
                 'M':max(0,10-(account.free['M']+mate.free['M']))}
        if eco.marriage_eligible(p):
            return 50 - abs(route.destination.row-1)*5 - min(abs(route.destination.col-j) for j in (2,3,4))
        return {'A':3+missing['A']*.5,'P':3+missing['P']*.5,
                'M':3+missing['M']*.5,'Perfil':14,'K':0.3,'.':0,'Casa':0}.get(cell,0)

    def choose_adult(self,p:PlayerState,situation:SituationCard,hand:AdultHand)->AdultChoice:
        candidates=[]
        eligible=(p.partner_id is not None and self.eco.marriage_eligible(p))
        for card in hand.cards:
            for letter in ('A','B'):
                for route in adult_options(p.position,card.distance(letter),marriage_eligible=eligible):
                    candidates.append((route,AdultChoice(card.id,letter,route.direction,route.consumed-1 if route.destination=='Casamiento' else None)))
        if not candidates:raise RuntimeError('No existe movimiento adulto legal')
        if self.config.policy=='aleatorio':return self.rng.choice(candidates)[1]
        scored=[(self._adult_score(p,route),i,choice) for i,(route,choice) in enumerate(candidates)]
        return max(scored,key=lambda x:(x[0],-x[1]))[2]

    def _project_for(self,p:PlayerState,kind:str):
        # Instancias dedicadas son una simplificación experimental: todos
        # podrían legalmente aportar a cualquiera de los proyectos.
        return self.eco.projects[f'{kind}-{p.id}']

    def _adjudicate(self,p:PlayerState,kind:str):
        ac=self.eco.accounts[p.id]
        resource='K' if kind=='Titulo' else 'P'
        if (kind=='Titulo' and ac.title) or (kind!='Titulo' and ac.passport is not None):return
        candidates=[project for project in self.eco.projects.values()
            if project.kind==kind and project.complete and project.winner is None and
            any(self.eco.receipts[rid].owner==p.id for rid in project.receipts)]
        if self.config.policy=='planificador':
            candidates.sort(key=lambda x:(x.id!=f'{kind}-{p.id}',x.id))
        else:self.rng.shuffle(candidates)
        if not candidates or not ac.free[resource]:return
        payment=min(self.config.adjudication_payment,ac.free[resource]) if self.config.policy=='planificador' else self.rng.randint(1,min(6,ac.free[resource]))
        won=self.eco.adjudicate(p,candidates[0].id,payment)
        self._event(p,'adjudication',kind=kind,project=candidates[0].id,payment=payment,won=won)

    def _invest(self,p:PlayerState,kind:str):
        ac=self.eco.accounts[p.id]
        if (kind=='Titulo' and ac.title) or (kind!='Titulo' and ac.passport is not None):return
        candidates=[project for project in self.eco.projects.values()
                    if project.kind==kind and not project.complete and project.winner is None]
        if not candidates:return
        if self.config.policy=='planificador':
            candidates.sort(key=lambda x:(x.id!=f'{kind}-{p.id}',-len(x.receipts),x.id))
        else:self.rng.shuffle(candidates)
        for project in candidates:
            r,n=PROJECT_COSTS[kind][len(project.receipts)]
            if ac.free[r]<n:continue
            if self.config.policy=='planificador':
                # Evita invertir recursos imprescindibles para poder adjudicar
                # proyectos ya completos sin necesidad de bloquearlos de modo permanente.
                if r=='K' and ac.free[r]-n<1 and self._has_ready_project(p,'Titulo'):
                    continue
                if r=='P' and ac.free[r]-n<1 and self._has_ready_project(p,PASSPORT_KIND[p.role]):
                    continue
            receipt=self.eco.invest(p,project.id,self.engine.round_no,self.engine.round_no*100+p.id)
            if receipt:self._event(p,'investment',kind=kind,project=project.id,receipt=receipt)
            break

    def _change_affinity(self,p:PlayerState):
        if self.profiles is None or p.partner_id is None:return
        ac=self.eco.accounts[p.id]
        mate=self.eco.accounts[p.partner_id]
        if ac.affinity is None or mate.affinity is None or ac.affinity==mate.affinity:return
        if any(ac.free[r]<3 for r in ('A','P','K','M')):return
        if self.config.policy=='aleatorio' and self.rng.randrange(5)!=0:return
        visible=self.profiles.top_visible(p.role)
        if self.config.policy=='planificador':
            take='visible' if visible is not None and visible.affinity==mate.affinity else 'hidden'
            discard='visible'
        else:
            take=self.rng.choice(('hidden','visible')) if visible is not None else 'hidden'
            discard=self.rng.choice(('hidden','visible'))
        card=self.profiles.change(self.eco,p,self.engine.round_no,take=take,discard=discard)
        self._event(p,'profile_change',card=card.id,take=take,matching=(card.affinity==mate.affinity))

    def after_turn(self,engine:RoundEngine,p:PlayerState,out:TurnOutcome):
        if engine is not self.engine:raise ValueError('Motor distinto')
        if p.stage==Stage.JUVENTUD:
            target=out.target
            if target=='Universidad':self._adjudicate(p,'Titulo')
            if target=='Tramite':self._adjudicate(p,PASSPORT_KIND[p.role])
            # Emparejamiento: encuentro exacto; solo el activo propone.
            if p.partner_id is None:
                rivals=[q for q in engine.players.values() if q.id!=p.id and
                    q.partner_id is None and q.role!=p.role and q.stage==p.stage and
                    q.position==p.position]
                if self.config.policy=='planificador':
                    rivals.sort(key=lambda q:(self.eco.accounts[q.id].affinity!=self.eco.accounts[p.id].affinity,q.id))
                else:self.rng.shuffle(rivals)
                for q in rivals:
                    if self.eco.form_pair(p,q):
                        self._event(p,'couple',mate=q.id)
                        if self.first_pair_round is None:self.first_pair_round=engine.round_no
                        break
            self._invest(p,'Titulo')
            self._invest(p,PASSPORT_KIND[p.role])
            self._change_affinity(p)
        elif p.stage==Stage.ADULTEZ and out.target=='Casa' and p.partner_id is not None:
            if self.eco.buy_house(p,max_attempts=1):
                self._event(p,'house',mate=p.partner_id)
                if self.first_house_round is None:self.first_house_round=engine.round_no
        if p.stage==Stage.ADULTEZ:
            self._change_affinity(p)
        self.eco.audit()