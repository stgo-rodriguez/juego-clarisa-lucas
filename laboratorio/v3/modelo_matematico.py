"""Motor matemático determinista para el Laboratorio de Balance v3.0.

NO es el simulador. Obtiene presupuestos de flujos, demanda mínima cronológica
de objetivos y propuestas continuas de premios por mecanismo usando frecuencias
explicitas. Los importes y frecuencias no se infieren de v2.x.

Los presupuestos de flujos son valores esperados (no partidas observadas).
Las proyecciones de pérdidas deben usar magnitudes EFECTIVAS medidas, no
pretendidas, cuando el saldo pueda truncar la pérdida.
"""
from __future__ import annotations

from collections import defaultdict
from math import ceil, floor, isfinite
from typing import Mapping, Sequence

from laboratorio.v3.catalogo import CatalogoInvalido, RECURSOS, validar_ajustes

ETAPAS = ("Infancia", "Juventud", "Adultez")
FLUJOS_ECONOMICOS = frozenset((
    "EMISION", "CONSUMO", "INVERSION", "RESERVA",
    "TRANSFERENCIA", "CONSUMO/TRANSFERENCIA",
))
ESTADOS_LIBRES = ("libre", "reserva_pareja", "reserva_casa", "invertido")
ETAPAS_MAP = {"Infancia": 0, "Juventud": 1, "Adultez": 2}


def _catalogo(matriz: Mapping) -> dict:
    return {p["id"]: p for p in matriz["parametros"]}


def _numero_no_negativo(valor, nombre: str) -> float:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise CatalogoInvalido(f"{nombre} debe ser numérico")
    if not isfinite(valor) or valor < 0:
        raise CatalogoInvalido(f"{nombre} debe ser finito y no negativo")
    return float(valor)


def _entero_no_negativo(valor, nombre: str) -> int:
    if isinstance(valor, bool) or not isinstance(valor, int) or valor < 0:
        raise CatalogoInvalido(f"{nombre} debe ser entero no negativo")
    return valor


def _etapa_valida(etapa: str, definicion: Mapping) -> None:
    if etapa not in ETAPAS:
        raise CatalogoInvalido(f"Etapa desconocida: {etapa}")
    vigente = definicion["etapa"]
    if vigente not in (etapa, "Todas") and not (
        vigente == "Juventud/Adultez" and etapa in ("Juventud", "Adultez")
    ):
        raise CatalogoInvalido(
            f"{definicion['id']} no corresponde a la etapa {etapa}"
        )


