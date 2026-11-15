"""Ecualizador v3.1: tiempo esperado de aprobación UTN sin Monte Carlo.

Modelo de decisión de Markov absorbente (MDP) en estados
posición × P libre × K libre, más nodo UTN/examen y regreso obligatorio.
La política elige, tras ver D6, si entrar o continuar para minimizar E[turnos].
Los efectos P/K de Situación son IID según probabilidades introducidas;
esto es una aproximación declarada si el mazo finito tiene dependencia.
"""
from __future__ import annotations
import math

def analizar_infancia_utn(config: dict, **override) -> dict:
    opts={**config.get("supuestos", {}).get("utn_v31", {}),**override}
    rol=opts.get("rol", "Clarisa")
    posicion=opts.get("posicion_inicial")
    P0=opts.get("P_inicial")
    K0=opts.get("K_inicial")
    modo=opts.get("modo_situaciones","configuradas")
    target=opts.get("objetivo_rondas", 5)
    rp=config.get("requisitos",{}).get("utn",{}).get("P")
    rk=config.get("requisitos",{}).get("utn",{}).get("K")
    faltan=[]
    def entero(x):
        return type(x) in (int,float) and float(x).is_integer() and x>=0 and math.isfinite(x)
    if rol not in ("Clarisa","Lucas"):
        faltan.append("Rol Clarisa o Lucas")
    if posicion is None or not entero(posicion):
        faltan.append("Casillero inicial de Infancia (1–6)")
    elif posicion not in (1,2,3,4,5,6):
        faltan.append("Casillero inicial de Infancia (1–6)")
    for nombre,valor in (("P requerida",rp),("K requerido",rk),("P inicial",P0),("K inicial",K0)):
        if (nombre=="P inicial" and rp==0) or (nombre=="K inicial" and rk==0):
            continue
        if valor is None:
            faltan.append(nombre)
        elif not entero(valor):
            faltan.append(nombre+" (entero no negativo)")
    if modo not in ("configuradas","neutras"):
        faltan.append("Modo de Situaciones válido")
    if faltan:
        return {"estado":"pendiente","faltan":faltan,"objetivo_rondas":target}
    P0=0 if rp==0 else P0
    K0=0 if rk==0 else K0
    rp,rk,P0,K0=int(rp),int(rk),int(P0),int(K0)
    cells=(rp+1)*(rk+1)
    if cells>625:
        return {"estado":"limite","detalle":"El espacio P×K supera 625 estados por posición.","estados":cells}
    cas=[]
    for i in range(1,7):
        m=next((x for x in config["etapas"]["infancia"]["mecanismos"] if x["id"]==f"i_c{i}"),None)
        if m is None:
            faltan.append(f"Casillero {i}")
            continue
        p=0 if rp==0 else m.get("premios",{}).get("P",0)
        k=0 if rk==0 else m.get("premios",{}).get("K",0)
        if (rp>0 and p is None) or (rk>0 and k is None):
            faltan.append(f"Premio P/K del casillero {i}")
        elif not isinstance(p,int) or not isinstance(k,int):
            faltan.append(f"Premios P/K enteros del casillero {i}")
        cas.append({"P":p,"K":k})
    outcomes=[]
    if modo=="neutras":
        outcomes=[{"prob":1,"P":0,"K":0}]
    else:
        situ=next((x for x in config["etapas"]["infancia"]["mecanismos"]
                   if x["id"]==("i_s_c" if rol=="Clarisa" else "i_s_l")),None)
        if situ is None:
            faltan.append("Situación de "+rol)
        else:
            a={"P":0 if rp==0 else situ["opcion_A"].get("P"),"K":0 if rk==0 else situ["opcion_A"].get("K")}
            b={"P":0 if rp==0 else situ["opcion_B"].get("P"),"K":0 if rk==0 else situ["opcion_B"].get("K")}
            q=situ["probabilidad_A"]
            same=all(v is not None for v in (*a.values(),*b.values())) and a==b
            if same:
                outcomes=[{"prob":1,**a}]
            elif q is None or not isinstance(q,(int,float)) or not 0<=q<=1:
                faltan.append("Probabilidad A de Situación "+rol)
            else:
                for prob,v,nombre in ((q,a,"A"),(1-q,b,"B")):
                    if prob>0:
                        if any(z is None for z in v.values()):
                            faltan.append("Efectos P/K de la opción "+nombre+" · "+rol)
                        else:
                            outcomes.append({"prob":prob,**v})
    if any(not isinstance(x["P"],int) or not isinstance(x["K"],int) for x in outcomes):
        faltan.append("Efectos P/K enteros de Situación")
    if faltan:
        return {"estado":"pendiente","faltan":list(dict.fromkeys(faltan)),"objetivo_rondas":target}
    has_loss=any((rp>0 and v["P"]<0) or (rk>0 and v["K"]<0)
                 for v in [*cas,*outcomes])
    if has_loss:
        return {
            "estado":"limite","rol":rol,"objetivo_rondas":target,
            "detalle":"Existen efectos P/K negativos. El modelo v3.1 no trunca excedentes bajo pérdidas: se requiere solver ampliado."
        }
    if (rp>P0 and max([c["P"] for c in cas]+[o["P"] for o in outcomes])<=0) or (
        rk>K0 and max([c["K"] for c in cas]+[o["K"] for o in outcomes])<=0):
        return {
            "estado":"inalcanzable","rondas_esperadas":math.inf,"rol":rol,
            "detalle":"Al menos un recurso requerido presenta déficit sin fuente positiva.",
            "objetivo_rondas":target
        }
    W=rk+1
    S=cells
    O=len(outcomes)
    def idx(state,deltaP,deltaK):
        P=state//W
        K=state%W
        return min(rp,max(0,P+deltaP))*W+min(rk,max(0,K+deltaK))
    success=[[0]*O for _ in range(S)]
    passes=[[False]*O for _ in range(S)]
    land=[[[0]*O for _ in range(S)] for _ in range(6)]
    for state in range(S):
        for s,outcome in enumerate(outcomes):
            nxt=idx(state,outcome["P"],outcome["K"])
            success[state][s]=nxt
            passes[state][s]=(nxt//W>=rp and nxt%W>=rk)
            for dest in range(6):
                land[dest][state][s]=idx(state,cas[dest]["P"]+outcome["P"],
                                         cas[dest]["K"]+outcome["K"])
    C=[[0.0]*S for _ in range(6)]
    U=[0.0]*S
    R=[0.0]*S
    tol=opts.get("tolerancia",1e-9)
    max_iterations=opts.get("max_iteraciones",1500)
    err=math.inf
    iterations=0
    for iteration in range(max_iterations):
        err=0
        for state in range(S-1,-1,-1):
            exam=1.
            back=1.
            entering=0.
            for s,outcome in enumerate(outcomes):
                ns=success[state][s]
                w=outcome["prob"]
                exam+=w*(.5*U[ns] if passes[state][s] else R[ns])
                back+=w*C[4][ns]
                entering+=w*(U[ns] if passes[state][s] else R[ns])
            err=max(err,abs(exam-U[state]),abs(back-R[state]))
            U[state],R[state]=exam,back
            for pos in range(6):
                dist=(4-pos+6)%6
                values=0.
                for die in range(1,7):
                    dest=(pos+die)%6
                    stay=sum(outcome["prob"]*C[dest][land[dest][state][s]]
                             for s,outcome in enumerate(outcomes))
                    values+=min(stay,entering) if die>=dist+1 else stay
                val=1+values/6
                err=max(err,abs(val-C[pos][state]))
                C[pos][state]=val
        iterations=iteration+1
        if err<tol:
            break
    if err>=tol:
        return {
            "estado":"no_convergente","rol":rol,"iteraciones":iterations,"residuo":err,
            "objetivo_rondas":target,
            "detalle":"Bellman no alcanzó la tolerancia. Posible demora elevada o estados sin acceso garantizado."
        }
    expected=C[int(posicion)-1][min(P0,rp)*W+min(K0,rk)]
    return {
        "estado":"calculado","rondas_esperadas":expected,"rol":rol,
        "objetivo_rondas":target,"desviacion":expected-target,
        "posicion_inicial":int(posicion),"requisitos":{"P":rp,"K":rk},
        "iniciales":{"P":P0,"K":K0},
        "estados":8*S,"iteraciones":iterations,"residuo":err,
        "modelo":"MDP absorbente finito; valor esperado óptimo; Bellman; sin Monte Carlo",
        "hipotesis":[
            "D6 uniforme; solo el destino final del circuito entrega premio.",
            "Ingresar a UTN desde casillero 5 consume un paso y descarta los restantes.",
            "El jugador optimiza cuándo ingresar tras ver D6, antes de Situación.",
            "Situación al final de cada turno, incluido examen y regreso obligatorio.",
            "La primera tirada de examen es al turno siguiente; P(aprobación)=1/2.",
            "Sin requisitos después de Situación en UTN, se vuelve al casillero 5 el siguiente turno sin D6 ni premio.",
            "Solo se modelan efectos P/K no negativos; las pérdidas y excedentes bajo riesgo requieren otro solver.",
            "Situaciones P/K neutralizadas solo como hipótesis explícita." if modo=="neutras" else
            "Efectos A/B IID por turno; no se modela el orden del mazo finito.",
        ],
    }
