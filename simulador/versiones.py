"""Seleccionar explícitamente el motor de reglas 2.1, 2.2 o 2.3.

Cada versión conserva manifiestos, semillas y trazas independientes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class VersionInfo:
    version: str
    status: str
    specification: str | None
    engine_module: str | None


VERSIONS = {
    "2.1": VersionInfo(
        version="2.1",
        status="implemented_experimental",
        specification="Clarisa_y_Lucas_Especificacion_Integral_v2_1_Consolidada_Autonoma_2026-11-08.docx",
        engine_module="simulador.reglas_v21",
    ),
    "2.2": VersionInfo(
        version="2.2",
        status="implemented_experimental",
        specification="Clarisa_y_Lucas_Especificacion_Integral_v2_2_Consolidada_2026-11-09.docx",
        engine_module="simulador.reglas_v22",
    ),
    "2.3": VersionInfo(
        version="2.3",
        status="implemented_experimental",
        specification="Clarisa_y_Lucas_Especificacion_Integral_v2_3_Consolidada_2026-11-10.docx",
        engine_module="simulador.reglas_v23",
    ),
}


class RulesetNotReady(RuntimeError):
    """La versión pedida no tiene reglas verificables implementadas."""


def get_version(version: str) -> VersionInfo:
    try:
        return VERSIONS[version]
    except KeyError as exc:
        raise ValueError(f"Versión no reconocida: {version!r}") from exc


def require_implemented(version: str) -> VersionInfo:
    info = get_version(version)
    if info.status != "implemented_experimental" or not info.engine_module:
        raise RulesetNotReady(
            f"SIMLOG v{version} no tiene implementación verificada; "
            "no se puede ejecutar otra versión con esa etiqueta."
        )
    return info


def run_versioned(
    version: str,
    execute: Callable[..., object],
    **kwargs: object,
) -> object:
    """Comprueba la versión ANTES de crear archivos o producir una corrida."""
    require_implemented(version)
    return execute(**kwargs)
