"""Economía experimental. No modifica pagos, requisitos, reservas ni reglas del juego."""
from __future__ import annotations
from dataclasses import dataclass, asdict
import json
import pathlib

@dataclass(frozen=True)
class EconomyConfig:
    perfiles_pct: int = 100
    cartas_ganancias_pct: int = 100
    cartas_perdidas_pct: int = 100
    infancia_pct: int = 100
    juventud_pct: int = 0
    adultez_pct: int = 0

    def __post_init__(self):
        for name in ('perfiles_pct','cartas_ganancias_pct','cartas_perdidas_pct','infancia_pct'):
            v=getattr(self,name)
            if type(v) is not int or not 50<=v<=150:
                raise ValueError(f'{name} debe ser un entero entre 50 y 150: {v!r}')
        for name in ('juventud_pct','adultez_pct'):
            if type(getattr(self,name)) is not int or getattr(self,name) not in (0,100):
                raise ValueError(f'{name} solo admite 0 o 100 para el MVP')

    @classmethod
    def from_dict(cls,d:dict)->'EconomyConfig':
        if set(d)-set(cls.__dataclass_fields__):
            raise ValueError(f'Parámetros económicos desconocidos: {set(d)-set(cls.__dataclass_fields__)}')
        return cls(**d)


def scaled_int(amount:int, percentage:int, rng)->int:
    """Redondeo estocástico sin RNG adicional cuando el producto es entero.

    La rama pct==100 preserva completamente el consumo de RNG original.
    RNG de economía es independiente de dados, cartas y políticas de bots.
    """
    if percentage==100: return amount
    if amount<0: raise ValueError('scaled_int recibe valores no negativos')
    whole, remainder = divmod(amount*percentage, 100)
    if remainder:
        return whole + (rng.random()<remainder/100)
    return whole


@dataclass(frozen=True)
class ScenarioConfig:
    id: str = 'base_v13_solo_infancia'
    jugadores: int = 6
    partidas: int = 1000
    seed: int = 131028
    incremento_seed: int = 103
    max_rondas: int = 120
    bot: str = 'mixed'
    economia: EconomyConfig = EconomyConfig()

    def __post_init__(self):
        if self.jugadores not in (6,10): raise ValueError('El MVP solo admite 6 o 10 jugadores')
        if type(self.partidas) is not int or self.partidas<1: raise ValueError('partidas debe ser >=1')
        if type(self.seed) is not int: raise ValueError('seed debe ser entero')
        if type(self.incremento_seed) is not int or self.incremento_seed<1: raise ValueError('incremento_seed debe ser >0')
        if type(self.max_rondas) is not int or self.max_rondas<1: raise ValueError('max_rondas debe ser >=1')
        if self.bot not in ('mixed','inversor','oportunista','planificador','competitivo','cooperativo'):
            raise ValueError('bot no reconocido')

    @classmethod
    def load(cls,path: str|pathlib.Path)->'ScenarioConfig':
        data=json.loads(pathlib.Path(path).read_text(encoding='utf-8'))
        keys=set(cls.__dataclass_fields__)
        if set(data)-keys: raise ValueError(f'Campos desconocidos: {set(data)-keys}')
        data['economia']=EconomyConfig.from_dict(data.get('economia',{}))
        return cls(**data)

    def as_dict(self):return asdict(self)
