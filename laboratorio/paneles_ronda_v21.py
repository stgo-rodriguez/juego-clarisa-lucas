"""Paneles verificables de hitos/subhitos e interacciones SIMLOG v2.1.

Todos los estados se leen AL CIERRE de la ronda seleccionada, nunca del
manifest final ni de registros de rondas futuras. Las actividades usan
exclusivamente eventos realmente emitidos por el motor y los bots.
"""
from __future__ import annotations

from laboratorio.simlog_viewer_v21 import decode, integer, role_name
from laboratorio.narrativa_simlog_v21 import (
    _round_events, _id, _covered_by_duel_transfer, NOMBRES,
)
from simulador.economia_v2 import PASSPORT_KIND, PROJECT_COSTS

HITOS = (
    ("titulo", "Título", "graduation-cap"),
    ("pasaporte", "Pasaporte", "book-user"),
    ("casa", "Casa", "house"),
    ("casamiento", "Casamiento", "heart"),
)


def _last(rows, round_no, player=None):
    found = [
        r for r in rows
        if integer(r.get("Ronda")) == round_no
        and r.get("Momento") == "despues"
        and (player is None or integer(r.get("Jugador")) == player)
    ]
    return max(found, key=lambda r: integer(r.get("Turno_global"))) if found else None


def _true(value):
    return value is True or str(value).strip().lower() in ("true", "1", "sí", "si")


def _ids(value):
    value = decode(value, None)
    if not isinstance(value, (list, tuple)):
        return set() if value is None else {_id(value)} - {None}
    return {_id(x) for x in value if _id(x) is not None}


def _project_kind(project, projects=None):
    if isinstance(projects, dict) and isinstance(projects.get(project), dict):
        kind = projects[project].get("kind")
        if kind in PROJECT_COSTS:
            return kind
    # IDs derivados del esquema vigente Titulo-1 / Italia-4 / Polonia-5
    return next((k for k in PROJECT_COSTS if str(project).startswith(k+"-")), None)


def _label_project(kind):
    return {"Titulo":"Título", "Italia":"Pasaporte (Italia)",
            "Polonia":"Pasaporte (Polonia)"}.get(kind, "Proyecto")


def _global_snapshot(game, ronda):
    world = _last(game.get("estados_globales.csv", []), ronda)
    if world is not None:
        return {
            "casa": _ids(world.get("Casa_duenios")),
            "casamiento": _ids(world.get("Casamiento")),
            "proyectos": decode(world.get("Proyectos_JSON"), {}) or {},
        }
    # Trazas parciales antiguas: el último turno de la ronda conserva el
    # estado global. No usar otro turno o el manifiesto del fin de partida.
    rows = [t for t in game.get("turnos.csv", []) if integer(t.get("Ronda")) == ronda]
    if not rows:
        return None
    last = max(rows, key=lambda t: integer(t.get("Turno_global")))
    if "Casa_duenios" not in last or "Casamiento_duenios" not in last:
        return None
    return {
        "casa": _ids(last.get("Casa_duenios")),
        "casamiento": _ids(last.get("Casamiento_duenios")),
        "proyectos": {},
    }


def estado_noviazgo(game, ronda, jugador):
    """Estado real de pareja al finalizar la ronda; nunca inferido del casamiento final.

    No confunde ausencia de pareja (campo null) con falta de snapshot.
    Si la pareja se casó, prioriza «Casados» sobre «De novios».
    """
    ronda, jugador = integer(ronda), integer(jugador)
    state = _last(game.get("estados_jugadores.csv", []), ronda, jugador)
    if state is None or "Pareja" not in state:
        return {"estado": "Sin datos", "pareja": None, "tono": "neutral",
                "detalle": "No hay estado de pareja registrado al cierre."}
    other = _id(state.get("Pareja"))
    if other is None:
        return {"estado": "Sin pareja", "pareja": None, "tono": "neutral",
                "detalle": "No estaba de novio/a al finalizar esta ronda."}
    name = role_name(game.get("manifest", {}), other)
    world = _global_snapshot(game, ronda)
    married = world is not None and jugador in world["casamiento"] and other in world["casamiento"]
    result = {
        "estado": "Casados" if married else "De novios",
        "pareja": other,
        "tono": "success" if married else "info",
        "detalle": f"{'Casados' if married else 'De novios'} con {name}.",
    }
    if "Pareja_compatible" in state and state["Pareja_compatible"] not in ("", None):
        result["afinidad"] = "Compatible" if _true(state["Pareja_compatible"]) else "Incompatible"
    return result