def proyectar_flujos(
    matriz: Mapping,
    ajustes: Mapping[str, object],
    activaciones: Sequence[Mapping],
) -> dict:
    """G × F por etapa/recurso/mecanismo, con tipología contable separada.

    Una entrada: {parametro, etapa, frecuencia, instancia?}.
    La magnitud puede venir de `ajustes`; o de `importe_instancia` con
    `instancia` obligatoria, para efectos diferenciados de cartas y Perfiles.
    Las frecuencias se expresan por jugador y ronda de la etapa indicada.
    No se suman reservas e inversiones como destrucción de fichas;
    tampoco transferencias como emisión. Conversiones se modelarán con
    eventos de dos piernas en SIMLOG, no en esta proyección agregada.
    """
    validar_ajustes(matriz, ajustes)
    defs = _catalogo(matriz)
    registro = defaultdict(float)
    vistos = set()
    avisos = []
    for e in activaciones:
        key, etapa = e.get("parametro"), e.get("etapa")
        row = defs.get(key)
        if row is None:
            raise CatalogoInvalido(f"Parámetro de activación desconocido: {key}")
        _etapa_valida(etapa, row)
        tipo = row["flujo"]
        if tipo not in FLUJOS_ECONOMICOS:
            raise CatalogoInvalido(
                f"{key} es {tipo}: no es una emisión/egreso activable"
            )
        freq = _numero_no_negativo(e.get("frecuencia"), f"Frecuencia {key}")
        instancia = e.get("instancia")
        if instancia is not None and (
            not isinstance(instancia, str) or not instancia.strip()
        ):
            raise CatalogoInvalido(f"Instancia inválida: {key}")
        unica = (key, etapa, instancia)
        if unica in vistos:
            raise CatalogoInvalido(
                f"Frecuencia duplicada para {key} / {etapa} / {instancia}"
            )
        vistos.add(unica)
        if "importe_instancia" in e:
            if not instancia or row["mecanismo"] not in (
                "Carta de Situación", "Perfil productivo",
            ):
                raise CatalogoInvalido(
                    f"Un importe por instancia requiere carta/Perfil identificable: {key}"
                )
            amount = _entero_no_negativo(
                e["importe_instancia"], f"Importe instancia {key}"
            )
        elif key in ajustes:
            amount = ajustes[key]
        elif freq == 0:
            amount = 0
        else:
            raise CatalogoInvalido(
                f"Falta importe para evento activo {key}; no asumir cero"
            )
        amount = _entero_no_negativo(amount, f"Importe {key}")
        if tipo == "CONSUMO/TRANSFERENCIA":
            destino = e.get("destino")
            if destino not in ("banca", "propietarios"):
                raise CatalogoInvalido(
                    f"{key}: distinguir pago a banca de transferencia a propietarios"
                )
            tipo = "CONSUMO" if destino == "banca" else "TRANSFERENCIA"
        # La pérdida nominal se puede proyectar como límite superior, no efectiva.
        if key.endswith("_PERDIDA") and freq and not e.get("perdida_efectiva"):
            avisos.append(
                f"{key}: pérdida nominal; el consumo efectivo puede ser menor "
                "si el saldo disponible es insuficiente"
            )
        registro[(etapa, row["recurso"], row["mecanismo"], tipo)] += freq * amount
    por_etapa = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
    por_mecanismo = defaultdict(float)
    for (etapa, r, mecanismo, tipo), total in registro.items():
        por_etapa[etapa][r][tipo] += total
        por_mecanismo[(etapa, mecanismo, r, tipo)] += total
    etapas = {}
    for etapa in ETAPAS:
        recursos = {}
        for r in "APKM":
            flows = dict(por_etapa[etapa][r])
            # El cambio de saldo libre no es el cambio de fichas físicas:
            # reservas/inversiones salen de libre pero siguen existiendo.
            liber = (flows.get("EMISION", 0.0)
                     - flows.get("CONSUMO", 0.0)
                     - flows.get("INVERSION", 0.0)
                     - flows.get("RESERVA", 0.0))
            recursos[r] = {
                "flujos": flows,
                "creacion_mesa_neta": (flows.get("EMISION", 0.0)
                                      - flows.get("CONSUMO", 0.0)),
                "delta_libre_sin_transferencias": liber,
                "volumen_redistribuido": flows.get("TRANSFERENCIA", 0.0),
            }
        emit = sum(recursos[r]["flujos"].get("EMISION", 0.0) for r in "APKM")
        for r in "APKM":
            recursos[r]["participacion_emision"] = (
                recursos[r]["flujos"].get("EMISION", 0.0)/emit if emit else None
            )
        etapas[etapa] = {"recursos": recursos, "emision_total": emit}
    return {
        "unidades": "fichas esperadas por jugador y ronda de cada etapa",
        "etapas": etapas,
        "mecanismos": [
            {"etapa": s, "mecanismo": m, "recurso": r, "flujo": f, "cantidad": q}
            for (s, m, r, f), q in sorted(por_mecanismo.items())
        ],
        "advertencias": avisos,
    }


