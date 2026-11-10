"""Ruteo explícito de versiones para no atribuir a v2.2 reglas v2.1.

La versión 2.2 no se activa hasta registrar una especificación aprobada
y un motor con pruebas independientes. No introduce mecánicas nuevas.
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
            "SIMLOG v2.2 no está implementado: falta una especificación v2.2 "
            "identificada y una matriz de diferencias confirmada. No se ejecuta "
            "el motor v2.1 con etiqueta v2.2."
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
