"""Optimización conjunta (premios + costos) para la economía conceptual v3.0.

Esta fase busca configuraciones ENTERAS no dominadas para un conjunto de
supuestos EXPLÍCITOS sobre duraciones, frecuencias y rutas económicas.

No simula partidas. La oferta de recursos se trata como esperada por mesa y
ronda; la demanda es una COTA INFERIOR optimista, sin tiempos intrarronda,
negociación, estrategias, azar ni probabilidades reales de victoria.

Ningún valor histórico de v2.x es usado por defecto.
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import random
from collections import defaultdict
from pathlib import Path
from typing import Mapping

from laboratorio.v3.catalogo import CatalogoInvalido, cargar_matriz, validar_ajustes
from laboratorio.v3.modelo_matematico import (
    ETAPAS, RECURSOS, _etapa_valida, _numero_no_negativo,
    calcular_demanda_secuencial,
)

CLAVES_METRICAS = (
    "deficit", "excedente", "desviacion_mezcla", "disparidad_rutas",
    "desviacion_presion",
)
ESCENARIO_EJEMPLO = Path(__file__).with_name(
    "escenario_optimizacion_NO_CALIBRADO.json"
)


def _numero_positivo(valor, nombre: str) -> float:
    x = _numero_no_negativo(valor, nombre)
    if x <= 0:
        raise CatalogoInvalido(f"{nombre} debe ser positivo")
    return x


def _validar_escenario(matriz: dict, escenario: Mapping) -> tuple:
    """Fallar ante hipótesis ausentes, reglas implícitas o variables inertes."""
    defs = {p["id"]: p for p in matriz["parametros"]}
    for key in ("variables", "ajustes_fijos", "fuentes",
                "rondas_por_etapa", "rutas", "pesos", "presion_objetivo"):
        if key not in escenario:
            raise CatalogoInvalido(f"Escenario sin {key}")
    vars_ = escenario["variables"]
    if not isinstance(vars_, list) or not vars_:
        raise CatalogoInvalido("Se requiere al menos una variable económica")
    fixed = validar_ajustes(matriz, escenario["ajustes_fijos"])
    seen = set()
    domains = []
    for v in vars_:
        key = v.get("parametro")
        if key not in defs or key in seen or key in fixed:
            raise CatalogoInvalido(f"Variable inexistente, repetida o fija: {key}")
        if defs[key]["flujo"] not in {
            "EMISION", "CONSUMO", "RESERVA", "REQUISITO", "INVERSION",
            "OBJETIVO", "CONSUMO/TRANSFERENCIA"
        }:
            raise CatalogoInvalido(f"No se permite optimizar flujo {key}")
        values = v.get("valores")
        if not isinstance(values, list) or not values or len(set(
            (type(x).__name__, str(x)) for x in values
        )) != len(values):
            raise CatalogoInvalido(f"Dominio vacío o repetido: {key}")
        for value in values:
            validar_ajustes(matriz, {key: value})
        domains.append((key, tuple(sorted(values))))
        seen.add(key)
    rounds = escenario["rondas_por_etapa"]
    if not isinstance(rounds, dict) or not rounds:
        raise CatalogoInvalido("Faltan rondas por etapa")
    if any(s not in ETAPAS for s in rounds):
        raise CatalogoInvalido("Etapa inválida en rondas")
    for stage, count in rounds.items():
        _numero_positivo(count, f"Rondas {stage}")
    sources = escenario["fuentes"]
    if not isinstance(sources, list) or not sources:
        raise CatalogoInvalido("Se requieren fuentes productivas")
    source_ids = set()
    uses = set()
    for src in sources:
        key, stage = src.get("parametro"), src.get("etapa")
        if key not in defs or defs[key]["flujo"] != "EMISION":
            raise CatalogoInvalido(f"Fuente desconocida o no productiva: {key}")
        _etapa_valida(stage, defs[key])
        if stage not in rounds:
            raise CatalogoInvalido(f"Sin rondas para fuente {key}/{stage}")
        rate = _numero_no_negativo(
            src.get("activaciones_por_ronda_mesa"),
            f"Activaciones por ronda de mesa {key}"
        )
        ident = (key, stage, src.get("instancia"))
        if ident in source_ids:
            raise CatalogoInvalido(f"Fuente duplicada: {ident}")
        source_ids.add(ident)
        if (not isinstance(src.get("instancia"), (type(None), str))
                or src.get("instancia") == ""):
            raise CatalogoInvalido(f"Instancia inválida: {key}")
        if rate:
            uses.add(key)
            if key not in fixed and key not in seen:
                raise CatalogoInvalido(f"Fuente activa sin importe: {key}")
    routes = escenario["rutas"]
    if not isinstance(routes, list) or not routes:
        raise CatalogoInvalido("Se requieren rutas de objetivos explícitas")
    names = set()
    for route in routes:
        rid = route.get("id")
        if not isinstance(rid, str) or not rid or rid in names:
            raise CatalogoInvalido(f"Ruta inexistente o repetida: {rid}")
        names.add(rid)
        _numero_positivo(route.get("peso"), f"Peso de ruta {rid}")
        actors = route.get("participantes")
        if not isinstance(actors, list) or not actors:
            raise CatalogoInvalido(f"Ruta sin participantes: {rid}")
        events = route.get("eventos")
        if not isinstance(events, list) or not events:
            raise CatalogoInvalido(f"Ruta sin eventos: {rid}")
        for event in events:
            key = event.get("parametro")
            if key not in defs:
                raise CatalogoInvalido(f"Evento sin parámetro de catálogo: {key}")
            if event.get("etapa") not in rounds:
                raise CatalogoInvalido(f"Sin ronda para evento {rid}/{key}")
            uses.add(key)
            if key not in fixed and key not in seen:
                raise CatalogoInvalido(f"Demanda sin importe: {rid}/{key}")
    if seen - uses:
        raise CatalogoInvalido(
            "Variables sin efecto en producción ni rutas: "
            + ", ".join(sorted(seen - uses))
        )
    if not isinstance(escenario["pesos"], dict) or set(
        escenario["pesos"]
    ) != set(CLAVES_METRICAS):
        raise CatalogoInvalido("Informar pesos de todas las métricas")
    scalar_weights = {}
    for key, val in escenario["pesos"].items():
        scalar_weights[key] = _numero_no_negativo(
            val, f"Peso de métrica {key}"
        )
    if not any(scalar_weights.values()):
        raise CatalogoInvalido("Los pesos de la optimización son todos cero")
    stress = _numero_no_negativo(
        escenario["presion_objetivo"], "Presión económica objetivo"
    )
    if not 0 < stress <= 1:
        raise CatalogoInvalido("Presión objetivo fuera del intervalo (0,1]")
    mix = escenario.get("mezcla_objetivo", {})
    for stage, target in mix.items():
        if stage not in rounds or set(target) != set(RECURSOS):
            raise CatalogoInvalido(f"Mezcla incompleta: {stage}")
        nums = [_numero_no_negativo(target[r], f"Mezcla {stage}/{r}")
                for r in "APKM"]
        if not math.isclose(sum(nums), 1, abs_tol=1e-9):
            raise CatalogoInvalido(f"La mezcla {stage} no suma 1")
    if scalar_weights["desviacion_mezcla"] > 0 and not mix:
        raise CatalogoInvalido("Peso de mezcla positivo sin mezcla objetivo")
    return fixed, domains, scalar_weights


def _oferta_por_mesa(
    matriz: dict, escenario: Mapping, amounts: Mapping[str, int]
) -> dict:
    definitions = {p["id"]: p for p in matriz["parametros"]}
    supply = defaultdict(lambda: defaultdict(float))
    sources = []
    for src in escenario["fuentes"]:
        key, stage = src["parametro"], src["etapa"]
        rate = src["activaciones_por_ronda_mesa"]
        n = amounts.get(key)
        if n is None:
            raise CatalogoInvalido(f"Fuente activa no parametrizada: {key}")
        value = n * rate * escenario["rondas_por_etapa"][stage]
        resource = definitions[key]["recurso"]
        supply[stage][resource] += value
        sources.append({
            "parametro": key,
            "instancia": src.get("instancia"),
            "etapa": stage, "recurso": resource,
            "activaciones_por_ronda_mesa": rate,
            "premio": n, "emision_esperada": value,
        })
    return {"por_etapa": {
        s: {r: supply[s][r] for r in "APKM"} for s in ETAPAS
    }, "por_fuente": sources}


def evaluar_configuracion(
    matriz: dict, escenario: Mapping,
    amounts: Mapping[str, int], *,
    verificar: bool = True
) -> dict:
    """Comparar recursos disponibles contra rutas y presión objetivo.

    La presión = demanda total / emisión total (para recursos con demanda),
    no la probabilidad de victoria. Los déficits se calculan recurso por
    recurso y etapa por etapa, permitiendo excedentes anteriores como stock.
    Las transferencias entre los dos miembros se idealizan: NO demuestra
    que un Falso Lucas decida colaborar ni que la Casa sea alcanzable.
    """
    if verificar:
        fixed, domains, weights = _validar_escenario(matriz, escenario)
        required = set(fixed) | {k for k, _ in domains}
        if set(amounts) != required:
            raise CatalogoInvalido(
                "Configuración incompleta, extras o no corresponde al escenario"
            )
        validar_ajustes(matriz, amounts)
        for k, values in domains:
            if amounts[k] not in values:
                raise CatalogoInvalido(f"Valor fuera del dominio: {k}")
        if any(amounts[k] != fixed[k] for k in fixed):
            raise CatalogoInvalido("No se pueden modificar ajustes fijos")
    else:
        weights = escenario["pesos"]
    supply = _oferta_por_mesa(matriz, escenario, amounts)
    rounds = escenario["rondas_por_etapa"]
    totals = defaultdict(float)
    for stage in rounds:
        for r in "APKM":
            totals[r] += supply["por_etapa"][stage][r]
    total_supply = sum(totals.values())
    ratio = {}
    for stage, goal in escenario.get("mezcla_objetivo", {}).items():
        production = supply["por_etapa"][stage]
        denom = sum(production.values())
        ratio[stage] = {
            r: production[r] / denom if denom else None for r in "APKM"
        }
    mix_error = 0.0
    for stage, goal in escenario.get("mezcla_objetivo", {}).items():
        actual = ratio[stage]
        if any(actual[r] is None for r in goal):
            mix_error += 1.0
        else:
            mix_error += sum(
                abs(actual[r] - goal[r]) for r in "APKM"
            ) / 2.0
    route_reports = []
    sumweights = sum(route["peso"] for route in escenario["rutas"])
    deficit = excess = stress_error = 0.0
    route_burdens = []
    for route in escenario["rutas"]:
        demands = calcular_demanda_secuencial(
            matriz, amounts, route["participantes"], route["eventos"],
            saldos_iniciales=route.get("saldos_iniciales")
        )
        credit = defaultdict(float)
        deficits = []
        needed_sum = 0.0
        # Presión global por recurso (no convierte recursos dispares).
        for stage in ETAPAS:
            for r in "APKM":
                new = supply["por_etapa"][stage][r]
                needed = demands["produccion_minima_por_etapa"][stage][r]
                credit[r] += new
                needed_sum += needed
                short = max(0.0, needed - credit[r])
                if short:
                    deficits.append({
                        "etapa": stage, "recurso": r,
                        "faltante": short, "demanda": needed,
                    })
                credit[r] = max(0.0, credit[r] - needed)
        # Escasez por tipo. Normalizaciones adimensionales y explícitas:
        # no compensamos una escasez de A con excedente de M.
        short_fraction = sum(
            d["faltante"] for d in deficits
        ) / max(1.0, needed_sum)
        remaining = sum(credit.values())
        excess_fraction = remaining / max(1.0, total_supply)
        pressure = needed_sum / max(1.0, total_supply)
        weight = route["peso"] / sumweights
        deficit += weight * short_fraction
        excess += weight * excess_fraction
        stress_error += weight * abs(pressure - escenario["presion_objetivo"])
        route_burdens.append((route["id"], pressure))
        route_reports.append({
            "ruta": route["id"],
            "peso_relativo": weight,
            "ganadores_hipoteticos": route.get("ganadores_hipoteticos"),
            "demanda_por_etapa": demands["produccion_minima_por_etapa"],
            "demanda_total": demands["produccion_minima_total"],
            "emision_total": total_supply,
            "faltantes": deficits,
            "deficit_relativo": short_fraction,
            "excedente_relativo": excess_fraction,
            "presion_total": pressure,
            "calculo": "Cota económica idealizada; no probabilidad de victoria",
        })
    disparity = (max(p for _, p in route_burdens)
                 - min(p for _, p in route_burdens)) if route_burdens else 0.0
    metrics = {
        "deficit": deficit,
        "excedente": excess,
        "desviacion_mezcla": mix_error,
        "disparidad_rutas": disparity,
        "desviacion_presion": stress_error,
    }
    score = sum(weights[k] * metrics[k] for k in CLAVES_METRICAS)
    if not math.isfinite(score):
        raise CatalogoInvalido("Puntaje inválido")
    return {
        "ajustes": dict(amounts),
        "objetivos": metrics, "puntaje_ponderado": score,
        "oferta": supply, "composicion": ratio,
        "rutas": route_reports,
        "interpretacion": "Comparación de presupuestos esperados; no simulación de partidas",
    }


def _domina(a: Mapping, b: Mapping, tol: float = 1e-10) -> bool:
    return (all(a[k] <= b[k] + tol for k in CLAVES_METRICAS)
            and any(a[k] < b[k] - tol for k in CLAVES_METRICAS))


def _frontera(evaluados: list[dict], limite: int) -> tuple[list[dict], int]:
    # Los cinco objetivos pueden contradecirse. No ocultar ese conflicto.
    front = []
    for candidate in evaluados:
        x = candidate["objetivos"]
        if any(_domina(other["objetivos"], x) for other in front):
            continue
        front = [other for other in front
                 if not _domina(x, other["objetivos"])]
        front.append(candidate)
    front.sort(key=lambda r: (r["puntaje_ponderado"],
                              tuple(sorted(r["ajustes"].items()))))
    return front[:limite], len(front)


def optimizar(
    matriz: dict, escenario: Mapping, *,
    max_evaluaciones: int = 1500, semilla: int = 20261114,
    limite_pareto: int = 12
) -> dict:
    """Exploración exacta de dominios pequeños; búsqueda local reproducible si no.

    El mejor por score depende de pesos elegidos por diseñador: no es una
    configuración universalmente óptima ni un resultado de SIMLOG.
    """
    fixed, domains, weights = _validar_escenario(matriz, escenario)
    if isinstance(max_evaluaciones, bool) or not isinstance(max_evaluaciones, int) or max_evaluaciones < 1:
        raise CatalogoInvalido("max_evaluaciones debe ser positivo")
    if isinstance(semilla, bool) or not isinstance(semilla, int):
        raise CatalogoInvalido("Semilla inválida")
    if isinstance(limite_pareto, bool) or not isinstance(limite_pareto, int) or limite_pareto < 1:
        raise CatalogoInvalido("limite_pareto debe ser positivo")
    keys = tuple(k for k, _ in domains)
    choices = tuple(v for _, v in domains)
    possible = math.prod(len(x) for x in choices)
    evaluated = {}
    rng = random.Random(semilla)

    def check(chromosome: tuple) -> dict | None:
        if chromosome in evaluated:
            return evaluated[chromosome]
        if len(evaluated) >= max_evaluaciones:
            return None
        amounts = dict(fixed)
        amounts.update(zip(keys, chromosome))
        out = evaluar_configuracion(matriz, escenario, amounts, verificar=False)
        evaluated[chromosome] = out
        return out

    if possible <= max_evaluaciones:
        method = "EXHAUSTIVA"
        for chromosome in itertools.product(*choices):
            check(chromosome)
    else:
        method = "COORDENADAS_MULTINICIO_DETERMINISTA"
        # Explora esquinas, centro y estados aleatorios; mejora cambiando
        # una variable por vez, con recomienzos acotados.
        centers = [
            tuple(x[0] for x in choices),
            tuple(x[len(x)//2] for x in choices),
            tuple(x[-1] for x in choices),
        ]
        centers.extend(
            tuple(rng.choice(x) for x in choices)
            for _ in range(min(50, max_evaluaciones // 4 + 1))
        )
        for initial in centers:
            if len(evaluated) >= max_evaluaciones:
                break
            current = initial
            previous = check(current)
            if previous is None:
                break
            while len(evaluated) < max_evaluaciones:
                best = current
                best_result = previous
                # Orden pseudoaleatorio pero reproducible: evita sesgo por ID.
                coordinates = list(range(len(keys)))
                rng.shuffle(coordinates)
                for pos in coordinates:
                    for amount in choices[pos]:
                        if amount == current[pos]:
                            continue
                        neighbor = current[:pos] + (amount,) + current[pos+1:]
                        next_result = check(neighbor)
                        if next_result is None:
                            break
                        if (next_result["puntaje_ponderado"]
                                < best_result["puntaje_ponderado"] - 1e-10):
                            best = neighbor
                            best_result = next_result
                    if len(evaluated) >= max_evaluaciones:
                        break
                if best == current:
                    break
                current, previous = best, best_result
        # Si los dominios son muy grandes y se agotan reinicios,
        # agregar muestras reproducibles en lugar de declarar exhaustividad.
        while len(evaluated) < max_evaluaciones:
            check(tuple(rng.choice(x) for x in choices))
    all_results = list(evaluated.values())
    all_results.sort(
        key=lambda x: (x["puntaje_ponderado"],
                       tuple(sorted(x["ajustes"].items())))
    )
    top, front_total = _frontera(all_results, limite_pareto)
    best = all_results[0]
    return {
        "estado": "EXPERIMENTO NUMERICO CON HIPOTESIS, NO BALANCE APROBADO",
        "metodo": method,
        "espacio_combinaciones": possible,
        "combinaciones_evaluadas": len(evaluated),
        "semilla": semilla,
        "variables": [{"parametro": k, "dominio": list(values)}
                      for k, values in domains],
        "pesos_objetivos": weights,
        "mejor_por_pesos": best,
        "frontera_pareto": top,
        "frontera_pareto_total": front_total,
        "frontera_pareto_mostrada": len(top),
        "limitaciones": [
            "No es un simulador v3.0 ni estima probabilidades de victoria.",
            "Frecuencias, rondas, pesos y dominios son HIPOTESIS explícitas.",
            "La demanda es cota inferior con cooperación idealizada y emisión agregada por pareja/mesa.",
            "No se modelan pérdidas estocásticas, distribución del ingreso entre integrantes ni ventanas de pago.",
            "Sin simulación no se pueden validar costos, premios ni duración reales.",
            "Las reglas ABIERTAS de v3.0 no quedan aprobadas por el resultado.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--escenario", type=Path, default=ESCENARIO_EJEMPLO)
    parser.add_argument("--salida", type=Path)
    parser.add_argument("--max-evaluaciones", type=int, default=1500)
    parser.add_argument("--semilla", type=int, default=20261114)
    args = parser.parse_args(argv)
    scenario = json.loads(args.escenario.read_text(encoding="utf-8"))
    result = optimizar(cargar_matriz(), scenario,
                       max_evaluaciones=args.max_evaluaciones,
                       semilla=args.semilla)
    result["titulo_escenario"] = scenario.get("titulo", "Sin título")
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.salida:
        args.salida.parent.mkdir(parents=True, exist_ok=True)
        args.salida.write_text(text, encoding="utf-8")
        print(args.salida)
    else:
        print(text)


if __name__ == "__main__":
    main()
