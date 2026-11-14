"""Ejecutar un escenario explícito del modelo matemático v3.0 (sin simular).

Ejemplo:
    python -m laboratorio.v3.ejecutar_modelo
    python -m laboratorio.v3.ejecutar_modelo --salida /tmp/modelo_v3.json
    python -m laboratorio.v3.ejecutar_modelo --escenario mis_hipotesis.json

Con el archivo incluido por defecto, TODOS los importes son didácticos,
no están calibrados y NO son decisiones oficiales de v3.0.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from laboratorio.v3.catalogo import cargar_matriz
from laboratorio.v3.modelo_matematico import (
    calcular_demanda_secuencial, calibrar_emisiones,
    proyectar_flujos, tasas_desde_demanda,
)

EJEMPLO = Path(__file__).with_name("escenario_didactico_NO_CALIBRADO.json")


def analizar_escenario(escenario: dict) -> dict:
    """Un único escenario versionado; no completa claves omitidas."""
    matriz = cargar_matriz()
    amounts = escenario["ajustes"]
    flows = proyectar_flujos(matriz, amounts, escenario["activaciones"])
    targets = calibrar_emisiones(
        matriz,
        escenario["objetivos_produccion"],
        escenario["fuentes_calibrar"],
    )
    routes = {}
    for route in escenario["rutas"]:
        if route["id"] in routes:
            raise ValueError(f"Ruta duplicada: {route['id']}")
        routes[route["id"]] = {
            "ganadores_hipoteticos": route.get("ganadores_hipoteticos"),
            "demanda": calcular_demanda_secuencial(
                matriz, amounts, route["participantes"], route["eventos"],
                saldos_iniciales=route.get("saldos_iniciales"),
            ),
        }
    return {
        "fuente": "Especificación conceptual v3.0, 14/11/2026",
        "nombre_escenario": escenario["titulo"],
        "estado": "ANALISIS DETERMINISTA: NO SIMULACION NI CONFIGURACION APROBADA",
        "advertencia": escenario.get("advertencia"),
        "flujos_esperados": flows,
        "calibracion_inversa_condicionada_a_hipotesis": targets,
        "rutas": routes,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--escenario", type=Path, default=EJEMPLO)
    parser.add_argument("--salida", type=Path)
    args = parser.parse_args(argv)
    escenario = json.loads(args.escenario.read_text(encoding="utf-8"))
    out = analizar_escenario(escenario)
    out["tasas_desde_demanda_ejemplo"] = {
        name: tasas_desde_demanda(
            route["demanda"],
            {"Adultez": 5},
            {"Adultez": 2},
        ) for name, route in out["rutas"].items()
    } if args.escenario == EJEMPLO else None
    content = json.dumps(out, ensure_ascii=False, indent=2) + "\n"
    if args.salida:
        args.salida.parent.mkdir(parents=True, exist_ok=True)
        args.salida.write_text(content, encoding="utf-8")
        print(str(args.salida))
    else:
        print(content)


if __name__ == "__main__":
    main()