def calibrar_emisiones(
    matriz: Mapping,
    objetivos: Mapping[str, Mapping[str, object]],
    fuentes: Sequence[Mapping],
    *,
    tolerancia: float = 1e-8,
) -> dict:
    """Cálculo inverso de premios promedio por activación.

    objetivos = {etapa: {recurso: cantidad_por_jugador_y_ronda}}
    fuentes = [{parametro, etapa, frecuencia, cuota, instancia?}, ...]
    Para cada etapa/recurso, las cuotas deben sumar 1. Si hay meta
    positiva, cada fuente con cuota positiva debe tener frecuencia >0.
    Devuelve cantidades continuas y vecinos enteros, NO redondea
    silenciosamente ni afirma que el resultado entero sea óptimo.
    """
    catalogo = _catalogo(matriz)
    objetivos_norm = {}
    for etapa, resources in objetivos.items():
        if etapa not in ETAPAS:
            raise CatalogoInvalido(f"Etapa desconocida: {etapa}")
        if set(resources) != set(RECURSOS):
            raise CatalogoInvalido(
                f"Objetivo {etapa}: deben informarse A, P, K y M"
            )
        for r, target in resources.items():
            objetivos_norm[(etapa, r)] = _numero_no_negativo(
                target, f"Objetivo de producción {etapa}/{r}"
            )
    grouped = defaultdict(list)
    vistas = set()
    for source in fuentes:
        key, etapa = source.get("parametro"), source.get("etapa")
        row = catalogo.get(key)
        if row is None or row["flujo"] != "EMISION":
            raise CatalogoInvalido(f"La fuente no corresponde a EMISION: {key}")
        _etapa_valida(etapa, row)
        if (etapa, row["recurso"]) not in objetivos_norm:
            raise CatalogoInvalido(f"Fuente sin objetivo: {key} {etapa}")
        freq = _numero_no_negativo(source.get("frecuencia"), f"Frecuencia {key}")
        cuota = _numero_no_negativo(source.get("cuota"), f"Cuota {key}")
        if cuota > 1:
            raise CatalogoInvalido(f"Cuota mayor a 1: {key}")
        instancia = source.get("instancia")
        if instancia is not None and (not isinstance(instancia, str) or not instancia.strip()):
            raise CatalogoInvalido(f"Instancia inválida: {key}")
        if row["mecanismo"] in ("Carta de Situación", "Perfil productivo") and not instancia:
            raise CatalogoInvalido(
                f"{key}: identificar carta/Perfil para calibrar individualmente"
            )
        identity = (key, etapa, instancia)
        if identity in vistas:
            raise CatalogoInvalido(f"Fuente duplicada: {identity}")
        vistas.add(identity)
        grouped[(etapa, row["recurso"])].append(
            (key, etapa, instancia, freq, cuota, row)
        )
    suggestions = []
    for (etapa, recurso), objective in objetivos_norm.items():
        g = grouped[(etapa, recurso)]
        share = sum(item[4] for item in g)
        if objective > 0 and abs(share - 1) > tolerancia:
            raise CatalogoInvalido(
                f"Cuotas de {etapa}/{recurso} suman {share}, no 1"
            )
        if objective == 0 and share > tolerancia:
            raise CatalogoInvalido(
                f"{etapa}/{recurso}: cuotas positivas para emisión objetivo cero"
            )
        for key, s, instancia, freq, cuota, row in g:
            if quota := (cuota > 0 and freq == 0):
                raise CatalogoInvalido(
                    f"{key}: cuota positiva sin frecuencia de activación"
                )
            per_use = objective * cuota / freq if freq else 0.0
            suggestions.append({
                "parametro": key, "instancia": instancia,
                "etapa": etapa, "recurso": recurso,
                "mecanismo": row["mecanismo"],
                "frecuencia": freq, "cuota": cuota,
                "emision_por_ronda": objective * cuota,
                "importe_medio_activacion": per_use,
                "entero_inferior": floor(per_use),
                "entero_superior": ceil(per_use),
                "ajuste_requiere_distribucion_de_premios": (
                    abs(per_use - round(per_use)) > tolerancia
                ),
            })
    return {
        "tipo": "solucion_continua_de_reparto; NO es óptimo entero validado",
        "objetivos": {s: {r: objetivos_norm[(s, r)] for r in "APKM"}
                      for s in objetivos},
        "recomendaciones": suggestions,
    }