def estado_hitos(game, ronda, jugador):
    """Estado acumulado del jugador, comprobantes que aún posee y logros de pareja."""
    ronda, jugador = integer(ronda), integer(jugador)
    state = _last(game.get("estados_jugadores.csv", []), ronda, jugador)
    global_state = _global_snapshot(game, ronda)
    role = (game.get("manifest", {}).get("roles") or {}).get(str(jugador))
    expected_passport = PASSPORT_KIND.get(role)
    entries = []
    for key, title, icon in HITOS:
        entries.append({"id": key, "nombre":title, "icono":icon,
                        "estado":"Sin datos", "tono":"neutral", "detalle":""})
    if state is None:
        return {"hitos": entries, "comprobantes": [], "disponible": False}
    raw_receipts = decode(state.get("Comprobantes_JSON"), []) or []
    receipts = [r for r in raw_receipts if isinstance(r, dict)] if isinstance(raw_receipts, list) else []
    projects = global_state["proyectos"] if global_state else {}
    owned = []
    for receipt in receipts:
        project = str(receipt.get("project") or "")
        kind = _project_kind(project, projects)
        if kind is None:
            continue
        sub = receipt.get("subhito")
        if sub in ("", None):
            rid = str(receipt.get("id") or "")
            sub = rid.rsplit("-S", 1)[-1] if "-S" in rid else "?"
        owned.append({
            "proyecto": _label_project(kind),
            "tipo": kind,
            "subhito": str(sub),
            "comprobante": str(receipt.get("id") or ""),
            "recurso": receipt.get("resource"),
            "cantidad": integer(receipt.get("amount")),
        })
    title_receipts = [r for r in owned if r["tipo"] == "Titulo"]
    passport_receipts = [r for r in owned if r["tipo"] == expected_passport]
    if "Titulo" in state:
        achieved = _true(state["Titulo"])
        if achieved:
            entries[0].update(estado="Logrado", tono="success")
        elif title_receipts:
            entries[0].update(estado="En progreso", tono="info")
        else:
            entries[0].update(estado="Pendiente", tono="neutral")
        entries[0]["detalle"] = (f"{len(title_receipts)} comprobante(s) propio(s)" if title_receipts else "")
    if "Pasaporte" in state:
        passport = state.get("Pasaporte")
        achieved = bool(passport and str(passport).strip().lower() not in ("none", "null", "false"))
        if achieved:
            entries[1].update(estado="Logrado", tono="success",
                              detalle=str(passport))
        elif passport_receipts:
            entries[1].update(estado="En progreso", tono="info")
        else:
            entries[1].update(estado="Pendiente", tono="neutral")
        if not achieved and passport_receipts:
            entries[1]["detalle"] = f"{len(passport_receipts)} comprobante(s) propio(s)"
    if global_state is not None:
        entries[2].update(estado="Lograda" if jugador in global_state["casa"] else "Pendiente",
                          tono="success" if jugador in global_state["casa"] else "neutral")
        entries[3].update(estado="Logrado" if jugador in global_state["casamiento"] else "Pendiente",
                          tono="success" if jugador in global_state["casamiento"] else "neutral")
    return {"hitos": entries, "comprobantes": owned, "disponible": True}


def _item(seq, title, description, status, tone, *, actor="propio", category=""):
    return {
        "secuencia": integer(seq),
        "titulo": title,
        "descripcion": description,
        "estado": status,
        "tono": tone,
        "participacion": actor,
        "tipo": category,
    }


def _pair_at_turn(game, turn, a, b):
    """Verifica que A y B compartían pareja al cerrar ese turno."""
    if a == b:
        return True
    rows = game.get("estados_jugadores.csv", [])
    state = next((x for x in rows if integer(x.get("Turno_global")) == turn
                  and integer(x.get("Jugador")) == a and x.get("Momento") == "despues"), None)
    if state is None:
        return False
    return _id(state.get("Pareja")) == b


def _pair_members_for_house(game, event, detail):
    action = event.get("Accion")
    if action in ("house_bought", "married"):
        return _ids(detail.get("owners") or detail.get("players"))
    active = _id(event.get("Jugador_activo"))
    if action == "house_attempt" and active is not None:
        players = {active}
        for state in game.get("estados_jugadores.csv", []):
            if (integer(state.get("Turno_global")) == integer(event.get("Turno_global"))
                    and state.get("Momento") == "despues"
                    and integer(state.get("Jugador")) == active):
                mate = _id(state.get("Pareja"))
                if mate is not None:
                    players.add(mate)
                break
        return players
    if action == "house_lost":
        prior = next((s for s in game.get("estados_globales.csv", [])
                      if integer(s.get("Turno_global")) == integer(event.get("Turno_global"))
                      and s.get("Momento") == "antes"), None)
        return _ids(prior.get("Casa_duenios")) if prior else set()
    return set()


