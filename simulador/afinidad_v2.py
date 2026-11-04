"""Afinidad por decisiones A/B: modelo experimental 0, Neutro [-2,+2]."""
from __future__ import annotations

def zone(position:int)->str:
    if type(position) is not int:
        raise TypeError('La posición debe ser un entero')
    return 'A' if position <= -3 else ('B' if position >= 3 else 'Neutro')

def compatible(positions:dict[int,int],a:int,b:int)->bool:
    return zone(positions[a])==zone(positions[b])

def shift(letter:str)->int:
    if letter=='A':return -1
    if letter=='B':return 1
    raise ValueError('Solo A o B actualizan afinidad')