def combinar_metas_afinidad(
    cartas: Sequence[Mapping],
    *,
    politica_coincidencia: str = "mismo_importe",
) -> dict[str, int]:
    """Una meta si coincide recurso, dos si son diferentes.

    No presume qué hacer con dos cartas del mismo recurso y distintas
    cantidades: exige una política de experimento explícita.
    """
    if len(cartas) != 2:
        raise CatalogoInvalido("La pareja debe tener dos Cartas de Afinidad")
    for c in cartas:
        if c.get("recurso") not in RECURSOS:
            raise CatalogoInvalido("Carta de Afinidad con recurso inválido")
        _entero_no_negativo(c.get("cantidad"), "Meta de Afinidad")
    left, right = cartas
    if left["recurso"] != right["recurso"]:
        return {c["recurso"]: c["cantidad"] for c in cartas}
    if left["cantidad"] == right["cantidad"]:
        return {left["recurso"]: left["cantidad"]}
    if politica_coincidencia == "maximo_experimental":
        return {left["recurso"]: max(left["cantidad"], right["cantidad"])}
    raise CatalogoInvalido(
        "Cartas del mismo recurso con distinto importe: regla ABIERTA; "
        "se requiere política experimental maximo_experimental"
    )


def calcular_demanda_secuencial(
    matriz: Mapping,
    ajustes: Mapping[str, object],
    participantes: Sequence[str],
    eventos: Sequence[Mapping],
    *,
    saldos_iniciales: Mapping[str, Mapping[str, int]] | None = None,
) -> dict:
    """Cota inferior de emisiones justo-a-tiempo para una RUTA EXPLICITA.

    Cada evento tiene: {etapa, hito, parametro, actores:[...],
    por_integrante:bool?, veces:int?, modo_objetivo:"pago"|"comprobacion"?}.
    Los costes se aplican a cada integrante cuando se indique expresamente;
    en otro caso las fichas libres de actores se consideran fungibles entre
    ellos (*cooperación y transferencias autorizadas idealizadas*).
    No modela azar, secuencia de movimiento, disputas, pérdidas futuras ni
    dinámica real de acuerdos; NO es probabilidad de completar una victoria.

    Los requisitos verifican fichas libres sin consumirlas, las reservas y
    las inversiones dejan de estar libres; el objetivo Afinidad en modalidad
    B se paga al cierre. Falso Lucas puede comprobar su M individual con
    `modo_objetivo="comprobacion"`.
    """
    amounts = validar_ajustes(matriz, ajustes)
    definitions = _catalogo(matriz)
    actores = list(participantes)
    if not actores or len(set(actores)) != len(actores) or any(
        not isinstance(a, str) or not a for a in actores
    ):
        raise CatalogoInvalido("Identificadores de participantes inválidos")
    estado = {a: {r: {k: 0 for k in ESTADOS_LIBRES} for r in "APKM"} for a in actores}
    for a, initial in (saldos_iniciales or {}).items():
        if a not in estado:
            raise CatalogoInvalido(f"Participante desconocido: {a}")
        for r, amount in initial.items():
            if r not in RECURSOS:
                raise CatalogoInvalido(f"Saldo inicial desconocido: {r}")
            estado[a][r]["libre"] = _entero_no_negativo(amount, f"Saldo {a}/{r}")
    additions = defaultdict(int)
    trail = []
    last_stage = -1
    for event in eventos:
        key, stage = event.get("parametro"), event.get("etapa")
        row = definitions.get(key)
        if row is None:
            raise CatalogoInvalido(f"Parámetro de objetivo no registrado: {key}")
        _etapa_valida(stage, row)
        if ETAPAS_MAP[stage] < last_stage:
            raise CatalogoInvalido(f"Eventos fuera de orden de etapas: {key}")
        last_stage = ETAPAS_MAP[stage]
        if key not in amounts:
            raise CatalogoInvalido(f"Falta importe objetivo: {key}")
        if row["flujo"] not in ("REQUISITO", "RESERVA",
                               "CONSUMO", "INVERSION", "OBJETIVO"):
            raise CatalogoInvalido(
                f"{key}: no admite flujo {row['flujo']} en demanda"
            )
        involved = event.get("actores")
        if (not isinstance(involved, list) or not involved
                or len(set(involved)) != len(involved)
                or any(a not in estado for a in involved)):
            raise CatalogoInvalido(f"Actores de evento inválidos: {key}")
        individual = event.get("por_integrante", False)
        if not isinstance(individual, bool):
            raise CatalogoInvalido(f"por_integrante no es booleano: {key}")
        count = event.get("veces", 1)
        if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
            raise CatalogoInvalido(f"veces debe ser entero positivo: {key}")
        kind = row["flujo"]
        modo = event.get("modo_objetivo")
        if kind == "OBJETIVO" and modo not in ("pago", "comprobacion"):
            raise CatalogoInvalido(f"{key}: objetivo requiere modo explícito")
        if kind != "OBJETIVO" and modo is not None:
            raise CatalogoInvalido(f"{key}: modo_objetivo no aplicable")
        r, amount = row["recurso"], amounts[key] * count
        if not amount:
            trail.append({"etapa": stage, "hito": event.get("hito", ""),
                          "parametro": key, "demanda_adicional": 0})
            continue
        grupos = [[a] for a in involved] if individual else [involved]
        step_deficit = 0
        for group in grupos:
            stock = sum(estado[a][r]["libre"] for a in group)
            missing = max(0, amount - stock)
            if missing:
                # Con demanda conjunta, asignación en el primer actor es
                # convención contable: no implica transferencias automáticas.
                account = group[0]
                estado[account][r]["libre"] += missing
                additions[(stage, account, r)] += missing
                step_deficit += missing
            if kind == "REQUISITO" or (kind == "OBJETIVO" and modo == "comprobacion"):
                continue
            remaining = amount
            for a in group:
                used = min(remaining, estado[a][r]["libre"])
                estado[a][r]["libre"] -= used
                dest = ("reserva_pareja" if key == "PAREJA_RESERVA_A"
                        else "reserva_casa" if key.startswith("CASA_RESERVA_")
                        else "invertido" if kind == "INVERSION" else None)
                if dest is not None:
                    estado[a][r][dest] += used
                remaining -= used
            if remaining:
                raise AssertionError("Balance interno de demanda inconsistente")
        trail.append({
            "etapa": stage, "hito": event.get("hito", key),
            "parametro": key, "recurso": r, "cantidad": amount,
            "actores": involved, "por_integrante": individual,
            "demanda_adicional": step_deficit,
            "tipo": kind, "modo_objetivo": modo,
        })
    grouped = defaultdict(lambda: defaultdict(int))
    for (stage, _actor, r), amount in additions.items():
        grouped[stage][r] += amount
    return {
        "tipo": "COTA_INFERIOR_OPTIMISTA; inyeccion justo-a-tiempo; no simulacion",
        "produccion_minima_por_etapa": {
            s: {r: grouped[s][r] for r in "APKM"} for s in ETAPAS
        },
        "produccion_minima_total": {
            r: sum(grouped[s][r] for s in ETAPAS) for r in "APKM"
        },
        "aporte_minimo_por_jugador": [
            {"etapa": s, "jugador": a, "recurso": r, "cantidad": amount}
            for (s, a, r), amount in sorted(additions.items())
        ],
        "traza": trail,
        "estado_final": estado,
    }
