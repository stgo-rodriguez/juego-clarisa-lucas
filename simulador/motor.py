"""Adaptador parametrizable para el motor v1.3 congelado.

No altera el código base. Sobrescribe solo producción y efectos de cartas.
Las políticas de bots originales permanecen en motor_v13_base.py durante Fase 1;
su extracción física se pospone hasta poder certificar equivalencia tras el refactor.
"""
from __future__ import annotations
import random
from . import motor_v13_base as base
from .economia import EconomyConfig,scaled_int

class Game(base.Game):
    def __init__(self,*args,economia:EconomyConfig|None=None,**kwargs):
        self.economia=economia if economia is not None else EconomyConfig()
        seed=kwargs.get('seed', args[1] if len(args)>1 else None)
        if seed is None: raise ValueError('Es obligatorio informar semilla')
        self.rng_economia=random.Random(seed*13+4)
        # Cuando cualquier etapa posterior está habilitada, permitimos que
        # square_gain base llegue al adaptador de producción (con filtro por etapa).
        kwargs['casilleros_solo_infancia']=(self.economia.juventud_pct==0 and self.economia.adultez_pct==0)
        super().__init__(*args,**kwargs)

    def square_gain(self,members,stage,dest,exact):
        if stage=='Juventud' and self.economia.juventud_pct==0:return
        if stage=='Adultez' and self.economia.adultez_pct==0:return
        return super().square_gain(members,stage,dest,exact)

    def produce(self,p,r,n,source):
        pct={'profile':self.economia.perfiles_pct,
             'square': (self.economia.infancia_pct if p.stage=='Infancia' else
                        self.economia.juventud_pct if p.stage=='Juventud' else
                        self.economia.adultez_pct)}.get(source,100)
        transformed=scaled_int(n,pct,self.rng_economia)
        if source=='profile' and p.profile is not None:
            # Motor original suma el importe sin escalar luego de producirlo.
            # Compensamos para mantener exacta la instrumentación auxiliar.
            self.profile_production[f'{p.profile.uid}_{r}']+=transformed-n
        return super().produce(p,r,transformed,source)

    def _scale_card(self,card):
        e=self.economia
        if e.cartas_ganancias_pct==100 and e.cartas_perdidas_pct==100:return card
        def scale(effect):
            return {r:scaled_int(n,e.cartas_ganancias_pct,self.rng_economia)
                    if n>=0 else -scaled_int(-n,e.cartas_perdidas_pct,self.rng_economia)
                    for r,n in effect.items()}
        return base.Card(card.id,scale(card.a),scale(card.b))

    def pick_card(self,p,card):
        return super().pick_card(p,self._scale_card(card))


def run_batch(n,players,seed,cards,log_samples=2,max_rounds=120,bot_mode='mixed',
              economia:EconomyConfig|None=None,incremento_seed=103):
    rows=[];samples=[]
    for i in range(n):
        game=Game(i+1,seed+i*incremento_seed,players,cards,log=i<log_samples,
                  max_rounds=max_rounds,bot_mode=bot_mode,economia=economia).run()
        rows.append(game.summary())
        if i<log_samples:
            samples.append({'partida':game.id,'semilla':game.seed,'errores':game.errors,'eventos':game.eventlog})
    return rows,samples

write_csv=base.write_csv
aggregate=base.aggregate
parse_cards=base.parse_cards
