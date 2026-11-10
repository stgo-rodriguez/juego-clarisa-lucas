"""Ejecutor versionado de Clarisa & Lucas.

La versión se valida antes de simular o escribir trazas. Los motores
v2.1 y v2.2 conservan directorios y manifiestos distintos.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from simulador.versiones import RulesetNotReady, require_implemented


def main(argv=None):
    parser = argparse.ArgumentParser(description="Ejecutor SIMLOG por versión.")
    parser.add_argument("--version", choices=("2.1", "2.2", "2.3"), required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--semillas", type=int, default=20)
    parser.add_argument("--inicio", type=int, default=1)
    parser.add_argument("--rondas", type=int, default=100)
    parser.add_argument("--jugadores", choices=("6", "10", "ambos"), default="ambos",
                        help="Mesa de 6, de 10 o ambas; por defecto ambas.")
    parser.add_argument("--sin-competencia", action="store_true")
    parser.add_argument("--politica", choices=("planificador", "aleatorio", "mixto"),
                        default="planificador")
    parser.add_argument("--mano", choices=(3, 4), type=int, default=3)
    parser.add_argument("--sin-banco", action="store_true")

    args = parser.parse_args(argv)

    try:
        require_implemented(args.version)
    except RulesetNotReady as exc:
        parser.error(str(exc))
    # Importar el motor únicamente después de comprobar la versión.
    if args.version == "2.1":
        from laboratorio.simular_mazos_vigentes_v2 import execute
        if args.politica == "mixto" or args.mano != 3 or args.sin_banco:
            parser.error("Para estas variantes debés utilizar --version 2.2")
        kwargs = {"policy": args.politica}
    elif args.version == "2.2":
        from laboratorio.simular_v22 import execute
        kwargs = {"policy": args.politica, "hand_size": args.mano,
                  "bank_enabled": not args.sin_banco}
    elif args.version == "2.3":
        from laboratorio.simular_v23 import execute
        kwargs = {"policy": args.politica, "hand_size": args.mano,
                  "bank_enabled": not args.sin_banco}
    else:
        raise AssertionError("Selección de reglas inesperada.")
    result = execute(
        args.out, seeds=args.semillas, start_seed=args.inicio,
        sizes=(6, 10) if args.jugadores == 'ambos' else (int(args.jugadores),),
        round_limit=args.rondas, competition=not args.sin_competencia, **kwargs
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


if __name__ == "__main__":
    main()
