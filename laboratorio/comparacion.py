"""Servicios de la Fase 3: corrida y comparación de escenarios, sin Streamlit.

Este módulo llama al adaptador ya validado. No altera el motor reglamentario,
las políticas de bots ni el consumo de RNG de la partida.
"""
from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import statistics
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile

from simulador.economia import EconomyConfig, ScenarioConfig
from simulador.motor import aggregate, parse_cards, run_batch, write_csv
from laboratorio.ejecucion import ADAPTER, CARDS, MOTOR, ROOT, sha


def escenario_desde_dict(data: dict) -> ScenarioConfig:
    """Construye un escenario respetando la validación del esquema existente."""
    if not isinstance(data, dict):
        raise ValueError("El escenario debe ser un objeto JSON")
    value = dict(data)
    economics = value.pop("economia", {})
    if not isinstance(economics, dict):
        raise ValueError("economia debe ser un objeto")
    unknown = set(value) - set(ScenarioConfig.__dataclass_fields__)
    if unknown:
        raise ValueError(f"Campos desconocidos: {sorted(unknown)}")
    return ScenarioConfig(**value, economia=EconomyConfig.from_dict(economics))


def escenario_base(jugadores: int, partidas: int, *, seed: int | None = None,
                   max_rondas: int = 120, bot: str = "mixed") -> ScenarioConfig:
    if jugadores not in (6, 10):
        raise ValueError("La línea base admite 6 o 10 jugadores")
    return ScenarioConfig(
        id=f"base_v13_solo_infancia_{jugadores}j", jugadores=jugadores,
        partidas=partidas, seed=(131028 if jugadores == 6 else 231028) if seed is None else seed,
        incremento_seed=103, max_rondas=max_rondas, bot=bot,
        economia=EconomyConfig(),
    )


def signature() -> dict:
    """Identidad de la implementación y entradas; sirve para invalidar cachés."""
    return {"motor_sha256": sha(MOTOR), "adaptador_sha256": sha(ADAPTER),
            "mazo_sha256": sha(CARDS),
            "economia_sha256": sha(ROOT / "simulador" / "economia.py")}


def ejecutar(config: ScenarioConfig) -> dict:
    """Ejecuta todas las partidas con idéntica llamada a run_batch que el CLI."""
    cards = parse_cards(CARDS)
    rows, samples = run_batch(
        config.partidas, config.jugadores, config.seed, cards,
        max_rounds=config.max_rondas, bot_mode=config.bot,
        economia=config.economia, incremento_seed=config.incremento_seed,
    )
    return {"escenario": config.as_dict(), "filas": rows,
            "muestras": samples, "resumen": aggregate(rows), "codigo": signature()}


def _semillas(resultado: dict) -> list[int]:
    rows = resultado["filas"]
    seeds = [int(row["semilla"]) for row in rows]
    if len(seeds) != len(set(seeds)):
        raise ValueError("La simulación contiene semillas duplicadas")
    return seeds


def comparar(base: dict, variante: dict) -> dict:
    """Estadísticas descriptivas apareadas. No son intervalos de confianza."""
    a, b = base["escenario"], variante["escenario"]
    for key in ("jugadores", "partidas", "seed", "incremento_seed", "max_rondas", "bot"):
        if a[key] != b[key]:
            raise ValueError(f"No son comparables: {key} diferente")
    if _semillas(base) != _semillas(variante):
        raise ValueError("Las semillas no coinciden por posición")
    aa, bb = base["filas"], variante["filas"]
    paired = [(int(x["rondas_observadas"]), int(y["rondas_observadas"]))
              for x, y in zip(aa, bb)
              if int(x["terminada"]) and int(y["terminada"])]
    delta = [y - x for x, y in paired]
    n = len(aa)
    valid = len(delta)
    changed = sum(x != y for x, y in zip(aa, bb))
    return {
        "total": n,
        "semillas_apareadas": True,
        "ambas_finalizadas": valid,
        "alguna_censurada": n - valid,
        "finalizadas_base": sum(int(x["terminada"]) for x in aa),
        "finalizadas_variante": sum(int(x["terminada"]) for x in bb),
        "delta_media_rondas_apareadas": round(statistics.mean(delta), 3) if delta else None,
        "delta_mediana_rondas_apareadas": round(statistics.median(delta), 3) if delta else None,
        "variaron_rondas_o_estado": sum(
            x["rondas_observadas"] != y["rondas_observadas"]
            or x["terminada"] != y["terminada"]
            for x, y in zip(aa, bb)),
        "filas_completamente_distintas": changed,
        "advertencia_censura": ("Los deltas de rondas usan solo pares que terminaron ambas partidas; "
                              "no estiman el tiempo total de partidas censuradas.") if valid < n else "",
    }


def _csv_bytes(rows: list[dict]) -> bytes:
    # Se reutiliza exactamente la misma serialización del CLI; conserva BOM,
    # columnas y orden, requisito para verificar los hashes históricos.
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "salida.csv"
        write_csv(path, rows)
        return path.read_bytes()


def exportar_zip(base: dict, variante: dict, comparacion: dict) -> bytes:
    """Descarga autocontenida con artefactos y SHA de cada resultado."""
    items = (("base", base), ("variante", variante))
    stream = BytesIO()
    manifest = {"version": "fase3-mvp", "archivos": {}, "motor": signature()}
    with ZipFile(stream, "w", compression=ZIP_DEFLATED, compresslevel=6) as zf:
        for label, result in items:
            csv_body = _csv_bytes(result["filas"])
            filename = f"{label}/resultados.csv"
            zf.writestr(filename, csv_body)
            manifest["archivos"][filename] = sha256(csv_body).hexdigest()
            zf.writestr(f"{label}/escenario.json", json.dumps(result["escenario"], ensure_ascii=False, indent=2))
            zf.writestr(f"{label}/resumen.json", json.dumps(result["resumen"], ensure_ascii=False, indent=2))
            zf.writestr(f"{label}/muestra_eventos.json", json.dumps(result["muestras"], ensure_ascii=False, indent=2))
        zf.writestr("comparacion.json", json.dumps(comparacion, ensure_ascii=False, indent=2))
        zf.writestr("manifiesto.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    return stream.getvalue()
