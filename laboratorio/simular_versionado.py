"""Ejecutor versionado de Clarisa & Lucas.

La versión se valida ANTES de simular o escribir trazas. No admite
re-etiquetar resultados de v2.1 como si fueran de v2.2.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from simulador.versiones import RulesetNotReady, require_implemented


def main(argv=None):
    parser = argparse.ArgumentParser(description="Ejecutor SIMLOG por versión.")
    parser.add_argument("--version", choices=("2.1", "2.2"), required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--semillas", type=int, default=20)
    parser.add_argument("--inicio", type=int, default=1)
    parser.add_argument("--rondas", type=int, default=100)
    parser.add_argument("--sin-competencia", action="store_true")
    args = parser.parse_args(argv)

    try:
        require_implemented(args.version)
    except RulesetNotReady as exc:
        parser.error(str(exc))
    # Importar el motor únicamente después de comprobar la versión.
    if args.version == "2.1":
        from laboratorio.simular_mazos_vigentes_v2 import execute

        result = execute(
            args.out, seeds=args.semillas, start_seed=args.inicio,
            round_limit=args.rondas, competition=not args.sin_competencia
        )
    else:
        raise AssertionError("Selección de reglas inesperada.")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


if __name__ == "__main__":
    main()
