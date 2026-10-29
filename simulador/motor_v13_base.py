#!/usr/bin/env python3
"""Clarisa & Lucas Monte Carlo v1.3.0-exp1.
Fuente normativa: v1.3 28/10/2026 y decisiones posteriores del usuario:
comprobantes transferibles con sus derechos; solvencia para iniciar cualquier Duelo.

Referencia reutilizada: sim_v034r02_conversion_planner.py (algoritmos de mazos,
registro de hitos, RNG separables, y esquema de resultados); NO se reutiliza
la máquina individual de hitos, incompatible con v1.3.

Supuestos de políticas bots y cuestiones ambiguas: ver SUPUESTOS_v13.md.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from collections import Counter, defaultdict
import argparse, csv, json, random, math, statistics, pathlib

R=('A','P','K','M')
ROLES=('Clarisa','Lucas')
PROFILES={
 'Clarisa':((2,1,2,1),(2,1,1,2),(1,1,1,3),(1,0,1,4)),
 'Lucas':((2,2,1,1),(2,1,1,2),(1,1,1,3),(1,0,1,4)),
}
PROFILE_LABELS={
 'Clarisa':('Consultora BI','Consultora senior / Líder BI','Líder de Inteligencia de Negocios','Ingeniería de Datos / Ciencia de Decisiones'),
 'Lucas':('Profesional inicial','Especialista','Coordinador / Líder','Gerente / Director'),
}
MARKS={'Infancia':6,'Juventud':6,'Adultez':7}
CIRCUIT={
 'Infancia':{2:('A',3),5:('P',2)},
 'Juventud':{1:('K',1,2),2:('P',1,2),4:('K',1,2),5:('P',1,2)},
 'Adultez':{1:('M',3,6),3:('A',2,4)},
}
SUBHITOS={'Titulo':(('K',1),('K',2),('K',3)), 'Italia':(('P',2),('P',3),('M',2)), 'Polonia':(('P',2),('P',3),('M',2))}

@dataclass(frozen=True)
class Card:
    id:str
    a:dict
    b:dict

def parse_cards(path):
    cards={'I':[],'J':[],'A':[]}
    for line in pathlib.Path(path).read_text(encoding='utf-8').splitlines():
        if not line.strip() or line.lstrip().startswith('#'): continue
        cid, raw=line.split(None,1)
        def effect(part):
            ret={r:0 for r in R}
            for t in part.split(','):
                t=t.strip()
                import re
                m=re.fullmatch(r'([APKM])([0-9]+)-([APKM])([0-9]+)',t)
                if not m: raise ValueError((cid,t))
                ret[m[1]]+=int(m[2]);ret[m[3]]-=int(m[4])
            return ret
        one,two=raw.strip().split('|')
        cards[cid[0]].append(Card(cid,effect(one),effect(two)))
    assert {k:len(v) for k,v in cards.items()}=={'I':24,'J':24,'A':30}
    assert len({c.id for vs in cards.values() for c in vs})==78
    return cards

class Deck:
    def __init__(self, cards, rng):
        self.all=list(cards);self.rng=rng;self.stack=[];self.shuffle()
    def shuffle(self):self.stack=self.all[:];self.rng.shuffle(self.stack)
    def draw(self):
        if not self.stack:self.shuffle()
        return self.stack.pop()

@dataclass(frozen=True)
class Profile:
    uid:str
    role:str
    tier:int
    affinity:int
    production:tuple

@dataclass
class Player:
    id:int
    role:str
    r:dict=field(default_factory=lambda:{x:0 for x in R}) # existencias libres + reservadas
    pair_res:int=0
    house_a:int=0
    house_p:int=0
    stage:str='Infancia'
    pos:int=1
    utn:bool=False
    at_utn:bool=False
    utn_passed:bool=False
    profile:Profile|None=None
    pair:int|None=None
    title:bool=False
    passport:bool=False
    passport_kind:str|None=None
    title_project:str|None=None
    passport_project:str|None=None
    married:bool=False
    used_profile_change:bool=False
    used_duel:bool=False
    used_adjudication:bool=False
    first:dict=field(default_factory=dict)
    bot:str='planificador'
    def free(self,r):return self.r[r]-(self.pair_res if r=='A' else 0)-(self.house_a if r=='A' else 0)-(self.house_p if r=='P' else 0)

@dataclass
class Receipt:
    id:str
    project:str
    subhito:int
    original:int
    owner:int

@dataclass
class Project:
    id:str
    kind:str
    subhitos:list=field(default_factory=list) # Receipt ids; ordered, indivisible
    state:str='abierto'
    winner:int|None=None
    created:int=0
    completed:int|None=None
    adjudicated:int|None=None
    last_funded_turn:dict=field(default_factory=dict)

class Market:
    def __init__(self,rng):
        self.hidden={};self.visible={};self.rng=rng
        for role in ROLES:
            deck=[Profile(f'{role[0]}-{tier+1}-{affinity+1}',role,tier,affinity,PROFILES[role][tier]) for tier in range(4) for affinity in range(4)]
            rng.shuffle(deck)
            self.visible[role]=[deck.pop()] # visible top is list[-1]
            self.hidden[role]=deck # hidden top is list[-1]
    def take(self,role,source):
        stack=self.visible[role] if source=='visible' else self.hidden[role]
        return stack.pop() if stack else None
    def put(self,profile,destination):
        if profile is None:return
        if destination=='visible':self.visible[profile.role].append(profile)
        else:self.hidden[profile.role].insert(0,profile)
    def valid(self):
        return sorted(p.uid for role in ROLES for pile in (self.visible[role],self.hidden[role]) for p in pile)

class Game:
    def __init__(self,id,seed,nplayers,cards,log=False,bot_mode='mixed',max_rounds=120,casilleros_solo_infancia=True):
        assert nplayers in (6,10)
        self.casilleros_solo_infancia=casilleros_solo_infancia
        self.id=id;self.seed=seed;self.rng_dice=random.Random(seed*13+1);self.rng_cards=random.Random(seed*13+2);self.rng_bot=random.Random(seed*13+3)
        self.max_rounds=max_rounds; self.round=0;self.turn=0;self.finished=False;self.win=None;self.log=log
        rlist=['Clarisa']*(nplayers//2)+['Lucas']*(nplayers//2)
        strategies=['inversor','oportunista','planificador','cooperativo','competitivo']
        self.players=[Player(i+1,rlist[i],bot= (strategies[i%len(strategies)] if bot_mode=='mixed' else bot_mode)) for i in range(nplayers)]
        self.decks={'I_C':Deck(cards['I'][:12],self.rng_cards),'I_L':Deck(cards['I'][12:],self.rng_cards),'J':Deck(cards['J'],self.rng_cards),'A':Deck(cards['A'],self.rng_cards)}
        self.market=Market(self.rng_cards)
        self.projects={};self.receipts={};self.house_owner=None
        self.stats=Counter();self.eventlog=[];self.first={x:None for x in ('UTN','Titulo','Pasaporte','Pareja','Adultez','Casa','Casamiento')}
        self.resource_flow=Counter();self.profiles_counter=Counter();self.profile_production=Counter();self.card_branch=Counter()
        self.errors=[];self.house_age=[];self.last_house_round=None;self.censored=False;self.first_affinity_compatible=None

    def p(self,id):return self.players[id-1]
    def partner(self,p):return self.p(p.pair) if p.pair else None
    def pairkey(self,p):return tuple(sorted((p.id,p.pair))) if p.pair else None
    def event(self,action,**kw):
        if self.log:self.eventlog.append({'ronda':self.round,'turno':self.turn,'evento':action,**kw})
    def mark(self,p,k):
        if k not in p.first:
            p.first[k]=self.round
            for r in R:self.stats[f'recurso_al_hito_{k}_{r}_total']+=p.free(r)
            self.stats[f'recurso_al_hito_{k}_jugadores']+=1
        if self.first.get(k) is None:self.first[k]=self.round
    def produce(self,p,r,n,source):
        if n<=0:return
        p.r[r]+=n;self.resource_flow[f'{source}_{r}']+=n;self.event('produce',jugador=p.id,recurso=r,n=n,fuente=source)
    def pay(self,p,r,n,source,share=True):
        if n<0:return False
        if n==0:return True
        if not self.ensure_free(p,r,n,share):return False
        p.r[r]-=n;self.resource_flow[f'consume_{source}_{r}']+=n;self.event('pago',jugador=p.id,recurso=r,n=n,causa=source)
        return True
    def ensure_free(self,p,r,n,share=True):
        if p.free(r)>=n:return True
        mate=self.partner(p) if share else None
        shortage=n-p.free(r)
        if mate and mate.free(r)>=shortage:
            mate.r[r]-=shortage;p.r[r]+=shortage
            self.stats['transfer_pair']+=1
            self.event('transfer_pair',desde=mate.id,hacia=p.id,recurso=r,n=shortage)
            return True
        return False
    def feasible(self,p,req,share=True):
        mate=self.partner(p) if share else None
        return all(p.free(r)+(mate.free(r) if mate else 0)>=n for r,n in req.items())
    def total_available(self,p,r):return p.r[r]+(self.partner(p).r[r] if p.pair else 0)
    def reserve_pair(self,p):
        if not self.ensure_free(p,'A',5):return False
        p.pair_res=5;return True
    def lose_house(self,cause):
        if self.house_owner is None:return
        for pid in self.house_owner:
            x=self.p(pid);x.house_a=0;x.house_p=0
        if self.last_house_round is not None:self.house_age.append(self.round-self.last_house_round)
        self.last_house_round=None;self.event('perdida_casa',propietarios=self.house_owner,causa=cause)
        self.house_owner=None;self.stats[f'house_lost_{cause}']+=1
    def fall_to_youth(self,p,cause):
        mate=self.partner(p)
        if p.stage=='Adultez' or (mate and mate.stage=='Adultez'):
            if self.house_owner==self.pairkey(p):self.lose_house(cause)
            for x in ([p,mate] if mate else [p]):
                x.stage='Juventud';x.pos=1
            self.stats['regress_youth']+=1
            self.event('retroceso_juventud',jugador=p.id,causa=cause)
    def break_pair(self,p,cause='voluntaria'):
        mate=self.partner(p)
        if not mate:return
        pair=self.pairkey(p)
        if self.house_owner==pair:self.lose_house('ruptura')
        if p.stage=='Adultez' or mate.stage=='Adultez':
            p.stage=mate.stage='Juventud';p.pos=mate.pos=1
        p.pair=None;mate.pair=None;p.pair_res=mate.pair_res=0
        self.stats['rupturas']+=1;self.stats[f'ruptura_{cause}']+=1
        self.event('ruptura',jugadores=pair,causa=cause)
    def check_held(self,p):
        mate=self.partner(p)
        if mate and (p.pair_res<5 or mate.pair_res<5):
            for x in (p,mate):
                if x.pair_res<5 and self.ensure_free(x,'A',5-x.pair_res):x.pair_res=5
            if p.pair_res<5 or mate.pair_res<5:self.break_pair(p,'sin_amor')
        if self.house_owner:
            own=[self.p(x) for x in self.house_owner]
            if any(x.house_a<8 or x.house_p<5 for x in own):self.lose_house('sin_reserva')
    def loss(self,p,r,n,source='carta'):
        # Avoid damaging reserves when free resources on either partner suffice.
        for x in ([p,self.partner(p)] if p.pair else [p]):
            if x is None:continue
            taken=min(n,max(0,x.free(r)));x.r[r]-=taken;n-=taken
            self.resource_flow[f'lost_{source}_{r}']+=taken
            if n<=0:break
        if n>0:
            for x in ([p,self.partner(p)] if p.pair else [p]):
                if x is None:continue
                if r=='A':
                    take=min(n,x.pair_res);x.pair_res-=take;x.r[r]-=take;n-=take;self.resource_flow[f'lost_{source}_{r}']+=take
                    take=min(n,x.house_a);x.house_a-=take;x.r[r]-=take;n-=take;self.resource_flow[f'lost_{source}_{r}']+=take
                if r=='P':
                    take=min(n,x.house_p);x.house_p-=take;x.r[r]-=take;n-=take;self.resource_flow[f'lost_{source}_{r}']+=take
                if n<=0:break
        self.check_held(p)
    def score_resource(self,p,r):
        if p.stage=='Infancia':return {'A':1.1,'P':1.0,'K':2.3,'M':.15}[r]
        if p.stage=='Juventud':
            wanted={'A':1.0,'P':1.2,'K':1.5,'M':2.2}
            if not p.title:wanted['K']=2.5
            if not p.passport:wanted['P']=2.0
            if p.pair is None:wanted['A']=2.4
            return wanted[r]
        if self.house_owner==self.pairkey(p):return {'A':2.8,'P':3.,'K':.45,'M':.9}[r]
        return {'A':2.4,'P':2.,'K':.55,'M':2.6}[r]
    def pick_card(self,p,card):
        def utility(e):
            sc=sum(v*self.score_resource(p,r) for r,v in e.items())
            for r,v in e.items():
                if v<0 and -v>p.free(r)+(self.partner(p).free(r) if p.pair else 0):sc-=15
            return sc
        a=utility(card.a);b=utility(card.b)
        return ('A',card.a) if a>=b else ('B',card.b)
    def card_at(self,p):
        deck=self.decks[('I_C' if p.role=='Clarisa' else 'I_L') if p.stage=='Infancia' else ('J' if p.stage=='Juventud' else 'A')]
        card=deck.draw();opt,eff=self.pick_card(p,card)
        # Simultaneous gain/loss assumption: losses first; gains afterwards.
        for r,n in eff.items():
            if n<0:self.loss(p,r,-n,'card')
        for r,n in eff.items():
            if n>0:self.produce(p,r,n,'card')
        self.stats['cards']+=1;self.card_branch[f'{card.id}_{opt}']+=1
        self.event('carta',jugador=p.id,carta=card.id,opcion=opt,efecto=eff)

    def utntest(self,p):
        die=self.rng_dice.randint(1,6);self.stats['utn_attempts']+=1
        if die>=4:
            p.utn=True;p.utn_passed=True;p.at_utn=False;self.mark(p,'UTN')
            card=self.market.take(p.role,'tapada')
            if card is None:card=self.market.take(p.role,'visible') # exhaustion policy
            p.profile=card;self.event('utn_aprobada',jugador=p.id,dado=die,perfil=card.uid if card else None)
        else:self.event('utn_falla',jugador=p.id,dado=die)

    def roll_movement(self,p):
        mate=self.partner(p);die=self.rng_dice.randint(1,6)
        members=[p]+([mate] if mate else [])
        stage=p.stage
        if any(x.stage!=stage or x.pos!=p.pos for x in members):
            self.errors.append('La pareja no comparte etapa y posicion')
            for x in members:x.stage=stage;x.pos=p.pos
        for step in range(die):
            prev=p.pos;n=MARKS[stage];dest=prev%n+1
            crossing=(prev==n and dest==1)
            for x in members:x.pos=dest
            if crossing:
                for x in members:
                    if x.profile:
                        self.profiles_counter[x.profile.uid]+=1
                        for k,r in enumerate(R):
                            amt=x.profile.production[k];self.produce(x,r,amt,'profile');self.profile_production[f'{x.profile.uid}_{r}']+=amt
                    self.stats['lap_crossings']+=1
            self.square_gain(members,stage,dest,step==die-1)
            if stage=='Infancia' and dest==5 and p.free('P')>=2 and p.free('K')>=1:
                if p.bot!='oportunista' or self.rng_bot.random()<.96:
                    p.at_utn=True;p.stage='UTN';p.pos=0
                    self.utntest(p)
                    return False # no final square actions
        return True
    def square_gain(self,members,stage,dest,exact):
        # Escenario aislado: eliminar SOLO las ganancias automáticas de casillero
        # de Juventud y Adultez. Los cruces de marca, perfiles y cartas siguen vigentes.
        if self.casilleros_solo_infancia and stage != "Infancia":return
        if dest not in CIRCUIT[stage]:return
        t=CIRCUIT[stage][dest];amt=t[2] if exact and len(t)>2 else t[1]
        for x in members:self.produce(x,t[0],amt,'square')
    def project_for(self,kind):return [x for x in self.projects.values() if x.kind==kind and x.state=='abierto']
    def owns_right(self,p,pr):return any(self.receipts[rid].owner==p.id for rid in pr.subhitos)
    def can_fund(self,p,pr):
        idx=len(pr.subhitos)
        if pr.state!='abierto' or idx>=3 or pr.last_funded_turn.get(p.id)==self.turn:return False
        if pr.kind!='Titulo' and idx<2 and (('Italia' if p.role=='Clarisa' else 'Polonia')!=pr.kind):return False
        r,n=SUBHITOS[pr.kind][idx]
        return self.feasible(p,{r:n})
    def funding(self,p,funded):
        if not p.utn or p.stage not in ('Juventud','Adultez'):return
        needs=['Titulo' if not p.title else None,('Italia' if p.role=='Clarisa' else 'Polonia') if not p.passport else None]
        kinds=[x for x in needs if x]
        self.rng_bot.shuffle(kinds)
        for kind in kinds:
            # Prioritize completing open projects over creating redundant ones.
            allopen=self.project_for(kind)
            allopen.sort(key=lambda x:(-len(x.subhitos),not self.owns_right(p,x)))
            choices=[x for x in allopen if x.id not in funded and self.can_fund(p,x)]
            if choices:pr=choices[0]
            elif not allopen and len([x for x in self.projects.values() if x.kind==kind])<len(self.players):
                key=f'{kind}-{len(self.projects)+1}';pr=Project(key,kind,created=self.round);self.projects[key]=pr
                self.stats[f'project_created_{kind}']+=1;self.event('proyecto_abierto',id=key,tipo=kind)
                if not self.can_fund(p,pr):continue
            else:continue
            idx=len(pr.subhitos);r,n=SUBHITOS[kind][idx]
            # Opportunists fund only when approaching an adjudicable completed project.
            if p.bot=='oportunista' and idx==0 and self.rng_bot.random()<.55:continue
            buffer=0 if p.bot in ('inversor','cooperativo') else (1 if r in ('K','P') else 0)
            if p.free(r)+(self.partner(p).free(r) if p.pair else 0)<n+buffer:continue
            if not self.pay(p,r,n,'inversion'):continue
            rid=f'{pr.id}-S{idx+1}';rec=Receipt(rid,pr.id,idx+1,p.id,p.id)
            self.receipts[rid]=rec;pr.subhitos.append(rid);funded.add(pr.id);pr.last_funded_turn[p.id]=self.turn
            self.stats['funded_subhitos']+=1;self.event('inversion',proyecto=pr.id,subhito=idx+1,inversor=p.id,recibo=rid,recurso=r,importe=n)
            if len(pr.subhitos)==3:
                pr.completed=self.round;self.stats['projects_complete']+=1
                self.event('proyecto_completo',proyecto=pr.id)
    def try_adjudicate(self,p):
        if p.used_adjudication or p.stage!='Juventud':return
        kind='Titulo' if p.pos in (1,4) else ('Italia' if p.role=='Clarisa' else 'Polonia') if p.pos in (2,5) else None
        if not kind or (p.title if kind=='Titulo' else p.passport):return
        possible=[pr for pr in self.project_for(kind) if len(pr.subhitos)==3 and self.owns_right(p,pr)]
        if not possible:return
        r='K' if kind=='Titulo' else 'P';available=p.free(r)+(self.partner(p).free(r) if p.pair else 0)
        if available<1:return
        payment=self.choose_payment(p,r,available)
        if not self.pay(p,r,payment,'adjudicacion'):return
        p.used_adjudication=True;self.stats['adjudication_attempts']+=1
        die=self.rng_dice.randint(1,6) if payment<6 else 6
        success=(die>=7-payment)
        pr=possible[0]
        self.event('examen_adjudicacion',jugador=p.id,proyecto=pr.id,pago=payment,dado=die,aprobado=success)
        if success:
            pr.state='adjudicado';pr.winner=p.id;pr.adjudicated=self.round
            for rr,nn in SUBHITOS[pr.kind]:self.resource_flow[f'settle_project_{rr}']+=nn
            if kind=='Titulo':p.title=True;p.title_project=pr.id;self.mark(p,'Titulo')
            else:p.passport=True;p.passport_kind=p.role;p.passport_project=pr.id;self.mark(p,'Pasaporte')
            self.stats['adjudication_success']+=1
            self.stats['adjud_by_not_original_investor']+=int(not any(self.receipts[x].original==p.id for x in pr.subhitos))
            self.stats['adjudication_used_traded_receipt']+=int(any(self.receipts[x].owner==p.id and self.receipts[x].original!=p.id for x in pr.subhitos))
            self.event('hito_adjudicado',jugador=p.id,proyecto=pr.id)
    def choose_payment(self,p,r,available):
        # Resource fee proportional to probability of success, but immediate timing matters.
        urgency=1 if p.pair else 0
        if p.stage=='Juventud' and (p.title!=p.passport):urgency+=1
        if p.bot=='planificador': urgency+=1
        if available>=6 and urgency>=1:return 6
        return max(1,min(available,4+urgency if available>=4 else available))

    def pair_encounters(self,p):
        # Los circuitos de Infancia son físicamente independientes.
        if p.pair or p.stage=='Infancia':return
        others=[x for x in self.players if x.role!=p.role and x.stage==p.stage and x.pos==p.pos and x.id!=p.id]
        if not others:return
        others.sort(key=lambda x:(int(x.title)+int(x.passport),x.r['A']),reverse=True)
        for target in others:
            if target.pair:
                continue # experimental bot: does not replace existing couples
            if not self.feasible_pair(p,target):continue
            self.rebalance_pair(p,target)
            p.pair=target.id;target.pair=p.id
            assert p.free('A')>=5 and target.free('A')>=5
            p.pair_res=target.pair_res=5
            self.stats['pair_formed']+=1;self.mark(p,'Pareja');self.mark(target,'Pareja')
            self.event('formacion_pareja',jugadores=(p.id,target.id))
            return
    def feasible_pair(self,a,b):return a.free('A')+b.free('A')>=10
    def rebalance_pair(self,a,b):
        if a.free('A')<5:
            n=5-a.free('A');b.r['A']-=n;a.r['A']+=n
        if b.free('A')<5:
            n=5-b.free('A');a.r['A']-=n;b.r['A']+=n
    def enter_adult(self,p):
        m=self.partner(p)
        if not m or p.stage!='Juventud' or p.pos not in (2,5):return
        if not all(x.title and x.passport and x.passport_kind==x.role and x.pair_res==5 for x in (p,m)):return
        if not all(self.feasible(x,{'K':5,'M':5},share=False) for x in (p,m)):
            # Collective resource redistribution can permit each member to satisfy the personal test.
            for r in ('K','M'):
                if p.free(r)+m.free(r)<10:return
                for x,y in ((p,m),(m,p)):
                    if x.free(r)<5:
                        d=5-x.free(r);y.r[r]-=d;x.r[r]+=d
        for x in (p,m):
            if x.free('K')<5 or x.free('M')<5:return
        for x in (p,m):x.stage='Adultez';x.pos=1;self.mark(x,'Adultez')
        self.stats['adult_entry']+=1;self.event('entrada_adultez',pareja=self.pairkey(p))

    def try_house(self,p):
        m=self.partner(p)
        if not m or self.house_owner==self.pairkey(p):return
        if not self.feasible(p,{'A':8,'P':5}) or not self.feasible(m,{'A':8,'P':5}):return
        # Each person's personal quota can be achieved by redistribution.
        for r,n in (('A',8),('P',5)):
            if p.free(r)+m.free(r)<2*n:return
            for x,y in ((p,m),(m,p)):
                if x.free(r)<n:
                    d=n-x.free(r);y.r[r]-=d;x.r[r]+=d
        if not self.feasible(p,{'A':8,'P':5},share=False) or not self.feasible(m,{'A':8,'P':5},share=False):return
        for num in range(1,6):
            price=15+(num-1)*5
            if p.free('M')+m.free('M')<2*price:break
            # To have enough personally, rebalance all the required money first.
            for x,y in ((p,m),(m,p)):
                if x.free('M')<price:
                    d=price-x.free('M');y.r['M']-=d;x.r['M']+=d
            if not all(x.free('M')>=price for x in (p,m)):break
            self.stats['house_attempts']+=1
            score_buy=self.rng_dice.randint(1,6)+self.rng_dice.randint(1,6)
            score_sell=self.rng_dice.randint(1,6)+self.rng_dice.randint(1,6)
            if score_buy<=score_sell:
                self.stats['house_failed']+=1
                continue
            prior=self.house_owner
            for x in (p,m):
                self.pay(x,'M',price,'casa',share=False);x.house_a=8;x.house_p=5
            if prior:
                sellers=[self.p(x) for x in prior]
                for x in sellers:x.r['M']+=price
                self.resource_flow['transfer_sale_house_M']+=2*price
                self.stats['house_transfers']+=1
                if self.last_house_round is not None:self.house_age.append(self.round-self.last_house_round)
                for x in sellers:x.house_a=x.house_p=0
            self.house_owner=self.pairkey(p);self.last_house_round=self.round
            self.stats['house_bought']+=1;self.mark(p,'Casa');self.mark(m,'Casa')
            self.event('compra_casa',pareja=self.house_owner,precio_personal=price,expropietarios=prior)
            return

    def try_marriage(self,p):
        m=self.partner(p)
        if not m or self.house_owner!=self.pairkey(p):return
        if p.profile is None or m.profile is None or p.profile.affinity!=m.profile.affinity:
            self.stats['blocked_affinity']+=1;return
        if not all(x.title and x.passport and x.passport_kind==x.role and x.pair_res==5 and x.house_a==8 and x.house_p==5 for x in (p,m)):return
        req={'A':12,'P':10,'M':5}
        for r,n in req.items():
            if p.free(r)+m.free(r)<2*n:self.stats[f'blocked_marriage_{r}']+=1;return
        for r,n in req.items():
            for x,y in ((p,m),(m,p)):
                if x.free(r)<n:
                    d=n-x.free(r);y.r[r]-=d;x.r[r]+=d
        if not all(self.feasible(x,req,share=False) for x in (p,m)):return
        for x in (p,m):
            for r,n in req.items():self.pay(x,r,n,'casamiento',share=False)
            x.married=True;self.mark(x,'Casamiento')
        self.stats['marriage']+=1;self.finished=True;self.win=self.pairkey(p)
        self.event('casamiento',ganadores=self.win)

    def change_character(self,p):
        # Legal al inicio de turno, incluso antes de aprobar UTN y sin perfil.
        if not self.pay(p,'P',3,'cambio_personaje'):return
        old=p.role;other='Lucas' if old=='Clarisa' else 'Clarisa'
        if p.pair:self.break_pair(p,'cambio_personaje')
        old_profile=p.profile
        if old_profile is not None:
            new=self.market.take(other,'visible' if self.rng_bot.random()<.5 else 'tapada')
            if new is None:new=self.market.take(other,'tapada' if self.market.hidden[other] else 'visible')
            if new is None:
                p.r['P']+=3
                self.resource_flow['consume_cambio_personaje_P']-=3
                return # No se resuelve el agotamiento total del mercado sin un nuevo supuesto
            self.market.put(old_profile,'visible' if self.rng_bot.random()<.5 else 'tapada')
            p.profile=new
        p.role=other
        if p.stage=='Infancia':p.pos=1
        if p.passport:p.passport_kind=p.role
        self.stats['character_change']+=1;self.event('cambio_personaje',jugador=p.id,antes=old,despues=p.role)
    def change_profile(self,p):
        if not p.profile or p.used_profile_change:return
        mate=self.partner(p);match=(mate is not None and mate.profile is not None and mate.profile.affinity==p.profile.affinity)
        available=self.market.visible[p.role][-1] if self.market.visible[p.role] else None
        wants_affinity=bool(mate and mate.profile and not match and (self.house_owner==self.pairkey(p) or p.stage=='Adultez'))
        current_value=sum(v*self.score_resource(p,r) for r,v in zip(R,p.profile.production))
        best_visible=sum(v*self.score_resource(p,r) for r,v in zip(R,available.production)) if available else -100
        value=best_visible-current_value
        if not wants_affinity and (value<3.5 or self.round<15):return
        if wants_affinity and available and available.affinity==mate.profile.affinity:source='visible'
        elif not wants_affinity and available and value>=4:source='visible'
        else:source='tapada' if self.market.hidden[p.role] else 'visible'
        if source=='visible' and not available:return
        if not all(self.feasible(p,{r:3}) for r in R):return
        # Just one paid action; global capacity check because all free resources independent.
        for r in R:
            if not self.pay(p,r,3,'cambio_perfil'):return
        old=p.profile;new=self.market.take(p.role,source)
        if new is None:raise AssertionError('Paid for nonexistent profile')
        p.profile=new;p.used_profile_change=True
        dest='visible' if (new.affinity!=(mate.profile.affinity if mate and mate.profile else new.affinity) and self.rng_bot.random()<.5) else 'tapada'
        self.market.put(old,dest)
        self.stats['profile_changes']+=1;self.stats[f'profile_source_{source}']+=1
        self.event('cambio_perfil',jugador=p.id,antes=old.uid,despues=new.uid,origen=source,destino=dest)

    def duel_capacity(self,p,r,n):
        # Reserves may be used, but bots never initiate when free stocks are insufficient.
        mate=self.partner(p)
        return p.r[r]+(mate.r[r] if mate else 0)>=n
    def duel_legal(self,attacker,defender,r,n,defender_wager=True):
        return (attacker.id!=defender.id and attacker.role==defender.role and attacker.stage==defender.stage and attacker.pos==defender.pos and (not attacker.used_duel) and self.duel_capacity(attacker,r,n) and (not defender_wager or self.duel_capacity(defender,r,n)) and self.duel_capacity(attacker,'P',1))
    def can_challenge_hito(self,p,defender,kind):
        if kind=='Titulo':
            if p.title or not defender.title:return False
            pr=self.projects.get(defender.title_project or '')
            wager=('K',5)
        else:
            if p.passport or not defender.passport or defender.passport_kind!=p.role:return False
            pr=self.projects.get(defender.passport_project or '')
            wager=('P',5)
        return bool(pr and self.owns_right(p,pr) and self.duel_legal(p,defender,*wager,defender_wager=False))
    def withdraw_or_roll(self,p,d_def,kind):
        # Retreat when theoretical success chance poor and we can spare P without losses.
        if d_def>=5 and p.free('P')>=1:
            return self.rng_bot.random()<.84
        return False
    def transfer_duel(self,src,dst,r,n):
        # Frees first; then eligible reserves. Both sides may use their partner's resources.
        rest=n
        for x in [src]+([self.partner(src)] if src.pair else []):
            if x is None:continue
            d=min(rest,max(0,x.free(r)));x.r[r]-=d;dst.r[r]+=d;rest-=d
        if rest:
            for x in [src]+([self.partner(src)] if src.pair else []):
                if x is None:continue
                if r=='A':
                    d=min(rest,x.pair_res);x.pair_res-=d;x.r[r]-=d;dst.r[r]+=d;rest-=d
                    d=min(rest,x.house_a);x.house_a-=d;x.r[r]-=d;dst.r[r]+=d;rest-=d
                if r=='P':
                    d=min(rest,x.house_p);x.house_p-=d;x.r[r]-=d;dst.r[r]+=d;rest-=d
                if not rest:break
        if rest:raise AssertionError(('duel insolvent during payment',rest))
        self.check_held(src);self.check_held(dst)
        self.stats['duel_resource_transferred']+=n
    def lose_hito(self,p,kind):
        if kind=='Titulo':p.title=False;p.title_project=None
        else:p.passport=False;p.passport_project=None;p.passport_kind=None
        self.fall_to_youth(p,'perdida_'+kind)
    def execute_duel(self,p,defender,kind='recursos',r='P',n=1):
        if not self.duel_legal(p,defender,r,n,defender_wager=(kind=='recursos')):return False
        if kind=='perfil' and (not p.profile or not defender.profile):return False
        if kind=='Titulo' and not self.can_challenge_hito(p,defender,'Titulo'):return False
        if kind=='Pasaporte' and not self.can_challenge_hito(p,defender,'Pasaporte'):return False
        p.used_duel=True;self.stats['duels_started']+=1;self.stats[f'duel_{kind}']+=1
        d_def=self.rng_dice.randint(1,6)
        if self.withdraw_or_roll(p,d_def,kind):
            self.transfer_duel(p,defender,'P',1);self.stats['duel_retreats']+=1
            self.event('duelo_retirada',retador=p.id,defensor=defender.id,modalidad=kind)
            return True
        d_att=self.rng_dice.randint(1,6)
        if d_att>d_def:
            self.stats['duels_won']+=1
            if kind=='recursos':self.transfer_duel(defender,p,r,n)
            elif kind=='perfil':p.profile,defender.profile=defender.profile,p.profile;self.stats['profile_duels_swapped']+=1
            else:
                source=defender.title_project if kind=='Titulo' else defender.passport_project
                self.lose_hito(defender,kind)
                if kind=='Titulo':p.title=True;p.title_project=source;self.mark(p,'Titulo')
                else:p.passport=True;p.passport_kind=p.role;p.passport_project=source;self.mark(p,'Pasaporte')
                self.projects[source].winner=p.id
                self.stats['hito_duels_transferred']+=1
                self.stats['duel_used_traded_receipt']+=int(any(self.receipts[x].owner==p.id and self.receipts[x].original!=p.id for x in self.projects[source].subhitos))
        elif d_att<d_def:
            self.stats['duels_lost']+=1
            if kind=='recursos':self.transfer_duel(p,defender,r,n)
            elif kind in ('Titulo','Pasaporte'):self.transfer_duel(p,defender,'K' if kind=='Titulo' else 'P',5)
        else:self.stats['duels_tied']+=1
        self.event('duelo',retador=p.id,defensor=defender.id,modalidad=kind,dado_defensor=d_def,dado_retador=d_att)
        return True
    def duel_interaction(self,p):
        others=[x for x in self.players if x.id!=p.id and x.role==p.role and x.stage==p.stage and x.pos==p.pos]
        if not others:return
        for x in others:
            for kind in ('Titulo','Pasaporte'):
                if self.can_challenge_hito(p,x,kind) and self.rng_bot.random()<.67:
                    self.execute_duel(p,x,kind,'K' if kind=='Titulo' else 'P',5);return
            if p.profile and x.profile and not p.used_duel and self.duel_capacity(p,'P',1):
                val1=sum(v*self.score_resource(p,r) for r,v in zip(R,p.profile.production))
                val2=sum(v*self.score_resource(p,r) for r,v in zip(R,x.profile.production))
                if val2>val1+3 and self.rng_bot.random()<.6:
                    if self.duel_legal(p,x,'P',1):self.execute_duel(p,x,'perfil','P',1);return
            if not p.used_duel and self.duel_legal(p,x,'A',1) and p.free('P')>=1 and p.free('A')>=1:
                if p.bot=='competitivo' and self.rng_bot.random()<.12:
                    self.execute_duel(p,x,'recursos','A',1);return
    def transfer_receipt(self,seller,buyer,receipt_id,price=0,resource='M'):
        """Cesión indivisible de comprobante y ambos derechos; la nacionalidad NO restringe tenencia.
        Requiere negociación válida por coincidencia, precio pagable y vendedor propietario.
        """
        rec=self.receipts.get(receipt_id)
        if not rec or rec.owner!=seller.id or seller.id==buyer.id:return False
        if seller.stage!=buyer.stage or seller.pos!=buyer.pos:return False
        if price<0 or (price and not self.feasible(buyer,{resource:price},share=False)):return False
        if price:
            buyer.r[resource]-=price;seller.r[resource]+=price
            self.resource_flow[f'transfer_negotiation_{resource}']+=price
        rec.owner=buyer.id
        self.stats['receipts_traded']+=1
        self.event('venta_comprobante',recibo=receipt_id,desde=seller.id,hacia=buyer.id,precio=price,recurso=resource)
        return True
    def negotiate_receipt(self,p):
        # Experiment-specific bot policy: simple mutually beneficial priced transfer.
        targets=[x for x in self.players if x.id!=p.id and x.stage==p.stage and x.pos==p.pos and x.role!=p.role]
        for target in targets:
            if self.rng_bot.random()>.1:continue
            for rec in self.receipts.values():
                if rec.owner!=target.id:continue
                pr=self.projects[rec.project]
                if pr.kind!='Titulo' and (('Italia' if p.role=='Clarisa' else 'Polonia')!=pr.kind):continue
                if (p.title if pr.kind=='Titulo' else p.passport):continue
                if self.owns_right(p,pr):continue
                if p.free('M')<2:continue
                if not self.feasible(p,{'M':2},share=False):continue
                if self.transfer_receipt(target,p,rec.id,price=2):return
    def trade_resources(self,seller,buyer,gives,receives):
        """Intercambio bilateral de recursos libres al coincidir exactamente en casillero."""
        if seller.id==buyer.id or seller.stage!=buyer.stage or seller.pos!=buyer.pos:return False
        if any(n<0 for n in list(gives.values())+list(receives.values())):return False
        if not self.feasible(seller,gives,share=False) or not self.feasible(buyer,receives,share=False):return False
        for r,n in gives.items():seller.r[r]-=n;buyer.r[r]+=n
        for r,n in receives.items():buyer.r[r]-=n;seller.r[r]+=n
        self.stats['resource_trades']+=1
        self.event('intercambio_recursos',jugadores=[seller.id,buyer.id],entrega=gives,recibe=receives)
        return True
    def transfer_hito(self,seller,buyer,kind):
        """Entrega voluntaria de un hito; los comprobantes/derechos NO cambian de dueño."""
        if seller.id==buyer.id or seller.stage!=buyer.stage or seller.pos!=buyer.pos:return False
        if kind=='Titulo':
            if not seller.title or buyer.title:return False
            ref=seller.title_project
        elif kind=='Pasaporte':
            if not seller.passport or buyer.passport:return False
            ref=seller.passport_project
            nationality=seller.passport_kind
        else:return False
        self.lose_hito(seller,kind)
        if kind=='Titulo':buyer.title=True;buyer.title_project=ref;self.mark(buyer,'Titulo')
        else:buyer.passport=True;buyer.passport_project=ref;buyer.passport_kind=nationality;self.mark(buyer,'Pasaporte')
        self.projects[ref].winner=buyer.id
        self.stats['hitos_traded']+=1
        self.event('transferencia_hito',tipo=kind,proyecto=ref,desde=seller.id,hacia=buyer.id)
        return True
    def change_passport_owner(self,p,target):
        # Transferencia de hito es legal por negociación; bot base no la propone.
        if not p.passport or target.passport:return False
        if p.stage!=target.stage or p.pos!=target.pos:return False
        if target.role!=p.passport_kind:return False
        project=p.passport_project
        self.lose_hito(p,'Pasaporte');target.passport=True;target.passport_kind=target.role;target.passport_project=project
        self.projects[project].winner=target.id
        return True
    def bank(self,p):
        # One direction and a single adjacent pair, possibly multiple units of 2:1.
        if p.stage=='Infancia':priority=('K','P','A','M')
        elif p.stage=='Juventud':priority=('M','K','P','A') if (p.title and p.passport) else ('K','P','M','A')
        elif self.house_owner==self.pairkey(p):priority=('P','A','M','K')
        else:priority=('M','A','P','K')
        pairs=[('A','P'),('P','A'),('P','K'),('K','P'),('K','M'),('M','K')]
        target={'Infancia':{'K':1,'P':2,'A':5,'M':0},'Juventud':{'K':5,'P':6,'M':9,'A':5},'Adultez':{'K':0,'P':15,'M':16,'A':20}}[p.stage]
        if p.stage=='Adultez' and self.house_owner==self.pairkey(p):target={'K':0,'P':10,'M':5,'A':12}
        for dest in priority:
            if p.free(dest)>=target[dest]:continue
            for src,dst in pairs:
                if dst!=dest:continue
                qty=p.free(src)//2
                reserve=target.get(src,0) if src in ('K','M','A','P') else 0
                qty=min(qty,max(0,(p.free(src)-reserve)//2))
                if qty<1:continue
                qty=min(qty,max(1,target[dest]-p.free(dest)))
                if self.pay(p,src,qty*2,'banco'):
                    self.produce(p,dst,qty,'banco');self.stats['bank_conversions']+=1
                    self.event('conversion',jugador=p.id,origen=src,destino=dst,cantidad=qty)
                    return

    def audit_ledger(self):
        """Compara unidades creadas, pagadas, perdidas, protegidas y transferidas."""
        failures={}
        for r in R:
            gen=sum(self.resource_flow.get(f'{source}_{r}',0) for source in ('square','profile','card','banco'))
            consumed=sum(v for k,v in self.resource_flow.items() if k.startswith('consume_') and not k.startswith('consume_inversion_') and k.endswith('_'+r))
            consumed -= self.resource_flow.get(f'transfer_sale_house_{r}',0)
            lost=self.resource_flow.get(f'lost_card_{r}',0)
            settle=self.resource_flow.get(f'settle_project_{r}',0)
            stock=sum(p.r[r] for p in self.players)
            invested=sum(n for pr in self.projects.values() if pr.state=='abierto' for rr,n in SUBHITOS[pr.kind][:len(pr.subhitos)] if rr==r)
            actual=stock+invested
            expected=gen-consumed-lost-settle
            if actual!=expected:failures[r]=(actual,expected,gen,consumed,lost,settle,invested)
        return failures
    def validate(self):
        for p in self.players:
            for r in R:
                if p.r[r]<0 or p.free(r)<0:self.errors.append(f'negativo {p.id} {r}')
            if p.pair:
                mate=self.partner(p)
                if mate is None or mate.pair!=p.id:self.errors.append('pareja inconsistente')
            if p.profile and p.profile.role!=p.role:self.errors.append('perfil personaje no coincide')
        seen=set()
        for rid,rec in self.receipts.items():
            if rid in seen or not(1<=rec.owner<=len(self.players)):self.errors.append('comprobante duplicado/invalido')
            seen.add(rid)
        for pr in self.projects.values():
            if len(pr.subhitos)>3 or pr.subhitos!=[f'{pr.id}-S{i+1}' for i in range(len(pr.subhitos))]:self.errors.append('subhitos fuera orden')
        allcards=[p.profile.uid for p in self.players if p.profile]
        for role in ROLES:
            allcards += [card.uid for stack in (self.market.visible[role],self.market.hidden[role]) for card in stack]
        if len(allcards)!=32 or len(set(allcards))!=32:self.errors.append('invariante 32 perfiles')
        if self.house_owner and any(self.p(x).house_a<8 or self.p(x).house_p<5 for x in self.house_owner):self.errors.append('casa sin reservas')
        ledger=self.audit_ledger()
        if ledger:self.errors.append('balance del libro de recursos: '+repr(ledger))
        return not self.errors
    def do_turn(self,p):
        if self.finished:return
        self.turn+=1;p.used_profile_change=False;p.used_duel=False;p.used_adjudication=False
        if p.stage=='UTN':
            if p.utn_passed:p.stage='Juventud';p.pos=1;self.mark(p,'UTN')
            else:self.utntest(p);return
        # Character changes are legal but bot uses only to resolve a deadlock (no complementary roles remaining).
        if p.stage=='Juventud' and p.pair is None and p.utn and self.round>18 and self.round%14==0:
            if not any(x.role!=p.role and x.pair is None for x in self.players) and self.rng_bot.random()<.25:self.change_character(p)
        funded=set()
        self.funding(p,funded)
        movement_done=self.roll_movement(p)
        if not movement_done:return
        self.funding(p,funded)
        if p.stage=='Infancia' and p.pos in (1,3,4,6):self.card_at(p)
        elif p.stage=='Juventud':
            if p.pos in (3,6):self.card_at(p)
            if p.pos in (1,2,4,5):self.try_adjudicate(p)
            if p.pos in (2,5):self.enter_adult(p)
        elif p.stage=='Adultez':
            if p.pos in (2,6):self.card_at(p)
            elif p.pos in (4,5):self.try_house(p)
            elif p.pos==7:
                self.change_profile(p)  # permitted before final marriage validation
                self.try_marriage(p)
        if self.finished:return
        self.pair_encounters(p)
        self.negotiate_receipt(p)
        self.duel_interaction(p)
        self.change_profile(p)
        self.bank(p)
    def run(self):
        for rnd in range(1,self.max_rounds+1):
            self.round=rnd
            for p in self.players:
                self.do_turn(p)
                if self.finished:break
            if self.first_affinity_compatible is None:
                if any(x.profile and self.partner(x) and self.partner(x).profile and x.profile.affinity==self.partner(x).profile.affinity for x in self.players if x.pair):self.first_affinity_compatible=self.round
            for x in self.players:
                if x.stage in ('Infancia','Juventud','Adultez'):
                    self.stats['stage_samples_'+x.stage]+=1
                    for r in R:self.stats[f'stock_{x.stage}_{r}']+=x.free(r)
            if self.house_owner and not self.finished:
                c,m=(self.p(x) for x in self.house_owner)
                if c.profile and m.profile and c.profile.affinity!=m.profile.affinity:self.stats['house_incompatible_rounds']+=1
            if self.finished:break
        if not self.finished:self.censored=True
        self.validate()
        return self
    def summary(self):
        d={'partida':self.id,'semilla':self.seed,'jugadores':len(self.players),'terminada':int(self.finished),'censurada':int(self.censored),
           'rondas_observadas':self.round,'turnos_individuales':self.turn,'rondas_hasta_casamiento':self.round if self.finished else '',
           'ganadores':'-'.join(map(str,self.win)) if self.win else '', 'errores':len(self.errors),'proyectos':len(self.projects),
           'proyectos_completados':sum(x.completed is not None for x in self.projects.values()),
           'proyectos_adjudicados':sum(x.state=='adjudicado' for x in self.projects.values()),
           'inversores_distintos_promedio':round(statistics.mean([len({self.receipts[r].original for r in pr.subhitos}) for pr in self.projects.values()]),3) if self.projects else 0,
           'porcentaje_perfiles_afinidad_compatibles_parejas':int(self.win is not None),
           'casa_al_final':int(self.house_owner is not None),
           'saldo_A':sum(p.free('A') for p in self.players),'saldo_P':sum(p.free('P') for p in self.players),
           'saldo_K':sum(p.free('K') for p in self.players),'saldo_M':sum(p.free('M') for p in self.players),
           'proyectos_pendientes_completos':sum(x.completed is not None and x.state=='abierto' for x in self.projects.values()),
           'proyectos_incompletos':sum(x.completed is None for x in self.projects.values()),
           'demora_proyecto_completado_media':round(statistics.mean([x.completed-x.created for x in self.projects.values() if x.completed is not None]),2) if any(x.completed is not None for x in self.projects.values()) else '',
           'tenencia_casa_media':round(statistics.mean(self.house_age),2) if self.house_age else '',
           'ronda_afinidad_compatible':self.first_affinity_compatible if self.first_affinity_compatible is not None else '',
           'rondas_casa_a_casamiento':self.round-self.last_house_round if self.finished and self.last_house_round is not None else '',
           'ganadores_milestones':json.dumps({k:max((self.p(x).first.get(k) for x in self.win if k in self.p(x).first),default=None) for k in self.first},ensure_ascii=False) if self.win else ''}
        if self.win:
            winners=[self.p(x) for x in self.win]
            for k in ('UTN','Titulo','Pasaporte','Pareja','Adultez','Casa','Casamiento'):
                vals=[p.first.get(k) for p in winners]
                d[f'ronda_ambos_ganadores_{k.lower()}']=max(vals) if all(v is not None for v in vals) else ''
            if all(w.first.get(k) is not None for w in winners for k in ('Titulo','Pasaporte','Pareja')):
                d['ronda_ambos_listos_hitos']=max(w.first[k] for w in winners for k in ('Titulo','Pasaporte','Pareja'))
            if all(w.first.get('Casa') is not None for w in winners):
                d['rondas_primera_casa_ganadores_a_casamiento']=self.round-max(w.first['Casa'] for w in winners)
        d.update({'ronda_primera_'+k.lower():v if v is not None else '' for k,v in self.first.items()})
        d.update(self.stats)
        for k,v in self.resource_flow.items():d['flujo_'+k]=v
        for k,v in self.profiles_counter.items():d['perfil_usos_'+k]=v
        return d

def percentile(x,q):
    if not x:return None
    x=sorted(x); t=(len(x)-1)*q;l=math.floor(t);h=math.ceil(t)
    return round(x[l]+(x[h]-x[l])*(t-l),2)

def aggregate(rows):
    concluded=[r['rondas_observadas'] for r in rows if r['terminada']]
    result={'partidas':len(rows),'finalizadas':len(concluded),'censuradas':len(rows)-len(concluded),
            'tasa_finalizacion':round(len(concluded)/len(rows)*100,2)}
    for label,data in [('casamiento',concluded)]+[(k,[float(r[k]) for r in rows if r.get(k,'')!='']) for k in ['ronda_primera_utn','ronda_primera_titulo','ronda_primera_pasaporte','ronda_primera_pareja','ronda_primera_adultez','ronda_primera_casa']]:
        result[label]={ 'n':len(data),'media':round(statistics.mean(data),2) if data else None,'mediana':percentile(data,.5),'p75':percentile(data,.75),'p90':percentile(data,.9),'p95':percentile(data,.95)}
    for f in ('proyectos','proyectos_completados','proyectos_adjudicados','funded_subhitos','bank_conversions','duels_started','profile_changes','receipts_traded','house_attempts','blocked_affinity'):
        result[f+'_media']=round(statistics.mean(float(x.get(f,0)) for x in rows),3)
    return result

def run_batch(n,players,seed,cards,log_samples=2,max_rounds=120,bot_mode='mixed',casilleros_solo_infancia=True):
    rows=[];samples=[]
    for i in range(n):
        g=Game(i+1,seed+i*103,players,cards,log=(i<log_samples),max_rounds=max_rounds,bot_mode=bot_mode,casilleros_solo_infancia=casilleros_solo_infancia).run()
        rows.append(g.summary())
        if i<log_samples:samples.append({'partida':g.id,'semilla':g.seed,'errores':g.errors,'eventos':g.eventlog})
    return rows,samples

def write_csv(path,rows):
    fields=sorted({k for row in rows for k in row});preferred=['partida','semilla','jugadores','terminada','censurada','rondas_observadas','turnos_individuales','rondas_hasta_casamiento','errores']
    cols=[k for k in preferred if k in fields]+[k for k in fields if k not in preferred]
    with open(path,'w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows(rows)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--n',type=int,default=1000);ap.add_argument('--players',type=int,choices=(6,10),default=6)
    ap.add_argument('--seed',type=int,default=131028);ap.add_argument('--max-rounds',type=int,default=120);ap.add_argument('--out',default='.')
    ap.add_argument('--cards',default=str(pathlib.Path(__file__).parent/'cards_v13_effects.txt'))
    ap.add_argument('--bot',choices=['mixed','inversor','oportunista','planificador','competitivo','cooperativo'],default='mixed')
    ap.add_argument('--ingresos-casilleros',choices=['infancia','todos'],default='infancia')
    args=ap.parse_args();out=pathlib.Path(args.out);out.mkdir(parents=True,exist_ok=True)
    cards=parse_cards(args.cards)
    rows,samples=run_batch(args.n,args.players,args.seed,cards,max_rounds=args.max_rounds,bot_mode=args.bot,casilleros_solo_infancia=(args.ingresos_casilleros=='infancia'))
    write_csv(out/f'resultados_{args.players}j.csv',rows)
    (out/f'registro_muestra_{args.players}j.json').write_text(json.dumps(samples,ensure_ascii=False,indent=2),encoding='utf-8')
    agg=aggregate(rows)
    (out/f'resumen_{args.players}j.json').write_text(json.dumps(agg,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(agg,ensure_ascii=False,indent=2))
