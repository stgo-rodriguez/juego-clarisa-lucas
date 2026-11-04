"""Mazos I v0.3, J v0.3, A v0.4; seis barajados independientes."""
from __future__ import annotations
from collections import Counter
import json
from pathlib import Path
import random

from simulador.movimiento_v2 import MovementCard
from simulador.turnos_v2 import CardPool, SituationCard, Stage
from simulador.afinidad_v2 import shift, zone
from simulador.economia_v2 import RESOURCES

PATH=Path(__file__).resolve().parent.parent/'docs/datos_v2_nuevas_cartas/catalogo_102_v03_v04.json'
EXPECTED={(s,r):n for s,n in [('Infancia',12),('Juventud',24),('Adultez',15)] for r in ('Clarisa','Lucas')}
STAGES={'Infancia':Stage.INFANCIA,'Juventud':Stage.JUVENTUD,'Adultez':Stage.ADULTEZ}

def load_current(path=PATH)->dict:
    c=json.loads(Path(path).read_text(encoding='utf-8'))
    assert c['schema']=='clarisa-lucas-cartas-2026-11-04-v2x'
    counts=Counter((x['stage'],x['role']) for x in c['cards'])
    if counts!=Counter(EXPECTED):raise ValueError(f'Mazos incompletos: {counts}')
    if len({x['id'] for x in c['cards']})!=102:raise ValueError('IDs no únicos')
    for x in c['cards']:
        if set(x['effects'])!={'A','B'}:raise ValueError(x['id'])
        for eff in x['effects'].values():
            if any(key not in RESOURCES or type(delta) is not int or abs(delta)>50 for key,delta in eff.items()):
                raise ValueError('Economía inválida en '+x['id'])
    for stage in STAGES:
        for index in range(EXPECTED[(stage,'Clarisa')]):
            cs=[x for x in c['cards'] if x['stage']==stage and x['role']=='Clarisa']
            ls=[x for x in c['cards'] if x['stage']==stage and x['role']=='Lucas']
            if cs[index]['effects']!=ls[index]['effects']:raise ValueError('Simetría rota')
    return c

def new_decks(catalog:dict,seed:int):
    out={}
    for si,stage in enumerate(STAGES):
        for ri,role in enumerate(('Clarisa','Lucas')):
            cards=[SituationCard(x['id'],STAGES[stage],role,{'origin':'v03_v04','effects':x['effects'],
                        'title':x['title'],'source':x['source']})
                   for x in catalog['cards'] if x['role']==role and x['stage']==stage]
            # Semillas separadas, no se comparte RNG ni orden, hasta al rebarajar descartes.
            out[(STAGES[stage],role)]=CardPool(cards,random.Random(seed*150001+si*1637+ri*101+23),recycle=True)
    # Exigir un orden distinto incluso ante una colisión excepcional de la permutación.
    for stage in STAGES.values():
        c=out[(stage,'Clarisa')];l=out[(stage,'Lucas')]
        indices=lambda pool: [x.id.split('-')[-1] for x in pool._deck]
        if indices(c)==indices(l):
            l._deck[-1],l._deck[-2]=l._deck[-2],l._deck[-1]
        assert indices(c)!=indices(l)
    return out

class CurrentResolver:
    """Efectos con pérdida truncada y elección económica + compatibilidad dinámica."""
    def __init__(self,eco,policy='planificador',seed=0,affinity_weight=8.0):
        if policy not in ('planificador','aleatorio'):raise ValueError(policy)
        self.eco=eco;self.policy=policy;self.rng=random.Random(seed)
        self.affinity_weight=affinity_weight
        self.events=[]
    def _score(self,p,eff,choice):
        ac=self.eco.accounts[p.id]
        weights={'A':1.8,'P':1.8,'K':2.1,'M':2.0}
        base=sum(weights[r]*(n if n>=0 else max(n,-ac.free[r])) for r,n in eff.items())
        if p.partner_id is not None:
            positions=self.eco.dynamic_affinity
            proposed=positions[p.id]+shift(choice)
            other=positions[p.partner_id]
            if zone(proposed)==zone(other):base+=self.affinity_weight
            if zone(positions[p.id])!=zone(other):
                base+=min(4,abs(positions[p.id]-other)-abs(proposed-other))*0.9
        return base
    def _apply(self,p,eff):
        # Pierde hasta lo disponible y luego obtiene recursos, en el orden definido.
        for r,n in eff.items():
            if n<0:
                real=min(-n,self.eco.accounts[p.id].free[r])
                if real:self.eco.spend(p.id,r,real,'situacion_vigente_perdida')
        for r,n in eff.items():
            if n>0:self.eco.issue(p.id,r,n,'situacion_vigente_premio')
    def resolve(self,engine,p,card,letter):
        if card.payload.get('origin')!='v03_v04':raise ValueError('Mazo no vigente')
        if p.stage==Stage.JUVENTUD:
            if letter not in ('A','B'):raise ValueError('Movimiento juvenil requiere A/B')
            choice=letter
        else:
            if self.policy=='aleatorio':choice=self.rng.choice(('A','B'))
            else:choice=max(('A','B'),key=lambda v:(self._score(p,card.payload['effects'][v],v),v=='A'))
        position_before=self.eco.dynamic_affinity[p.id]
        pzone_before=zone(self.eco.dynamic_affinity[p.partner_id]) if p.partner_id is not None else None
        compatible_before=(zone(position_before)==pzone_before if pzone_before is not None else None)
        self._apply(p,card.payload['effects'][choice])
        self.eco.dynamic_affinity[p.id]+=shift(choice)
        position_after=self.eco.dynamic_affinity[p.id]
        self.eco.events.append({'action':'afinidad_desplazamiento','player':p.id,
                 'card':card.id,'choice':choice,'before':position_before,'after':position_after,
                 'zona_antes':zone(position_before),'zona_despues':zone(position_after),
                 'pareja_zona':pzone_before,
                 'pareja_compatible_antes':compatible_before,
                 'pareja_compatible_despues':(zone(position_after)==pzone_before if pzone_before is not None else None)})
        self.events.append({'action':'proposed_situation','round':engine.round_no,
             'player':p.id,'card':card.id,'stage':card.stage.value,'family':'A/B vigente',
             'result':choice,'source':card.payload['source']})
        self.eco.audit()
