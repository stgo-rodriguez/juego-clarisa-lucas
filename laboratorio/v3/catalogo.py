"""Catálogo económico conceptual v3.0.

Origen único: matriz_economica_v3.json, derivada de la especificación
conceptual del 14/11/2026. Este módulo NO simula partidas, NO impone
valores de v2.x y NO convierte reglas abiertas en decisiones aprobadas.

Uso:
    python -m laboratorio.v3.catalogo --validar
    python -m laboratorio.v3.catalogo --csv /ruta/a/matriz.csv
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Mapping

MATRIZ_PATH = Path(__file__).with_name("matriz_economica_v3.json")
RECURSOS = frozenset(("A", "P", "K", "M"))
ESTADOS = frozenset(("A DEFINIR", "ABIERTO", "EXPERIMENTAL"))
FLUJOS = frozenset((
    "EMISION", "CONSUMO", "INVERSION", "RESERVA", "REQUISITO",
    "TRANSFERENCIA", "CONSUMO/TRANSFERENCIA", "CONVERSION",
    "OBJETIVO", "CONTROL", "OBJETIVO_ANALITICO",
))


class CatalogoInvalido(ValueError):
    """Definición económica mal formada o escenario inconsistente."""


def cargar_matriz(ruta: Path | str = MATRIZ_PATH) -> dict:
    data = json.loads(Path(ruta).read_text(encoding="utf-8"))
    validar_matriz(data)
    return data


def validar_matriz(data: Mapping) -> None:
    if data.get("version") != "3.0-matriz-0.1":
        raise CatalogoInvalido("Versión de matriz v3.0 inesperada")
    filas = data.get("parametros")
    if not isinstance(filas, list) or not filas:
        raise CatalogoInvalido("Matriz vacía o inválida")
    campos = data.get("campos")
    if not isinstance(campos, list) or not campos:
        raise CatalogoInvalido("Falta el esquema de columnas")
    ids = set()
    for row in filas:
        if any(c not in row for c in campos):
            raise CatalogoInvalido(f"Fila sin campos obligatorios: {row!r}")
        key = row["id"]
        if not key or key in ids:
            raise CatalogoInvalido(f"Identificador de parámetro inválido: {key}")
        ids.add(key)
        if row["recurso"] not in RECURSOS | {"-"}:
            raise CatalogoInvalido(f"Recurso inválido: {key}")
        if row["flujo"] not in FLUJOS or row["estado"] not in ESTADOS:
            raise CatalogoInvalido(f"Flujo/estado inválido: {key}")
        if row["valor"] is not None:
            raise CatalogoInvalido(
                f"La matriz conceptual contiene una cifra prefijada: {key}"
            )
        if not row["fuente_seccion"] or not row["detalle"]:
            raise CatalogoInvalido(f"Fuente o descripción ausente: {key}")
        if row["flujo"] in {"EMISION", "CONSUMO", "INVERSION",
                            "RESERVA", "REQUISITO", "TRANSFERENCIA",
                            "OBJETIVO", "CONSUMO/TRANSFERENCIA"}:
            if row["recurso"] not in RECURSOS:
                raise CatalogoInvalido(f"Falta recurso real: {key}")
    # Un identificador por cada etapa, rol, decisión, recurso y tipo de efecto.
    for etapa in "IJD":
        for rol in "CL":
            for opcion in "AB":
                for recurso in "APKM":
                    for tipo in ("GANANCIA", "PERDIDA"):
                        key = f"SIT_{etapa}_{rol}_{opcion}_{recurso}_{tipo}"
                        if key not in ids:
                            raise CatalogoInvalido(f"Falta plantilla de carta: {key}")
    for r in RECURSOS:
        if f"AFINIDAD_META_{r}" not in ids:
            raise CatalogoInvalido(f"Falta meta de afinidad: {r}")
    if "FALSO_LUCAS_META_M" not in ids:
        raise CatalogoInvalido("Falta meta individual del Falso Lucas")


def exportar_csv(data: dict, destino: Path | str) -> Path:
    path = Path(destino)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=data["campos"], delimiter=",",
                                extrasaction="ignore")
        writer.writeheader()
        writer.writerows(data["parametros"])
    return path


def validar_ajustes(data: dict, ajustes: Mapping[str, object]) -> dict:
    """Devuelve un escenario parcial, sin completar silenciosamente faltantes.

    Los importes son fichas enteras no negativas; las participaciones 0..1.
    Los controles cualitativos quedan abiertos y no admiten cifras
    hasta que exista una codificación explícita de su variante.
    """
    params = {row["id"]: row for row in data["parametros"]}
    result = {}
    for key, amount in ajustes.items():
        if key not in params:
            raise CatalogoInvalido(f"Parámetro desconocido: {key}")
        row = params[key]
        if row["flujo"] == "CONTROL":
            raise CatalogoInvalido(
                f"Control reglamentario pendiente de codificación: {key}"
            )
        if row["flujo"] == "OBJETIVO_ANALITICO" and key.startswith("OBJETIVO_MEZCLA_"):
            if isinstance(amount, bool) or not isinstance(amount, (int, float)) or not 0 <= amount <= 1:
                raise CatalogoInvalido(f"Participación fuera de 0..1: {key}")
        elif isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
            raise CatalogoInvalido(f"Importe debe ser entero no negativo: {key}")
        if key in ("BANCO_ENTREGA", "BANCO_RECIBE") and amount == 0:
            raise CatalogoInvalido(f"La tasa del banco debe ser positiva: {key}")
        result[key] = amount
    return result


def emisiones_esperadas(
    data: dict,
    ajustes: Mapping[str, object],
    activaciones: Mapping[str, float],
) -> dict[tuple[str, str], float]:
    """Producción bruta por etapa/recurso dada una frecuencia medida.

    Separa plantillas no activadas: una frecuencia de 0 no necesita un
    importe; una frecuencia positiva con importe desconocido es ERROR.
    No contempla pérdidas, costes, transferencias ni conversiones.
    """
    amounts = validar_ajustes(data, ajustes)
    catalog = {row["id"]: row for row in data["parametros"]}
    totals = defaultdict(float)
    for key, freq in activaciones.items():
        if key not in catalog:
            raise CatalogoInvalido(f"Activación sin parámetro: {key}")
        row = catalog[key]
        if row["flujo"] != "EMISION":
            raise CatalogoInvalido(f"Esta función solo calcula EMISION: {key}")
        if isinstance(freq, bool) or not isinstance(freq, (int, float)) or freq < 0:
            raise CatalogoInvalido(f"Frecuencia inválida: {key}")
        if freq and key not in amounts:
            raise CatalogoInvalido(f"Importe pendiente para {key}; no asumir cero")
        if freq:
            # El evento Juventud/Adultez se asignará a etapa real en SIMLOG.
            if row["etapa"] == "Juventud/Adultez":
                raise CatalogoInvalido(
                    f"Activación de Perfil requiere etapa real: {key}"
                )
            totals[(row["etapa"], row["recurso"])] += freq * amounts[key]
    return dict(totals)


def resumen(data: dict) -> dict:
    return {
        "version": data["version"],
        "parametros": len(data["parametros"]),
        "por_flujo": dict(Counter(row["flujo"] for row in data["parametros"])),
        "por_estado": dict(Counter(row["estado"] for row in data["parametros"])),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validar", action="store_true")
    parser.add_argument("--csv", type=Path)
    args = parser.parse_args(argv)
    matriz = cargar_matriz()
    if args.csv:
        exportar_csv(matriz, args.csv)
    print(json.dumps(resumen(matriz), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