def eventos_hitos_ronda(game, ronda, jugador):
    """Avances de la ronda, sin confundir inversión, adjudicación y posesión."""
    ronda, jugador = integer(ronda), integer(jugador)
    manifest = game.get("manifest", {})
    world = _global_snapshot(game, ronda) or {}
    projects = world.get("proyectos", {})
    result = []
    for ev, d in _round_events(game, ronda):
        action, seq = ev.get("Accion"), ev.get("Secuencia")
        active = _id(ev.get("Jugador_activo"))
        if action == "invest" and _id(d.get("player")) == jugador:
            kind = _project_kind(d.get("project"), projects)
            receipt = str(d.get("receipt") or "")
            subtext = receipt.rsplit("-S",1)[-1] if "-S" in receipt else "?"
            cost = PROJECT_COSTS.get(kind, ())
            index = integer(subtext, 0) - 1
            text = f"Proyecto {d.get('project')} · comprobante {receipt}"
            if 0 <= index < len(cost):
                r, amount = cost[index]
                text += f" · inversión {amount} de {NOMBRES[r]}"
            result.append(_item(seq, f"{_label_project(kind)} · Subhito {subtext}", text,
                                "Invirtió", "info", category="subhito"))
        elif action == "adjudicate" and _id(d.get("player")) == jugador:
            won = _true(d.get("won"))
            kind = _project_kind(d.get("project"), projects)
            text = (f"Proyecto {d.get('project')} · dado {d.get('die', '—')}"
                    f" · pago {d.get('payment', '—')}")
            result.append(_item(seq, f"Adjudicación de {_label_project(kind)}", text,
                                "Conseguido" if won else "Intento fallido",
                                "success" if won else "warning", category="hito"))
        elif action == "receipt_transfer":
            sender, receiver = _id(d.get("source")), _id(d.get("dest"))
            if jugador not in (sender, receiver):
                continue
            received = jugador == receiver
            peer = sender if received else receiver
            result.append(_item(seq, "Cesión de subhito",
                                f"Comprobante {d.get('receipt') or 'sin ID'} · "
                                f"{'recibido de' if received else 'entregado a'} {role_name(manifest, peer)}",
                                "Recibido" if received else "Transferido",
                                "info" if received else "neutral", category="subhito"))
        elif action == "house_attempt" and jugador in _pair_members_for_house(game, ev, d):
            won = _true(d.get("won"))
            result.append(_item(seq, "Intento de Casa",
                                f"Dados {d.get('dice_buyers', '—')} contra "
                                f"{d.get('dice_owners_or_bank', '—')} · "
                                f"precio {d.get('price_per_player', '—')} Dinero por integrante",
                                "Tirada ganada" if won else "Intento fallido",
                                "success" if won else "warning",
                                actor="realizado" if jugador == active else "en pareja",
                                category="casa"))
        elif action in ("house_bought", "married") and jugador in _pair_members_for_house(game, ev, d):
            result.append(_item(seq, "Casa" if action == "house_bought" else "Casamiento",
                                "Logro compartido por la pareja.",
                                "Conseguida" if action == "house_bought" else "Ganaron",
                                "success", actor="en pareja", category="hito"))
        elif action == "house_lost" and jugador in _pair_members_for_house(game, ev, d):
            result.append(_item(seq, "Casa", "Perdieron la propiedad de la Casa.",
                                "Perdida", "danger", actor="en pareja", category="casa"))
    return sorted(result, key=lambda x:x["secuencia"])


