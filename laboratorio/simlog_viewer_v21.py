"""Lectura y preparación de partidas SIMLOG v2.1/v2.2/v2.3 de solo lectura.

No reejecuta partidas ni altera el motor, los mazos o los logs.
Acepta una carpeta de resultados o un ZIP que incluya las carpetas de traza.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from io import BytesIO, StringIO
from pathlib import Path
import csv
import hashlib
import json
import re
import zipfile

SCHEMA = "SIMLOG-2.1"  # Conservado por compatibilidad con pruebas y archivos históricos.
RULESET = "especificacion-integral-2026-11-08"
SUPPORTED_RULESETS = {
    "SIMLOG-2.1": "especificacion-integral-2026-11-08",
    "SIMLOG-2.2": "especificacion-integral-2026-11-09",
    "SIMLOG-2.3": "especificacion-integral-2026-11-10",
}


def _supported(manifest: dict) -> bool:
    """Validar el par esquema + reglas, sin confundir trazas entre versiones."""
    schema = manifest.get("schema")
    return (schema in SUPPORTED_RULESETS
            and SUPPORTED_RULESETS[schema] == manifest.get("ruleset"))
CATEGORIES = (
    "Situación A/B", "Movimiento", "Duelos", "Canjes", "Noviazgo",
    "Subhitos", "Acuerdos", "Hitos", "Afinidad", "Perfil",
    "Recursos", "Otros",
)
DEFAULT_CATEGORIES = CATEGORIES[:10]
STAGE_COLORS = {
    "Infancia": "#b9cbe5",
    "UTN": "#c5d6e9",
    "Juventud": "#c7d9c2",
    "Vuelo a Dublín": "#e7d8b8",
    "Adultez": "#e5cae5",
}
CATEGORY_COLORS = {
    "Situación A/B": "#2563eb", "Movimiento": "#94a3b8",
    "Duelos": "#dc2626", "Canjes": "#f97316",
    "Noviazgo": "#db2777", "Subhitos": "#7c3aed",
    "Acuerdos": "#0891b2", "Hitos": "#16a34a",
    "Afinidad": "#a855f7", "Perfil": "#b45309",
    "Recursos": "#64748b", "Otros": "#475569",
}
CATEGORY_SYMBOLS = {
    "Situación A/B": "circle", "Movimiento": "circle-open",
    "Duelos": "x", "Canjes": "diamond", "Noviazgo": "star-diamond",
    "Subhitos": "square", "Acuerdos": "triangle-up",
    "Hitos": "star", "Afinidad": "hexagon",
    "Perfil": "pentagon", "Recursos": "circle-open",
    "Otros": "cross",
}


def integer(value, default=0):
    try:
        return int(float(str(value).strip().lstrip("'")))
    except (TypeError, ValueError):
        return default


def decode(value, default=None):
    if value in (None, ""):
        return default
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except (ValueError, TypeError):
        return default


def pair_from_manifest(manifest):
    summary = manifest.get("summary") or {}
    pair = decode(summary.get("winning_pair"))
    if pair is None:
        pair = decode(summary.get("pair"))
    if isinstance(pair, (tuple, list)) and len(pair) == 2:
        try:
            return tuple(sorted(int(x) for x in pair))
        except (ValueError, TypeError):
            pass
    return ()


def _manifest_to_game(directory, manifest):
    if not _supported(manifest):
        return None
    summary = manifest.get("summary") or {}
    pair = pair_from_manifest(manifest)
    status = str(manifest.get("status") or "")
    rounds = integer(summary.get("rounds"), 0)
    size = integer(manifest.get("player_count"), integer(summary.get("size"), 0))
    return {
        "directory": directory,
        "id": str(manifest.get("run_id") or directory or "partida"),
        "schema": manifest.get("schema"),
        "ruleset": manifest.get("ruleset"),
        "size": size,
        "seed": integer(manifest.get("seed"), integer(summary.get("seed"), 0)),
        "rounds": rounds,
        "pair": pair,
        "won": bool(pair) and (status == "marriage" or summary.get("won") is True),
        "status": status,
    }


def _is_zip_source(root, zip_bytes=None):
    return zip_bytes is not None or (
        Path(root).expanduser().is_file() and
        Path(root).suffix.lower() == ".zip"
    )


def _open_zip(root, zip_bytes=None):
    return zipfile.ZipFile(BytesIO(zip_bytes) if zip_bytes is not None
                           else Path(root).expanduser())


def discover_games(root: str | Path, zip_bytes: bytes | None = None) -> list[dict]:
    """Encuentra trazas v2.1, v2.2 o v2.3 en carpetas o ZIP locales."""
    games = []
    if _is_zip_source(root, zip_bytes):
        with _open_zip(root, zip_bytes) as archive:
            for member in archive.namelist():
                if member.split("/")[-1] != "manifest.json" or member.endswith("/"):
                    continue
                if member.startswith("/") or ".." in Path(member).parts:
                    continue
                try:
                    manifest = json.loads(archive.read(member))
                    directory = member.rsplit("/", 1)[0] if "/" in member else ""
                    game = _manifest_to_game(directory, manifest)
                    if game:
                        games.append(game)
                except (ValueError, KeyError, OSError):
                    continue
    else:
        folder = Path(root).expanduser()
        if folder.is_file() and folder.name == "manifest.json":
            paths = [folder]
        elif folder.is_dir():
            paths = sorted(folder.rglob("manifest.json"))
        else:
            paths = []
        for path in paths:
            try:
                manifest = json.loads(path.read_text(encoding="utf-8"))
                game = _manifest_to_game(str(path.parent.resolve()), manifest)
                if game:
                    games.append(game)
            except (ValueError, OSError):
                continue
    return sorted(games, key=lambda v: (v["size"], v["seed"], v["id"]))


def _read_raw(root, directory, name, zip_bytes):
    if _is_zip_source(root, zip_bytes):
        key = f"{directory}/{name}" if directory else name
        with _open_zip(root, zip_bytes) as archive:
            return archive.read(key)
    folder = Path(directory).expanduser().resolve()
    return (folder / name).read_bytes()


def _read_text(root, directory, name, zip_bytes):
    return _read_raw(root, directory, name, zip_bytes).decode("utf-8-sig")


def load_game(root: str | Path, directory: str, zip_bytes: bytes | None = None):
    """Devuelve los datos de una sola partida (validando esquema y pertenencia)."""
    valid = {g["directory"] for g in discover_games(root, zip_bytes)}
    if directory not in valid:
        raise ValueError("Partida no incluida en la fuente SIMLOG compatible seleccionada")
    manifest = json.loads(_read_text(root, directory, "manifest.json", zip_bytes))
    if not _supported(manifest):
        raise ValueError("Esquema SIMLOG/ruleset no compatible (admite v2.1 y v2.2)")
    data = {"manifest": manifest, "directory": directory}
    for name in ("turnos.csv", "eventos.csv", "hitos.csv",
                 "estados_jugadores.csv", "estados_globales.csv",
                 "recursos_por_ronda.csv"):
        try:
            content = _read_text(root, directory, name, zip_bytes)
            data[name] = list(csv.DictReader(StringIO(content)))
        except (FileNotFoundError, KeyError):
            if name in ("turnos.csv", "eventos.csv"):
                raise ValueError(f"Falta el archivo requerido {name}") from None
            data[name] = []
    return data


def role_name(manifest, player):
    role = (manifest.get("roles") or {}).get(str(player), "")
    return f"{role} #{player}" if role else f"Jugador #{player}"


def _actors(detail, event):
    """IDs explícitos. El activo solo se usa cuando no hay otro participante."""
    actors = set()
    for field in ("player", "players", "owners", "prior", "challenger", "defender",
                  "active", "target", "winner", "source", "dest", "from_player",
                  "to_player", "partner", "support_from_companion"):
        value = detail.get(field)
        if isinstance(value, (list, tuple, set)):
            candidates = value
        else:
            candidates = [value]
        for candidate in candidates:
            if isinstance(candidate, int) or (isinstance(candidate, str) and candidate.isdigit()):
                actors.add(int(candidate))
    affected = event.get("Jugador_afectado")
    if affected not in (None, "") and str(affected).isdigit():
        actors.add(int(affected))
    if not actors:
        active = event.get("Jugador_activo")
        if active not in (None, "") and str(active).isdigit():
            actors.add(int(active))
    return actors


def _category(event, detail):
    action = str(event.get("Accion") or "").lower()
    source = str(event.get("Fuente") or "").lower()
    cause = str(detail.get("source") or "").lower()
    if action in ("duel", "duelo", "duel_retreat", "duelo_retirada"):
        # El controlador también emite un resumen del duelo: usar la instancia
        # detallada del subsistema 'duelo' y no duplicar el combate.
        return None if source == "competencia" else "Duelos"
    if cause == "conversion_bancaria":
        return None  # Los dos movimientos contables se sintetizan desde Canje.
    if action in ("pair", "pair_broken", "pair_proposed", "pair_proposal",
                  "proposal_accepted", "proposal_rejected", "noviazgo",
                  "noviazgo_propuesta", "noviazgo_resultado"):
        return "Noviazgo"
    if action in ("invest", "adjudicate", "receipt_transfer"):
        return "Subhitos"
    if action in ("transfer", "pair_reserve_repaired", "pair_reserve_not_repaired",
                  "transfer_pair"):
        return "Acuerdos"
    if action in ("married", "house_bought", "house_attempt", "house_lost",
                  "enter_dublin", "enter_dublin_from_youth", "dublin_to_adult",
                  "land_dublin", "enter_utn", "utn_exam", "utn_to_youth",
                  "return_youth_after_hito", "utn_requirements_missing"):
        return "Hitos"
    if action in ("afinidad_desplazamiento",):
        return "Afinidad"
    if action in ("profile_changed", "profile_activation", "utn_profile_awarded"):
        return "Perfil"
    if action in ("issue", "spend", "reserve_loss"):
        return "Recursos"
    if action in ("turno_inicio", "turno_final", "paso_por_casillero",
                  "casillero_activado", "situation_resolved",
                  "proposed_situation", "situation_revealed",
                  "situation_assignment_locked", "situation_context",
                  "movement", "round_start", "youth_dealt",
                  "transicion_inicio_ronda", "hand_renewed"):
        return None
    return "Otros"


def _describe(detail):
    important = ("resource", "amount", "source", "project", "receipt",
                 "choice", "result", "die", "won", "card", "player",
                 "players", "challenger", "defender", "defender_die", "target", "accepted",
                 "challenger_die", "from_player", "dest", "stage",
                 "before", "after", "reserve")
    return " · ".join(f"{k}: {detail[k]}" for k in important if detail.get(k) is not None)


def _item(round_no, turn, player, category, label, description="", sequence=None, detail=None, stage=""):
    return {
        "ronda": integer(round_no), "turno": integer(turn), "jugador": int(player),
        "categoria": category, "evento": str(label), "detalle": str(description or ""),
        "secuencia": integer(sequence), "etapa": str(stage or ""),
        "datos": detail if detail is not None else {},
    }


def build_events(game, players=None):
    """Eventos realmente registrados para los jugadores indicados.

    Si players no se especifica, se usa la pareja ganadora (compatibilidad
    histórica). En partidas sin casamiento se debe indicar a quién seguir.
    """
    manifest = game["manifest"]
    winners = tuple(players) if players is not None else pair_from_manifest(manifest)
    if not winners:
        return []
    items = []
    turns = sorted(game["turnos.csv"], key=lambda t: integer(t.get("Turno_global")))
    stages_by_turn = {integer(t.get("Turno_global")): t.get("Etapa_antes") for t in turns}
    for t in turns:
        p = integer(t.get("Jugador"))
        if p not in winners:
            continue
        rnd, turn = integer(t.get("Ronda")), integer(t.get("Turno_global"))
        stage = t.get("Etapa_situacion") or t.get("Etapa_antes")
        if t.get("Carta_ID") and t.get("Desenlace_elegido") in ("A", "B"):
            letter = t["Desenlace_elegido"]
            label = f"Situación {letter} · {t.get('Situacion') or t['Carta_ID']}"
            desc = f"Carta {t['Carta_ID']} · {t.get('Desenlace_texto') or ''}"
            items.append(_item(rnd, turn, p, "Situación A/B", label, desc,
                               stage=stage, detail={"carta": t["Carta_ID"], "opcion": letter}))
        movement = t.get("Carta_Movimiento")
        if movement or t.get("Dado") not in ("", None):
            choice = t.get("Desenlace_movimiento") or ""
            title = f"Movimiento {choice}" if choice else "Movimiento D6"
            desc = (f"Carta {movement or 'D6'} · dado {t.get('Dado') or '—'} · "
                    f"distancia {t.get('Distancia_movimiento') or '—'} · "
                    f"{t.get('Pos_antes')} → {t.get('Pos_despues')}")
            items.append(_item(rnd, turn, p, "Movimiento", title, desc,
                               stage=t.get("Etapa_movimiento") or t.get("Etapa_antes"),
                               detail={"ruta": decode(t.get("Ruta_JSON"), [])}))
        if t.get("Canje"):
            items.append(_item(rnd, turn, p, "Canjes", "Conversión de recursos",
                               t["Canje"], stage=t.get("Etapa_antes")))
    for ev in game["eventos.csv"]:
        detail = decode(ev.get("Detalle_JSON"), {}) or {}
        if not isinstance(detail, dict):
            detail = {"valor": detail}
        category = _category(ev, detail)
        if category is None:
            continue
        actors = _actors(detail, ev).intersection(winners)
        if not actors:
            continue
        turn = integer(ev.get("Turno_global"))
        for player in sorted(actors):
            items.append(_item(ev.get("Ronda"), turn, player, category,
                               ev.get("Accion") or "Evento", _describe(detail),
                               sequence=ev.get("Secuencia"), detail=detail,
                               stage=stages_by_turn.get(turn) or ""))
    # Evita entradas idénticas del mismo evento y jugador sin perder orden real.
    seen, output = set(), []
    for item in sorted(items, key=lambda x: (x["ronda"], x["turno"], x["secuencia"], x["jugador"], x["categoria"])):
        key = (item["ronda"], item["turno"], item["secuencia"], item["jugador"],
               item["categoria"], item["evento"])
        if key not in seen:
            output.append(item)
            seen.add(key)
    return output


def stage_intervals(game, winners):
    """Rangos visuales derivados de etapas registradas, no de duraciones supuestas."""
    by_player = defaultdict(list)
    for t in game["turnos.csv"]:
        pid = integer(t.get("Jugador"))
        if pid in winners:
            by_player[pid].append((integer(t.get("Ronda")), t.get("Etapa_antes") or ""))
    intervals = []
    for pid in winners:
        rows = sorted(by_player[pid])
        if not rows:
            continue
        first, last, stage = rows[0][0], rows[0][0], rows[0][1]
        for rnd, next_stage in rows[1:]:
            if next_stage != stage or rnd > last + 1:
                intervals.append((pid, stage, first, last))
                first, stage = rnd, next_stage
            last = rnd
        intervals.append((pid, stage, first, last))
    return intervals


def visible_events(items, categories, from_round, to_round):
    categories = set(categories)
    return [x for x in items if x["categoria"] in categories
            and from_round <= x["ronda"] <= to_round]


def audit(game, root, zip_bytes=None):
    manifest = game["manifest"]
    errors = []
    for filename, expected in (manifest.get("file_sha256") or {}).items():
        try:
            # Hash del archivo original: no normalizar BOM ni saltos de línea.
            raw = _read_raw(root, game["directory"], filename, zip_bytes)
            if hashlib.sha256(raw).hexdigest() != expected:
                errors.append(f"SHA-256 diferente: {filename}")
        except (OSError, KeyError, ValueError):
            errors.append(f"No se pudo verificar: {filename}")
    events = game["eventos.csv"]
    sequences = [integer(e.get("Secuencia")) for e in events]
    if sequences != list(range(1, len(sequences) + 1)):
        errors.append("Secuencia de eventos no consecutiva")
    run_id = manifest.get("run_id")
    if run_id and any(row.get("Partida") != run_id for row in game["turnos.csv"]):
        errors.append("ID de partida inconsistente en turnos")
    return errors
