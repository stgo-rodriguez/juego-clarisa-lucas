"""Clarisa & Lucas v3.0 — ecualizador matemático, sin partidas ni Monte Carlo.

Uso:
    python laboratorio/v3/modelo_matematico.py laboratorio/v3/matriz_economica_v3.json

Los importes None representan parámetros a definir; no se convierten a cero.
Las duraciones producidas son cotas económicas optimistas, nunca p80 ni pronósticos
de duración total del juego.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

RECURSOS = ("A", "P", "K", "M")
ROLES = ("Clarisa", "Lucas")
ETAPAS = ("infancia", "juventud", "adultez")


def _cero() -> dict[str, float]:
    return {k: 0.0 for k in RECURSOS}


def _inicial() -> dict[str, dict[str, float]]:
    return {rol: _cero() for rol in ROLES}


def _val(obj: dict | None, key: str) -> float | None:
    return (obj or {}).get(key, 0.0)


def _sum(a: float | None, b: float | None) -> float | None:
    return None if a is None or b is None else a + b


def _mul(a: float | None, b: float | None) -> float | None:
    return None if a is None or b is None else a * b


def _sumar_vectores(vectores: list[dict]) -> dict:
    return {k: _acumular([_val(v, k) for v in vectores]) for k in RECURSOS}


def _acumular(numeros) -> float | None:
    res = 0.0
    for n in numeros:
        res = _sum(res, n)
    return res


def _primera_llegada(restricciones: list[tuple]) -> float | None:
    """Cota max(deficit/tasa). None para faltantes, inf para imposible.

    No es el tiempo esperado de primera llegada de una caminata aleatoria.
    """
    demora, faltan = 0.0, False
    for need, have, rate in restricciones:
        if need is None or have is None or rate is None:
            faltan = True
            continue
        deficit = max(0.0, need - have)
        if deficit > 1e-9 and rate <= 0:
            return math.inf
        if deficit > 1e-9:
            demora = max(demora, deficit / rate)
    return None if faltan else demora


def _cond_por_persona(requisitos: dict, saldo: dict, tasa: dict) -> list[tuple]:
    return [
        (_val(requisitos, k), saldo[rol][k], tasa[rol][k])
        for rol in ROLES for k in RECURSOS
    ]


def _crecer(saldo: dict, tasa: dict, rondas: float | None) -> dict:
    out = _inicial()
    for rol in ROLES:
        for k in RECURSOS:
            a, b = saldo[rol][k], tasa[rol][k]
            out[rol][k] = (
                None if rondas is None or not math.isfinite(rondas)
                or a is None or b is None else a + rondas * b
            )
    return out


def _debitar(saldo: dict, cargo: dict) -> dict:
    out = _inicial()
    for rol in ROLES:
        for k in RECURSOS:
            a, b = saldo[rol][k], _val(cargo, k)
            out[rol][k] = None if a is None or b is None else a - b
    return out


def _pareja(saldo: dict, recurso: str) -> float | None:
    return _sum(saldo["Clarisa"][recurso], saldo["Lucas"][recurso])


def _acumular_duracion(*partes: float | None) -> float | None:
    if math.inf in partes:
        return math.inf
    if any(x is None for x in partes):
        return None
    return sum(partes)


def evaluar(config: dict[str, Any]) -> dict[str, Any]:
    """Evalúa una configuración sin aleatoriedad y sin mutarla."""
    sp, req = config["supuestos"], config["requisitos"]
    flujos, desglose, pendientes = {}, {}, []

    for etapa in ETAPAS:
        flujos[etapa], desglose[etapa] = {}, {}
        for rol in ROLES:
            total, eventos = _cero(), {}
            for m in config["etapas"][etapa]["mecanismos"]:
                if m["rol"] not in ("ambos", rol):
                    continue
                if m.get("variante") and m["variante"] != sp["variante_juvenil"]:
                    continue

                f = m["frecuencia"]
                if m["tipo"] == "casillero" and etapa != "infancia":
                    f = _mul(f, sp.get("multiplicador_destinos_en_pareja_" + etapa))
                emitir = _cero()
                for recurso in RECURSOS:
                    premio = _val(m.get("premios"), recurso)
                    if m["tipo"] == "situacion":
                        a = _val(m["opcion_A"], recurso)
                        b = _val(m["opcion_B"], recurso)
                        p = m["probabilidad_A"]
                        premio = (
                            a if a is not None and b is not None and a == b
                            else None if p is None or a is None or b is None
                            else p * a + (1 - p) * b
                        )
                    emitir[recurso] = 0.0 if f == 0 or premio == 0 else _mul(f, premio)
                    total[recurso] = _sum(total[recurso], emitir[recurso])
                    if emitir[recurso] is None:
                        pendientes.append(f"{etapa} / {rol} / {m['nombre']} / {recurso}")
                eventos[m["id"]] = emitir
            flujos[etapa][rol] = total
            desglose[etapa][rol] = eventos

    titulo = _sumar_vectores([*req["titulo"], req["adjudicacion_titulo"]])
    pasaporte = _sumar_vectores([*req["pasaporte"], req["adjudicacion_pasaporte"]])
    infancia = _primera_llegada(
        _cond_por_persona(req["utn"], _inicial(), flujos["infancia"])
    )
    saldo_i = _crecer(_inicial(), flujos["infancia"], infancia)

    titulo_t = _primera_llegada(
        _cond_por_persona(titulo, saldo_i, flujos["juventud"])
    )
    pasaporte_t = _primera_llegada(
        _cond_por_persona(pasaporte, saldo_i, flujos["juventud"])
    )
    juveniles_gastos = _sumar_vectores([titulo, pasaporte, req["pareja"]])
    juvenil_necesidad = _sumar_vectores([juveniles_gastos, req["vuelo"]])
    juventud = _primera_llegada(
        _cond_por_persona(juvenil_necesidad, saldo_i, flujos["juventud"])
    )
    saldo_j = _debitar(
        _crecer(saldo_i, flujos["juventud"], juventud), juveniles_gastos
    )

    # Colocación inicial en "Cobrar Perfil": una activación por integrante.
    saldo_adulto = _inicial()
    for rol in ROLES:
        perfil_id = "a_perfil_c" if rol == "Clarisa" else "a_perfil_l"
        perfil = next((m for m in config["etapas"]["adultez"]["mecanismos"]
                       if m["id"] == perfil_id), None)
        for recurso in RECURSOS:
            saldo_adulto[rol][recurso] = _sum(
                saldo_j[rol][recurso],
                _val(perfil.get("premios") if perfil else {}, recurso)
            )

    casa = req["casa"]
    restricciones_casa = [
        (
            _val(casa["reserva_individual"], k),
            saldo_adulto[rol][k],
            flujos["adultez"][rol][k],
        )
        for rol in ROLES for k in ("A", "P")
    ]
    fraccion = sp["fraccion_precio_casa_lucas"]
    precio = casa["precio_M"]
    if fraccion is None:
        restricciones_casa.append(
            (precio, _pareja(saldo_adulto, "M"), _pareja(flujos["adultez"], "M"))
        )
    else:
        restricciones_casa.extend([
            (None if precio is None else precio * (1 - fraccion),
             saldo_adulto["Clarisa"]["M"], flujos["adultez"]["Clarisa"]["M"]),
            (None if precio is None else precio * fraccion,
             saldo_adulto["Lucas"]["M"], flujos["adultez"]["Lucas"]["M"])
        ])
    casa_t = _primera_llegada(restricciones_casa)
    saldo_c = _debitar(
        _crecer(saldo_adulto, flujos["adultez"], casa_t), casa["reserva_individual"]
    )
    if fraccion is None or precio is None:
        saldo_c["Clarisa"]["M"] = None
        saldo_c["Lucas"]["M"] = None
    else:
        if saldo_c["Clarisa"]["M"] is not None:
            saldo_c["Clarisa"]["M"] -= precio * (1 - fraccion)
        if saldo_c["Lucas"]["M"] is not None:
            saldo_c["Lucas"]["M"] -= precio * fraccion

    ca, la = sp["afinidad_clarisa"], sp["afinidad_lucas"]
    afinidad = {
        k: _val(req["afinidad"], k) if k in (ca, la) else 0.0
        for k in RECURSOS
    }
    boda_t = _primera_llegada([
        (afinidad[k], _pareja(saldo_c, k), _pareja(flujos["adultez"], k))
        for k in RECURSOS
    ])
    falso_t = _primera_llegada([
        (
            req["falso_lucas_M"],
            saldo_c["Lucas"]["M"],
            flujos["adultez"]["Lucas"]["M"],
        )
    ])
    resultados = {
        "utn": infancia,
        "titulo": _acumular_duracion(infancia, titulo_t),
        "pasaporte": _acumular_duracion(infancia, pasaporte_t),
        "dublin": _acumular_duracion(infancia, juventud),
        "casa": _acumular_duracion(infancia, juventud, casa_t),
        "boda_autentica": _acumular_duracion(infancia, juventud, casa_t, boda_t),
        "boda_con_falso": _acumular_duracion(infancia, juventud, casa_t, boda_t),
        "falso_lucas": _acumular_duracion(infancia, juventud, casa_t, falso_t),
    }

    cuellos = []
    for rol in ROLES:
        for k in RECURSOS:
            t = _primera_llegada([
                (juvenil_necesidad[k], saldo_i[rol][k], flujos["juventud"][rol][k])
            ])
            if t is not None:
                cuellos.append(dict(etapa="Juventud", rol=rol, recurso=k, rondas=t))
    for k in RECURSOS:
        if afinidad[k] == 0:
            continue
        t = _primera_llegada([
            (afinidad[k], _pareja(saldo_c, k), _pareja(flujos["adultez"], k))
        ])
        if t is not None:
            cuellos.append(dict(etapa="Adultez · afinidad", rol="Pareja", recurso=k, rondas=t))
    cuellos.sort(key=lambda x: x["rondas"], reverse=True)
    avisos = []
    if sp["regla_afinidad"] != "pago":
        avisos.append("Solo se calcula pago terminal de afinidad; otras variantes están abiertas.")
    if fraccion is not None and not 0 <= fraccion <= 1:
        avisos.append("La fracción de Casa pagada por Lucas debe estar entre 0 y 1.")
    for etapa in ETAPAS:
        for rol in ROLES:
            for k in RECURSOS:
                valor = flujos[etapa][rol][k]
                if valor is not None and valor < 0:
                    avisos.append(
                        f"Tasa neta negativa {etapa}/{rol}/{k}: pérdidas requieren topes por saldo."
                    )
    if any(x is None for x in resultados.values()):
        avisos.append("Resultados N/D: hay importes o frecuencias que no están definidos.")
    avisos.append(
        "Cotas económicas optimistas. No incorporan tiempos de ubicación, examen,"
        " adjudicación, compatibilidad, consentimiento, disputa ni política de decisiones."
    )
    avisos.append(
        "Boda con Falso Lucas: el cómputo supone cooperación hipotética, no consentimiento."
    )
    return {
        "flujos": flujos,
        "desglose": desglose,
        "necesidades": {
            "titulo": titulo, "pasaporte": pasaporte,
            "juventud": juvenil_necesidad, "afinidad": afinidad,
        },
        "estimaciones": resultados,
        "etapas": {
            "infancia": infancia, "juventud": juventud,
            "adultez_casa": casa_t, "adultez_boda": boda_t,
            "adultez_falso": falso_t,
        },
        "cuellos": cuellos[:10],
        "avisos": avisos,
        "desconocidos": sorted(set(pendientes)),
        "saldos": {
            "salida_infancia": saldo_i,
            "salida_juventud": saldo_j,
            "despues_casa": saldo_c,
        },
        "precision": "Cota económica, no duración probabilística ni p80.",
    }


def cargar_catalogo(ruta: str | Path | None = None) -> dict:
    ruta = Path(ruta) if ruta else Path(__file__).with_name("matriz_economica_v3.json")
    return json.loads(ruta.read_text(encoding="utf-8"))


def _json_safe(x: Any) -> Any:
    if isinstance(x, float) and math.isinf(x):
        return "inalcanzable"
    if isinstance(x, dict):
        return {k: _json_safe(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_json_safe(v) for v in x]
    return x


if __name__ == "__main__":
    catalogo = cargar_catalogo(sys.argv[1] if len(sys.argv) > 1 else None)
    print(json.dumps(_json_safe(evaluar(catalogo)), ensure_ascii=False, indent=2))