def eventos_sociales_ronda(game, ronda, jugador):
    """Una tarjeta por interacción; propuestas y resultado quedan vinculados."""
    ronda, jugador = integer(ronda), integer(jugador)
    manifest = game.get("manifest", {})
    events = _round_events(game, ronda)
    outcomes = {}
    proposals = set()
    for ev, d in events:
        if ev.get("Accion") == "noviazgo_resultado":
            key = (integer(ev.get("Turno_global")), _id(d.get("player")), _id(d.get("target")))
            outcomes[key] = d.get("accepted")
        elif ev.get("Accion") == "noviazgo_propuesta":
            proposals.add((integer(ev.get("Turno_global")), _id(d.get("player")), _id(d.get("target"))))
    result = []
    for ev, d in events:
        action, seq, turn = ev.get("Accion"), ev.get("Secuencia"), integer(ev.get("Turno_global"))
        if action == "duel" and ev.get("Fuente") == "duelo":
            a, b = _id(d.get("challenger")), _id(d.get("defender"))
            if jugador not in (a, b):
                continue
            initiated = jugador == a
            other = b if initiated else a
            outcome = d.get("result")
            won = (outcome == "victoria" and initiated) or (outcome == "derrota" and not initiated)
            lost = (outcome == "derrota" and initiated) or (outcome == "victoria" and not initiated)
            if won:
                status, tone = "Ganó", "success"
            elif lost:
                status, tone = "Perdió", "danger"
            elif outcome == "retirada":
                status, tone = ("Se retiró", "warning") if initiated else ("Rival se retiró", "success")
            elif outcome == "empate":
                status, tone = "Empate", "neutral"
            else:
                status, tone = "Registrado", "neutral"
            kind = {"ordinario":"por recursos", "perfil":"por Perfil",
                    "hito":"por un hito"}.get(d.get("kind"), str(d.get("kind") or ""))
            text = f"{'Desafió a' if initiated else 'Lo desafió'} {role_name(manifest,other)} · {kind}"
            paid, resource = integer(d.get("paid")), d.get("paid_resource")
            if paid and resource in NOMBRES:
                receiver = ("recibió" if won or (outcome == "retirada" and not initiated)
                            else "entregó")
                text += f" · {receiver} {paid} {NOMBRES[resource]}"
            if d.get("project"):
                text += f" · {d['project']}"
            result.append(_item(seq, "Duelo", text, status, tone,
                                actor="realizado" if initiated else "recibido", category="duelo"))
        elif action == "noviazgo_propuesta":
            a, b = _id(d.get("player")), _id(d.get("target"))
            if jugador not in (a, b):
                continue
            created = jugador == a
            other = b if created else a
            key = (turn,a,b)
            accepted = outcomes.get(key)
            if accepted is None:
                status,tone = "Sin resolución", "neutral"
            else:
                status,tone = ("Aceptada","success") if _true(accepted) else ("No concretada","warning")
            result.append(_item(seq, "Propuesta de noviazgo",
                                f"{'A' if created else 'De'} {role_name(manifest,other)}",
                                status,tone,
                                actor="realizada" if created else "recibida",category="noviazgo"))
        elif action == "pair":
            participants = _ids(d.get("players"))
            if jugador not in participants or any(
                t == turn and jugador in (a,b) for t,a,b in proposals
            ):
                continue
            other = next(iter(participants - {jugador}),None)
            result.append(_item(seq, "Pareja formada",
                                f"Con {role_name(manifest,other)}", "Formada",
                                "success",actor="compartido",category="noviazgo"))
        elif action == "pair_broken":
            participants = _ids(d.get("players"))
            if jugador in participants:
                result.append(_item(seq, "Ruptura", "Terminó la relación de pareja.",
                                    "Separación","warning",actor="compartido",category="noviazgo"))
        elif action == "transfer":
            sender, receiver = _id(d.get("source")), _id(d.get("dest"))
            if jugador not in (sender,receiver) or _covered_by_duel_transfer(ev,d,jugador,events):
                continue
            delivered = jugador == sender
            other = receiver if delivered else sender
            res = NOMBRES.get(d.get("resource"),str(d.get("resource") or "recurso"))
            result.append(_item(seq, "Transferencia",
                                f"{integer(d.get('amount'))} {res} "
                                f"{'a' if delivered else 'de'} {role_name(manifest,other)}",
                                "Entregó" if delivered else "Recibió",
                                "neutral" if delivered else "info",
                                actor="realizada" if delivered else "recibida",category="transferencia"))
        elif action in ("pair_reserve_repaired","pair_reserve_not_repaired"):
            affected = {_id(d.get(k)) for k in ("player","source","dest","active")}
            affected.discard(None)
            if jugador in affected:
                success = action=="pair_reserve_repaired"
                result.append(_item(seq,"Ayuda para reserva de pareja",
                                    "Recuperación de la reserva de Amor.",
                                    "Restituida" if success else "No restituida",
                                    "success" if success else "warning",
                                    actor="en pareja",category="acuerdo"))
        elif action == "receipt_transfer":
            # Se ve tanto en Subhitos como en Interacciones: se indica la cesión,
            # no se atribuye una segunda inversión.
            sender, receiver = _id(d.get("source")), _id(d.get("dest"))
            if jugador not in (sender,receiver):
                continue
            given = jugador == sender
            other = receiver if given else sender
            result.append(_item(seq,"Cesión de comprobante",
                                f"{d.get('receipt')} · {'a' if given else 'de'} {role_name(manifest,other)}",
                                "Entregó" if given else "Recibió",
                                "neutral" if given else "info",
                                actor="realizada" if given else "recibida",category="acuerdo"))
    return sorted(result,key=lambda x:x["secuencia"])
