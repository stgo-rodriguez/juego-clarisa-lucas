"""Primera versión ejecutable (experimental) del simulador económico v3.0.

No sustituye al reglamento ni al simulador v2.x. Incluye Infancia,
UTN, Juventud, proyectos cooperativos, pareja, Vuelo a Dublín,
Adultez 5x5, Casa y tres cierres. Duelos, cesiones de comprobantes,
cambios de rol, negociaciones complejas y disputas completas de hitos
NO están implementados: se declaran límites, no datos de balance validado.

El motor jamás toma importes v2.x por defecto: todos los importes de
ejemplo están en escenario_simulacion_NO_CALIBRADO.json.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import statistics
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path

from laboratorio.v3.catalogo import cargar_matriz, validar_ajustes
from laboratorio.v3.estado_v3 import LibroMayor, Personaje, EstadoInvalido, RECURSOS

EJEMPLO = Path(__file__).with_name("escenario_simulacion_NO_CALIBRADO.json")
ETAPAS = ("Infancia", "Juventud", "Adultez")
LETRAS = ("A", "B")
DIRECCIONES = tuple(
    (dr, dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1)
    if dr or dc
)
CASILLEROS_INFANCIA = {1:"A", 2:"P", 3:"A", 4:"P", 5:"K", 6:"A"}
CASILLEROS_ADULTOS = {
    (1,1):"K", (1,5):"A", (2,1):"M",
    (3,5):"M", (4,2):"P", (5,2):"A"
}

PARAMETROS_REQUERIDOS = (
    "UTN_UMBRAL_P", "UTN_UMBRAL_K",
    "TITULO_SUBHITO_1_K", "TITULO_SUBHITO_2_K", "TITULO_SUBHITO_3_K",
    "PASAPORTE_SUBHITO_1_P", "PASAPORTE_SUBHITO_2_P", "PASAPORTE_SUBHITO_3_M",
    "ADJ_TITULO_PAGO_MIN_K", "ADJ_PASAPORTE_PAGO_MIN_P",
    "PAREJA_RESERVA_A", "DUBLIN_UMBRAL_K", "DUBLIN_UMBRAL_M",
    "CASA_RESERVA_A", "CASA_RESERVA_P", "CASA_OFERTA_BASE_M",
    "CASA_OFERTA_INCREMENTO_M", "FALSO_LUCAS_META_M",
    *(f"AFINIDAD_META_{r}" for r in RECURSOS),
    *(f"CAS_I_{pos}_{r}" for pos,r in CASILLEROS_INFANCIA.items()),
    *(f"CAS_D_F{row}C{col}_{r}" for (row,col),r in CASILLEROS_ADULTOS.items()),
)

def validar_config(config: dict) -> None:
    if config.get("etiqueta") != "EXPERIMENTO_NO_CALIBRADO":
        raise ValueError("El escenario debe identificarse como experimental")
    params = config.get("parametros", {})
    validated = validar_ajustes(cargar_matriz(), params)
    missing = set(PARAMETROS_REQUERIDOS) - set(validated)
    if missing:
        raise ValueError("Parámetros obligatorios ausentes: " + ", ".join(sorted(missing)))
    variants = config.get("variantes", {})
    for key in ("neutral_desde", "neutral_hasta", "limite_afinidad",
                "mano_adulta", "juvenil_cobro", "consentimiento_falso",
                "prioridad_cierre", "numero_casa_reintentos",
                "politica_entrada_utn"):
        if key not in variants:
            raise ValueError(f"Variante explícita requerida: {key}")
    if not (-variants["limite_afinidad"] <= variants["neutral_desde"]
            <= 0 <= variants["neutral_hasta"] <= variants["limite_afinidad"]):
        raise ValueError("Límites de afinidad inválidos")
    if variants["mano_adulta"] not in (3,4):
        raise ValueError("Mano adulta inválida")
    if variants["politica_entrada_utn"] not in ("solo_con_umbral_previo","entrar_aunque_falten"):
        raise ValueError("Política experimental UTN inválida")
    if variants["juvenil_cobro"] not in ("destino", "paso"):
        raise ValueError("Variante de casilleros de Juventud inválida")
    if variants["consentimiento_falso"] not in ("acepta", "rechaza"):
        raise ValueError("Política experimental de consentimiento inválida")
    if variants["prioridad_cierre"] != "orden_de_turnos":
        raise ValueError("Prioridad no implementada: usar orden_de_turnos")
    if type(variants["numero_casa_reintentos"]) is not int or variants["numero_casa_reintentos"] < 0:
        raise ValueError("Número de reintentos inválido")
    situations = config.get("situaciones", {})
    profiles = config.get("perfiles", {})
    for s in ETAPAS:
        for role in ("Clarisa","Lucas"):
            key = s + "_" + role
            if not isinstance(situations.get(key), list) or not situations[key]:
                raise ValueError("Falta mazo de Situación "+key)
            for card in situations[key]:
                if not card.get("id") or any(opt not in card for opt in LETRAS):
                    raise ValueError("Carta incompleta en "+key)
                for opt in LETRAS:
                    for r,n in card[opt].items():
                        if r not in RECURSOS or type(n) is not int:
                            raise ValueError("Efecto inválido en "+key)
    for role in ("Clarisa","Lucas"):
        prof = profiles.get(role)
        if not isinstance(prof, dict) or set(prof)!=set(RECURSOS):
            raise ValueError("Perfil experimental incompleto: "+role)
        if any(type(n) is not int or n<0 for n in prof.values()):
            raise ValueError("Perfil inválido")
    young = config.get("juventud_casilleros", {})
    if not isinstance(young,dict) or set(young)!= {"UNIVERSIDAD","TRAMITE"}:
        raise ValueError("Definición de casilleros juveniles incompleta")
    for place, resources in young.items():
        if not isinstance(resources,list) or len(set(resources))!=len(resources):
            raise ValueError("Recursos juveniles inválidos")
        for r in resources:
            key = f"CAS_J_{place}_{variants['juvenil_cobro'].upper()}_{r}"
            if key not in validated:
                raise ValueError(f"Falta premio juvenil parametrizado {key}")
    if type(config.get("rondas_maximas")) is not int or config["rondas_maximas"]<1:
        raise ValueError("Límite de rondas inválido")


class Mazo:
    def __init__(self, cards, rng):
        self.cards = list(cards)
        if not self.cards:
            raise ValueError("Mazo vacío")
        self.rng = rng
        self.pending = []
        self.ciclos = 0

    def tomar(self):
        if not self.pending:
            self.pending = self.cards.copy()
            self.rng.shuffle(self.pending)
            self.ciclos += 1
        return self.pending.pop()


class SimulacionV3:
    def __init__(self, config, n=6, seed=2001, politica="planificador"):
        validar_config(config)
        if n not in (6,10):
            raise ValueError("Configuración validada solo para 6 o 10 jugadores")
        if politica not in ("planificador","aleatorio"):
            raise ValueError("Política de agente inválida")
        self.config = config
        self.values = config["parametros"]
        self.rules = config["variantes"]
        self.rng = random.Random(seed)
        self.seed, self.n, self.politica = seed,n,politica
        self.ronda = 0
        self.personas = {}
        self.economia = None
        self.eventos = []
        self.propiedad_casa = None
        self.cierre = None
        self.proyectos = {}
        self.secuencia_proyectos = 0
        self.situaciones = {key:Mazo(cards,self.rng)
                            for key,cards in config["situaciones"].items()}
        pairs = [(a,b) for a in range(1,7) for b in range(1,7) if a!=b]
        self.mazo_joven = Mazo(pairs,self.rng)
        self.mazo_adulto = Mazo(pairs,self.rng)
        self._preparar()

    def _log(self, tipo, **data):
        self.eventos.append({"ronda":self.ronda,"tipo":tipo,**data})

    def _preparar(self):
        nroles = self.n//2
        ids = [f"C{i+1}" for i in range(nroles)] + [
            f"L{i+1}" for i in range(nroles)
        ]
        false_id = self.rng.choice(ids[nroles:])
        for pid in ids:
            role = "Clarisa" if pid.startswith("C") else "Lucas"
            resource = self.rng.choice(RECURSOS)
            p = Personaje(id=pid, rol=role, falso=pid==false_id,
                          afinidad_recurso=resource,
                          afinidad_cantidad=self.values[f"AFINIDAD_META_{resource}"])
            self.personas[pid] = p
        self.orden = list(ids)
        self.rng.shuffle(self.orden)
        self.economia = LibroMayor(self.personas)
        # Un solo registro cronológico: asientos y eventos de reglas intercalados.
        self.economia.eventos = self.eventos
        for project_type in ("TITULO","PASAPORTE_C","PASAPORTE_L"):
            self._nuevo_proyecto(project_type)
        self._log("preparacion", jugadores=self.n, politica=self.politica,
                  roles={a:p.rol for a,p in self.personas.items()})
        # Identidad secreta y cartas ocultas NO entran en eventos públicos.

    def _nuevo_proyecto(self,tipo):
        self.secuencia_proyectos += 1
        self.proyectos[tipo] = {
            "id":f"{tipo}-{self.secuencia_proyectos}", "tipo":tipo,
            "siguiente":0, "financiadores":[],
        }

    def _ganar(self,p,r,amount,param,source,**extra):
        if amount:
            self.economia.emitir(self.ronda,source,p.id,r,amount,param)
            self._log("fuente", jugador=p.id, etapa=p.etapa,
                      parametro=param, recurso=r, cantidad=amount, fuente=source,
                      **extra)

    def _pagar(self,p,r,amount,param,why):
        self.economia.consumir(self.ronda,why,p.id,r,amount,param)
        self._log("consumo", jugador=p.id, recurso=r, cantidad=amount,
                  parametro=param, causa=why)

    def _lanzar(self):
        return self.rng.randint(1,6)

    def _zona(self,p):
        if p.zona < self.rules["neutral_desde"]:
            return "A"
        if p.zona > self.rules["neutral_hasta"]:
            return "B"
        return "Neutro"

    def _efecto(self,p,card,choice):
        sig = "IJD"[ETAPAS.index(card["_situation_stage"])]
        role = "C" if card["_situation_role"]=="Clarisa" else "L"
        previous = p.zona
        delta = -1 if choice=="A" else 1
        p.zona = max(-self.rules["limite_afinidad"],
                     min(self.rules["limite_afinidad"],p.zona+delta))
        self._log("situacion", jugador=p.id, carta=card["id"],
                  etapa_asignada=card["_situation_stage"],
                  etapa_actual=p.etapa, opcion=choice,
                  afinidad_antes=previous, afinidad_despues=p.zona)
        for r,amount in card[choice].items():
            if amount>0:
                param=f"SIT_{sig}_{role}_{choice}_{r}_GANANCIA"
                self._ganar(p,r,amount,param,"Situacion",carta=card["id"])
            elif amount<0:
                param=f"SIT_{sig}_{role}_{choice}_{r}_PERDIDA"
                effective=self.economia.perder(self.ronda,p.id,r,-amount,param)
                self._log("perdida", jugador=p.id, carta=card["id"], recurso=r,
                          nominal=-amount, efectiva=effective,parametro=param)
        self._mantener_pareja(p)

    def _elegir_opcion(self,p,card,juvenil_movimiento=None):
        if self.politica=="aleatorio":
            return self.rng.choice(LETRAS)
        need = {"A":1.0, "P":1.1, "K":1.3, "M":1.0}
        if p.etapa=="Infancia":
            need={"A":.25,"P":2.0 if p.libre("P")<self.values["UTN_UMBRAL_P"] else .5,
                  "K":2.4 if p.libre("K")<self.values["UTN_UMBRAL_K"] else .5,"M":.3}
        if p.etapa=="Juventud":
            if not p.titulo:need["K"]=3
            if not p.pasaporte:need["P"]=2;need["M"]=2
            if not p.pareja:need["A"]=2
        if p.etapa=="Adultez":
            if p.falso:need["M"]=4
            elif p.pareja:
                for x in (p, self.personas[p.pareja]):
                    if x.afinidad_revelada:
                        need[x.afinidad_recurso]=2.5
                if not self._casa_suya(p): need["A"]=3;need["P"]=2;need["M"]=3
        scores={}
        for choice in LETRAS:
            scores[choice]=sum(need[r]*n for r,n in card[choice].items())
            if juvenil_movimiento is not None:
                dest = (p.posicion-1+juvenil_movimiento[0 if choice=="A" else 1])%6+1
                if not p.titulo and dest in (1,4):scores[choice]+=2
                if not p.pasaporte and dest in (2,5):scores[choice]+=2
                if p.pareja and self._puede_volar(p):
                    d=juvenil_movimiento[0 if choice=="A" else 1]
                    steps=[(p.posicion-1+j)%6+1 for j in range(1,d+1)]
                    if any(x in (2,5) and i<d-1 for i,x in enumerate(steps)):
                        scores[choice]+=15
        mx=max(scores.values())
        return self.rng.choice([c for c,v in scores.items() if v==mx])

    def _cobrar_perfil(self,p,razon):
        if not p.examen_aprobado:
            return
        for r,n in self.config["perfiles"][p.rol].items():
            self._ganar(p,r,n,f"PERFIL_{'C' if p.rol=='Clarisa' else 'L'}_{r}",
                        "Perfil",activacion=razon)

    def _mover_infancia(self,p):
        roll=self._lanzar()
        if p.posicion=="UTN":
            if p.utm_regreso:
                p.utm_regreso=False
                p.posicion=(5+(roll-1)-1)%6+1
                self._log("regreso_utn",jugador=p.id,dado=roll,destino=p.posicion)
            else:
                return False,roll
        else:
            pos=p.posicion
            travelled=False
            for step in range(1,roll+1):
                current=(pos-1+step)%6+1
                if (current==5 and step<roll
                        and (self.rules["politica_entrada_utn"] == "entrar_aunque_falten"
                             or self._satisface_utn(p))):
                    p.posicion="UTN"
                    travelled=True
                    self._log("llegada_utn",jugador=p.id,dado=roll,pasos=step+1)
                    break
            if not travelled:
                p.posicion=(pos-1+roll)%6+1
        if p.posicion!="UTN":
            r=CASILLEROS_INFANCIA[p.posicion]
            param=f"CAS_I_{p.posicion}_{r}"
            self._ganar(p,r,self.values[param],param,"Casillero",
                        posicion=p.posicion)
        return True,roll

    def _satisface_utn(self,p):
        return all(p.libre(r)>=self.values[f"UTN_UMBRAL_{r}"] for r in ("P","K"))

    def _infancia(self,p,card):
        arrived=p.posicion!="UTN"
        did_move,dice=self._mover_infancia(p)
        if arrived and p.posicion=="UTN":
            self._efecto(p,card,self._elegir_opcion(p,card))
            if not self._satisface_utn(p):
                p.utm_regreso=True
            return
        self._efecto(p,card,self._elegir_opcion(p,card))
        if p.posicion=="UTN":
            if not self._satisface_utn(p):
                p.utm_regreso=True
                self._log("utn_sin_requisitos",jugador=p.id)
            elif not did_move:  # Examen solamente en turno posterior a llegada.
                p.examenes+=1
                rolled=self._lanzar()
                passed=rolled>=4
                self._log("examen_utn",jugador=p.id,dado=rolled,aprobado=passed)
                if passed:
                    p.examen_aprobado=True
                    p.perfil="perfil_"+p.rol
                    p.etapa="Juventud"
                    p.posicion=1
                    self._log("ingreso_juventud",jugador=p.id)
        # Si se regresó al circuito, no se reingresa a UTN en ese turno.

    def _poder_reservar(self,p,resource,value):
        return p.libre(resource)>=value

    def _puede_formar(self,p,other):
        amount=self.values["PAREJA_RESERVA_A"]
        return (p.rol!=other.rol and p.pareja is None and other.pareja is None
                and p.etapa==other.etapa=="Juventud"
                and p.posicion==other.posicion
                and all(self._poder_reservar(z,"A",amount) for z in (p,other)))

    def _buscar_pareja(self,p):
        if p.pareja or p.etapa!="Juventud":
            return
        candidates=[other for other in self.personas.values()
                    if other.id!=p.id and self._puede_formar(p,other)]
        if not candidates:return
        other=self.rng.choice(candidates)
        for z in (p,other):
            self.economia.reservar(self.ronda,z.id,"A",
                                  self.values["PAREJA_RESERVA_A"],
                                  "reserva_pareja","PAREJA_RESERVA_A")
        p.pareja=other.id;other.pareja=p.id
        self._log("pareja_formada",clarisa=p.id if p.rol=="Clarisa" else other.id,
                  lucas=p.id if p.rol=="Lucas" else other.id,
                  politica="aceptacion_automatica_experimental")

    def _casa_suya(self,p):
        return p.pareja is not None and self.propiedad_casa==frozenset(
            (p.id,p.pareja)
        )

    def _perder_casa(self,porque):
        if self.propiedad_casa is None:return
        owners=self.propiedad_casa
        self._log("casa_perdida",propietarios=sorted(owners),causa=porque)
        for pid in owners:
            for r in ("A","P"):
                self.economia.liberar(self.ronda,pid,r,"reserva_casa",
                                     f"CASA_RESERVA_{r}")
        self.propiedad_casa=None

    def _romper(self,p):
        if not p.pareja:return
        other=self.personas[p.pareja]
        if self._casa_suya(p):
            self._perder_casa("ruptura")
        self._log("pareja_rota",jugadores=sorted((p.id,other.id)))
        for z in (p,other):
            self.economia.liberar(self.ronda,z.id,"A","reserva_pareja",
                                  "PAREJA_RESERVA_A")
            z.pareja=None
            if z.etapa=="Adultez":
                z.etapa="Juventud";z.posicion=1;z.mano.clear()
        # Retorno a 1: variante técnica experimental; posición abierta en v3.0.

    def _mantener_pareja(self,p):
        if not p.pareja:return
        other=self.personas[p.pareja]
        req=self.values["PAREJA_RESERVA_A"]
        for z,partner in ((p,other),(other,p)):
            short=max(0,req-z.recursos["A"]["reserva_pareja"])
            if short:
                available=min(partner.libre("A"),short)
                if available:
                    self.economia.asiento(
                        self.ronda,"rescate_pareja","A",available,
                        origen=(partner.id,"libre"),
                        destino=(z.id,"reserva_pareja"),
                        parametro="PAREJA_RESERVA_A"
                    )
                    self._log("rescate_pareja",de=partner.id,a=z.id,cantidad=available)
        if any(z.recursos["A"]["reserva_pareja"]<req for z in (p,other)):
            self._romper(p)
            return
        if self._casa_suya(p):
            for z in (p,other):
                if any(z.recursos[r]["reserva_casa"] < self.values[f"CASA_RESERVA_{r}"]
                       for r in ("A","P")):
                    self._perder_casa("reservas_insuficientes")
                    break

    def _project_type(self,p,which):
        return "TITULO" if which=="TITULO" else (
            "PASAPORTE_C" if p.rol=="Clarisa" else "PASAPORTE_L"
        )

    def _subhitos(self,which):
        if which=="TITULO":
            return [(f"TITULO_SUBHITO_{j}_K","K") for j in (1,2,3)]
        return [("PASAPORTE_SUBHITO_1_P","P"),
                ("PASAPORTE_SUBHITO_2_P","P"),
                ("PASAPORTE_SUBHITO_3_M","M")]

    def _proyectos_turno(self,p,casilla):
        for which,owned,authorized in [
            ("TITULO",p.titulo,casilla in (1,4)),
            ("PASAPORTE",p.pasaporte,casilla in (2,5))
        ]:
            if owned:continue
            ty=self._project_type(p,which)
            proj=self.proyectos[ty]
            parts=self._subhitos(which)
            if proj["siguiente"]<3:
                i=proj["siguiente"]
                param,r=parts[i]
                cost=self.values[param]
                if p.libre(r)>=cost:
                    self.economia.reservar(self.ronda,p.id,r,cost,"invertido",param)
                    proj["financiadores"].append((p.id,r,cost))
                    proj["siguiente"]+=1
                    self._log("subhito_financiado",jugador=p.id,
                              proyecto=proj["id"],subhito=i+1,
                              recurso=r,cantidad=cost,parametro=param)
            if proj["siguiente"]==3 and authorized:
                if not any(x[0]==p.id for x in proj["financiadores"]):
                    continue
                param,resource=(("ADJ_TITULO_PAGO_MIN_K","K")
                    if which=="TITULO" else ("ADJ_PASAPORTE_PAGO_MIN_P","P"))
                payment=self.values[param]
                if p.libre(resource)<payment:continue
                self._pagar(p,resource,payment,param,"adjudicacion")
                dado=self._lanzar()
                # Variante explícita: D6 <= pago, máximo 6.
                won=dado<=min(payment,6)
                self._log("adjudicacion",jugador=p.id,proyecto=proj["id"],
                          dado=dado,pago=payment,lograda=won)
                if won:
                    if which=="TITULO":p.titulo=True
                    else:p.pasaporte=True
                    for owner,resource,amount in proj["financiadores"]:
                        self.economia.asiento(
                            self.ronda,"liquidacion_proyecto",resource,amount,
                            origen=(owner,"invertido"),parametro=param
                        )
                    self._nuevo_proyecto(ty)

    def _puede_volar(self,p):
        if not p.pareja:return False
        other=self.personas[p.pareja]
        if p.etapa!=other.etapa or p.etapa!="Juventud":return False
        return all(
            x.titulo and x.pasaporte
            and x.recursos["A"]["reserva_pareja"] >= self.values["PAREJA_RESERVA_A"]
            and all(x.libre(r)>=self.values[f"DUBLIN_UMBRAL_{r}"] for r in ("K","M"))
            for x in (p,other)
        )

    def _volar(self,p):
        other=self.personas[p.pareja]
        for z in (p,other):
            z.etapa="Adultez";z.posicion=(5,3);z.mano.clear()
            z.afinidad_revelada=True
            if z.falso:z.secreto_revelado=True
            self._log("revelacion_afinidad",jugador=z.id,
                      recurso=z.afinidad_recurso,cantidad=z.afinidad_cantidad)
            if z.falso:self._log("revelacion_falso_lucas",jugador=z.id)
            self._cobrar_perfil(z,"ingreso_desde_dublin")
        self._log("ingreso_adultez",pareja=sorted((p.id,other.id)))

    def _juvenil_casillero(self,p,pos):
        kind="UNIVERSIDAD" if pos in (1,4) else (
            "TRAMITE" if pos in (2,5) else None
        )
        if not kind:return
        for r in self.config["juventud_casilleros"][kind]:
            param=f"CAS_J_{kind}_{self.rules['juvenil_cobro'].upper()}_{r}"
            amount=self.values[param]
            for z in (p, self.personas[p.pareja]) if p.pareja else (p,):
                self._ganar(z,r,amount,param,"Casillero",posicion=pos)

    def _juvenil(self,p,card,mov):
        choice=self._elegir_opcion(p,card,mov)
        self._efecto(p,card,choice)
        if p.etapa!="Juventud":return
        dist=mov[0 if choice=="A" else 1]
        old=p.posicion
        accompany=self.personas[p.pareja] if p.pareja else None
        flyers=self._puede_volar(p)
        completed=0
        for step in range(1,dist+1):
            pos=(old-1+step)%6+1
            if flyers and pos in (2,5) and step<dist:
                self._volar(p)
                self._log("movimiento_juvenil",jugador=p.id,eleccion=choice,
                          carta=list(mov),pasos=step+1,salida="Dublin")
                return
            if pos==1:completed+=1
            if self.rules["juvenil_cobro"]=="paso":
                self._juvenil_casillero(p,pos)
        pos=(old-1+dist)%6+1
        p.posicion=pos
        if accompany:accompany.posicion=pos
        for _ in range(completed):
            for z in (p,accompany) if accompany else (p,):
                self._cobrar_perfil(z,"vuelta_juvenil")
        if self.rules["juvenil_cobro"]=="destino":
            self._juvenil_casillero(p,pos)
        self._log("movimiento_juvenil",jugador=p.id,eleccion=choice,
                  carta=list(mov),desde=old,destino=pos,pasos=dist)
        self._proyectos_turno(p,pos)
        self._buscar_pareja(p)

    def _simular_trayectoria(self,pos,dist,dr,dc):
        x,y=pos
        if not (1<=x+dr<=5 and 1<=y+dc<=5):
            return None
        for _ in range(dist):
            if not 1<=x+dr<=5:dr=-dr
            if not 1<=y+dc<=5:dc=-dc
            x+=dr;y+=dc
        return x,y

    def _puede_casarse(self,p):
        if p.etapa!="Adultez" or not self._casa_suya(p):return False
        other=self.personas[p.pareja]
        if other.etapa!="Adultez" or not all(
            z.titulo and z.pasaporte and z.afinidad_revelada
            for z in (p,other)
        ):return False
        if self._zona(p)!=self._zona(other):return False
        for z in (p,other):
            if z.recursos["A"]["reserva_pareja"]<self.values["PAREJA_RESERVA_A"]:
                return False
            if any(z.recursos[r]["reserva_casa"]<self.values[f"CASA_RESERVA_{r}"]
                   for r in ("A","P")):return False
        goals={}
        for z in (p,other):
            r=z.afinidad_recurso
            goals[r]=max(goals.get(r,0),z.afinidad_cantidad)
        return all(p.libre(r)+other.libre(r)>=amount
                   for r,amount in goals.items())

    def _casarse(self,p):
        # Requiere entrada al nodo desde acceso superior, nunca boda remota.
        if p.etapa!="Adultez" or p.posicion not in ((1,2),(1,3),(1,4)):
            return False
        if not self._puede_casarse(p):return False
        other=self.personas[p.pareja]
        if other.falso and self.rules["consentimiento_falso"]=="rechaza":
            return False
        if p.falso and self.rules["consentimiento_falso"]=="rechaza":
            return False
        goals={}
        for z in (p,other):
            goals[z.afinidad_recurso]=max(
                goals.get(z.afinidad_recurso,0),z.afinidad_cantidad
            )
        for r,amount in goals.items():
            remaining=amount
            for z in (p,other):
                take=min(z.libre(r),remaining)
                if take:self._pagar(z,r,take,f"AFINIDAD_META_{r}","boda")
                remaining-=take
            if remaining:raise EstadoInvalido("Pago de boda no atómico")
        winners=[z.id for z in (p,other) if not z.falso]
        self.cierre={"tipo":"boda_falso_lucas" if other.falso or p.falso
                     else "boda_autentica","ganadores":sorted(winners),
                     "ronda":self.ronda}
        self._log("casamiento",pareja=sorted((p.id,other.id)),
                  ganadores=self.cierre["ganadores"],metas=goals)
        return True

    def _financiacion_casa(self,p,other,precio):
        return all(
            z.libre("M")>=precio and all(
                z.libre(r)>=self.values[f"CASA_RESERVA_{r}"]
                for r in ("A","P")
            ) for z in (p,other)
        )

    def _comprar_casa(self,p):
        if not p.pareja or p.etapa!="Adultez":return
        other=self.personas[p.pareja]
        if other.etapa!="Adultez":return
        owners=frozenset((p.id,other.id))
        if self.propiedad_casa==owners:return
        # Contra propietarios, encuentro en su casillero; con banca, centro.
        oldowners=self.propiedad_casa
        if oldowners is None and p.posicion!=(3,3):return
        if oldowners is not None:
            if not any(p.posicion==self.personas[old].posicion for old in oldowners):
                return
        for index in range(self.rules["numero_casa_reintentos"]+1):
            price=self.values["CASA_OFERTA_BASE_M"]+index*self.values[
                "CASA_OFERTA_INCREMENTO_M"
            ]
            if not self._financiacion_casa(p,other,price):
                break
            buy=self._lanzar()+self._lanzar()
            defend=self._lanzar()+self._lanzar()
            success=buy>defend
            self._log("intento_casa",pareja=sorted(owners),precio=price,
                      dados_comprador=buy,dados_defensor=defend,exito=success,
                      rival="banca" if oldowners is None else sorted(oldowners))
            if success:
                if oldowners is not None:
                    sellers=list(sorted(oldowners))
                    # Pago cada comprador repartido por igual entre vendedores.
                    for z,seller in zip((p,other),sellers):
                        self.economia.transferir(
                            self.ronda,"compra_casa",z.id,seller,
                            "M",price,"CASA_OFERTA_BASE_M"
                        )
                    self._perder_casa("disputa_ganada")
                else:
                    for z in (p,other):
                        self._pagar(z,"M",price,"CASA_OFERTA_BASE_M","compra_casa")
                for z in (p,other):
                    for r in ("A","P"):
                        self.economia.reservar(
                            self.ronda,z.id,r,self.values[f"CASA_RESERVA_{r}"],
                            "reserva_casa",f"CASA_RESERVA_{r}"
                        )
                self.propiedad_casa=owners
                self._log("casa_adquirida",pareja=sorted(owners),
                          precio_por_integrante=price)
                break

    def _movimiento_adulto(self,p,card):
        if not p.mano:
            p.mano=[self.mazo_adulto.tomar()
                    for _ in range(self.rules["mano_adulta"])]
            self._log("mano_adulta_recibida",jugador=p.id,
                      cartas=[list(x) for x in p.mano])
        if (p.posicion[0]==1 and p.posicion[1] in (2,3,4)
                and self._puede_casarse(p) and not p.falso):
            if self._casarse(p):
                used=p.mano.pop(0)
                self._log("movimiento_boda",jugador=p.id,
                          carta=list(used),pasos=1)
                return
        if self.politica=="aleatorio":
            options=[]
            for i,pair in enumerate(p.mano):
                for ix,dist in enumerate(pair):
                    for direction in DIRECCIONES:
                        dest=self._simular_trayectoria(p.posicion,dist,*direction)
                        if dest is not None:options.append((i,ix,dist,direction,dest,0))
            chosen=self.rng.choice(options)
        else:
            options=[]
            target=(3,3) if not self._casa_suya(p) else (
                (1,3) if self._puede_casarse(p) and not p.falso else
                (3,5) if p.falso else (5,3)
            )
            for i,pair in enumerate(p.mano):
                for ix,dist in enumerate(pair):
                    for direction in DIRECCIONES:
                        dest=self._simular_trayectoria(p.posicion,dist,*direction)
                        if dest is None:continue
                        score= -(abs(dest[0]-target[0])+abs(dest[1]-target[1]))
                        if dest in CASILLEROS_ADULTOS:
                            r=CASILLEROS_ADULTOS[dest]
                            if p.falso and r=="M":score+=2
                            else:score+=.5
                        if dest==(5,3):score+=.8
                        if dest==target:score+=5
                        options.append((i,ix,dist,direction,dest,score))
            top=max(x[-1] for x in options)
            chosen=self.rng.choice([x for x in options if x[-1]==top])
        ix,letter_ix,dist,direction,dest,_=chosen
        used=p.mano.pop(ix)
        old=p.posicion
        p.posicion=dest
        other=self.personas[p.pareja] if p.pareja else None
        if other:other.posicion=dest
        self._log("movimiento_adulto",jugador=p.id,desde=list(old),
                  destino=list(dest),carta=list(used),letra=LETRAS[letter_ix],
                  direccion=list(direction),pasos=dist,
                  acompanante=other.id if other else None)
        if dest==(5,3):
            for z in (p,other) if other else (p,):
                self._cobrar_perfil(z,"casillero_perfil_adulto")
        elif dest in CASILLEROS_ADULTOS:
            r=CASILLEROS_ADULTOS[dest]
            param=f"CAS_D_F{dest[0]}C{dest[1]}_{r}"
            for z in (p,other) if other else (p,):
                self._ganar(z,r,self.values[param],param,"Casillero",
                            posicion=list(dest))
        self._comprar_casa(p)

    def _adulto(self,p,card):
        letter=self._elegir_opcion(p,card)
        self._efecto(p,card,letter)
        if p.etapa!="Adultez":return
        self._movimiento_adulto(p,card)
        if p.falso and p.secreto_revelado and self._casa_suya(p) and (
            p.libre("M")>=self.values["FALSO_LUCAS_META_M"]
        ) and self.cierre is None:
            self.cierre={"tipo":"falso_lucas_individual",
                         "ganadores":[p.id],"ronda":self.ronda}
            self._log("victoria_falso_lucas",jugador=p.id,
                      dinero_libre=p.libre("M"),titular_casa=True)

    def jugar(self):
        # Distribuciones públicas de Situación por etapa/rol al principio de ronda.
        rondas_jugador=Counter()
        for t in range(1,self.config["rondas_maximas"]+1):
            self.ronda=t
            start={pid:(p.etapa,p.rol) for pid,p in self.personas.items()}
            assignments={}
            for stage,role in sorted(set(start.values())):
                original=self.situaciones[stage+"_"+role].tomar()
                assignments[(stage,role)]={
                    **original, "_situation_stage":stage,
                    "_situation_role":role
                }
            juvenile_cards={pid:self.mazo_joven.tomar()
                            for pid,(stage,_) in start.items() if stage=="Juventud"}
            self._log("ronda",cartas={
                f"{stage}_{role}":card["id"]
                for (stage,role),card in assignments.items()
            })
            for pid in self.orden:
                p=self.personas[pid]
                # Puede haber cambiado de etapa por turno de su pareja,
                # pero la Situación de la ronda permanece la original.
                origin_stage,origin_role=start[pid]
                card=assignments[(origin_stage,origin_role)]
                rondas_jugador[origin_stage]+=1
                self._log("turno_inicio",jugador=pid,etapa_actual=p.etapa,
                          etapa_carta=origin_stage,carta=card["id"])
                if p.etapa=="Infancia":
                    self._infancia(p,card)
                elif p.etapa=="Juventud":
                    # Si cambió de Infancia a Juventud en la misma ronda:
                    # no tenía movimiento juvenil repartido; no mueve.
                    if pid in juvenile_cards:
                        self._juvenil(p,card,juvenile_cards[pid])
                    else:
                        self._efecto(p,card,self._elegir_opcion(p,card))
                elif p.etapa=="Adultez":
                    self._adulto(p,card)
                self.economia.comprobar()
                if self.cierre:break
            if self.cierre:break
        if self.cierre is None:
            self.cierre={"tipo":"censurada_sin_victoria","ganadores":[],
                         "ronda":self.ronda}
        return {
            "version":"SIMLOG-3.0-EXPERIMENTAL",
            "semilla":self.seed,"jugadores":self.n,"politica":self.politica,
            "rondas":self.ronda,"cierre":self.cierre,
            "exposicion_jugador_ronda":dict(rondas_jugador),
            "emitido":dict(self.economia.total_emitido),
            "consumido":dict(self.economia.total_consumido),
            "saldos_finales":{pid:{r:dict(v) for r,v in p.recursos.items()}
                             for pid,p in self.personas.items()},
            "estadios_finales":{
                pid:{"etapa":p.etapa,"posicion":p.posicion,"rol":p.rol,
                     "pareja":p.pareja,"titulo":p.titulo,
                     "pasaporte":p.pasaporte,
                     "afinidad_revelada":p.afinidad_revelada,
                     "falso_revelado":p.secreto_revelado}
                for pid,p in self.personas.items()
            },
            "eventos":self.eventos,
            "advertencias_modelo":[
                "Importes y cartas sintéticos, no calibrados.",
                "No incluye duelos ordinarios, disputa de hitos, cambios de rol, "
                "cesiones ni negociación estratégica.",
                "El emparejamiento tiene aceptación automática experimental.",
                "Se usa una sola producción de Perfil por rol, no el mercado completo.",
                "Movimiento y conservación de manos en retornos usan variantes explícitas.",
                "El simulador no certifica equilibrio sin validación posterior.",
            ],
        }


def ejecutar_lote(config, partidas=20, n=6, semilla=2001,
                  politica="planificador"):
    """Medir activaciones reales del escenario sintético, sin afirmar balance.

    Para frecuencia de mesa por ronda se divide por rondas en las que hay
    participantes de esa etapa. Para frecuencia individual se divide por
    exposiciones jugador/ronda de la etapa, incluyendo acompañantes.
    Las duraciones de partidas censuradas NO se agregan a las de victoria.
    """
    if type(partidas) is not int or not 1<=partidas<=10000:
        raise ValueError("Cantidad de partidas inválida")
    games=[]
    frequencies=Counter()
    production=Counter()
    loss_nominal=Counter()
    loss_effective=Counter()
    spending=Counter()
    exposure=Counter()
    rounds_stage=Counter()
    winners=Counter()
    by_mechanism = {p["id"]:p["mecanismo"] for p in cargar_matriz()["parametros"]}
    for i in range(partidas):
        g=SimulacionV3(config,n,semilla+i,politica).jugar()
        games.append(g)
        winners[g["cierre"]["tipo"]]+=1
        exposure.update(g["exposicion_jugador_ronda"])
        for e in g["eventos"]:
            if e.get("tipo")=="ronda":
                for stage in ETAPAS:
                    if any(key.startswith(stage+"_") for key in e["cartas"]):
                        rounds_stage[stage]+=1
            elif e.get("tipo")=="fuente":
                key=(e["etapa"],e["parametro"],e["recurso"])
                frequencies[key]+=1
                production[key]+=e["cantidad"]
            elif e.get("tipo")=="perdida":
                key=e["recurso"]
                loss_nominal[key]+=e["nominal"]
                loss_effective[key]+=e["efectiva"]
            elif e.get("tipo")=="consumo":
                spending[e["recurso"]]+=e["cantidad"]
    complete=[g["rondas"] for g in games
              if g["cierre"]["tipo"]!="censurada_sin_victoria"]
    by_stage=defaultdict(lambda:{r:0 for r in RECURSOS})
    by_mechanism_stage=defaultdict(int)
    for (stage,param,r),amount in production.items():
        by_stage[stage][r]+=amount
        by_mechanism_stage[(stage,by_mechanism.get(param,"DESCONOCIDO"),r)]+=amount
    perc={}
    for s in ETAPAS:
        denom=sum(by_stage[s].values())
        perc[s]={r:by_stage[s][r]/denom if denom else None
                 for r in RECURSOS}
    return {
        "status":"EXPERIMENTAL_NO_CALIBRADO",
        "jugadores":n,"cantidad_partidas":partidas,
        "semillas":[semilla,semilla+partidas-1],
        "politica":politica,
        "cierres":dict(winners),
        "partidas_censuradas":winners["censurada_sin_victoria"],
        "partidas_con_victoria":len(complete),
        "rondas_mediana_completadas":(
            statistics.median(complete) if complete else None
        ),
        "rondas_p80_completadas":(
            sorted(complete)[max(0,math.ceil(.8*len(complete))-1)]
            if complete else None
        ),
        "rondas_mediana_observada_con_censura":statistics.median(
            g["rondas"] for g in games
        ),
        "activaciones_observadas":[
            {"etapa":s,"parametro":param,
             "mecanismo":by_mechanism.get(param,"DESCONOCIDO"),
             "recurso":r,
             "activaciones":number,"emision":production[(s,param,r)],
             "exposicion_jugador_ronda":exposure[s],
             "rondas_con_etapa":rounds_stage[s],
             "frecuencia_por_jugador_ronda":(
                number/exposure[s] if exposure[s] else None
             ),
             "activaciones_por_ronda_mesa":(
                number/rounds_stage[s] if rounds_stage[s] else None
             )}
            for (s,param,r),number in sorted(frequencies.items())
        ],
        "generacion_por_etapa":dict(by_stage),
        "distribucion_por_etapa":perc,
        "generacion_por_mecanismo":[
            {"etapa":s,"mecanismo":m,"recurso":r,"cantidad":amount}
            for (s,m,r),amount in sorted(by_mechanism_stage.items())
        ],
        "perdidas_nominales":dict(loss_nominal),
        "perdidas_efectivas":dict(loss_effective),
        "pagos_consumidos":dict(spending),
        "mediciones_por_etapa":dict(exposure),
        "rondas_con_etapa":dict(rounds_stage),
        "partidas":[{k:v for k,v in g.items() if k!="eventos"}
                    for g in games],
        "advertencia":"Frecuencias observadas SOLO bajo escenario sintético y bots. "
                      "Los tiempos de censura no se contabilizan como victorias; "
                      "la mediana de partidas completadas es condicional. "
                      "No son probabilidades ni duraciones calibradas de v3.0 real.",
    }


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config",type=Path,default=EJEMPLO)
    ap.add_argument("--jugadores",type=int,choices=(6,10),default=6)
    ap.add_argument("--partidas",type=int,default=20)
    ap.add_argument("--semilla",type=int,default=2001)
    ap.add_argument("--politica",choices=("planificador","aleatorio"),default="planificador")
    ap.add_argument("--salida",type=Path)
    ap.add_argument("--traza",type=Path,help="Ruta completa de la primera partida")
    args=ap.parse_args(argv)
    config=json.loads(args.config.read_text(encoding="utf-8"))
    report=ejecutar_lote(config,args.partidas,args.jugadores,args.semilla,
                         args.politica)
    out=json.dumps(report,ensure_ascii=False,indent=2)+"\n"
    if args.salida:
        args.salida.parent.mkdir(parents=True,exist_ok=True)
        args.salida.write_text(out,encoding="utf-8")
        print(args.salida)
    else:print(out)
    if args.traza:
        detail=SimulacionV3(config,args.jugadores,args.semilla,
                           args.politica).jugar()
        args.traza.parent.mkdir(parents=True,exist_ok=True)
        args.traza.write_text(
            json.dumps(detail,ensure_ascii=False,indent=2)+"\n",
            encoding="utf-8"
        )


if __name__=="__main__":
    main()
