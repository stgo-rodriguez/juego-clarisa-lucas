"""Relato verificable de los eventos SIMLOG v2.1, por jugador y ronda.

Lee el registro de eventos (orden Secuencia) y el catálogo vigente. No deduce
propuestas, pagos ni resultados que no se hayan registrado en la partida.
"""
from __future__ import annotations

from collections import defaultdict

from laboratorio.simlog_viewer_v21 import decode, integer, role_name

NOMBRES = {"A": "Amor", "P": "Personalidad", "K": "Conocimiento", "M": "Dinero"}
INFANCIA_CASILLEROS = {1: "Amor", 2: "Personalidad", 3: "Amor",
                        4: "Personalidad", 5: "Conocimiento", 6: "Amor"}
FUENTES_CARTA = {"situacion_vigente_premio", "situacion_vigente_perdida"}
FUENTES_DESTINO = {"adultez_casillero", "juventud_universidad",
                   "juventud_tramite", "juventud_destino"}


def _id(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _actor_ids(d):
    ids = set()
    for key in ("player", "players", "owners", "prior", "challenger", "defender",
                "active", "target", "dest", "from_player", "to_player", "partner",
                "support_from_companion", "winner", "source"):
        value = d.get(key)
        for v in value if isinstance(value, (list, tuple)) else [value]:
            pid = _id(v)
            if pid is not None:
                ids.add(pid)
    return ids


def _player_name(manifest, p):
    return role_name(manifest, p) if p is not None else "otro jugador"


def _resource(resource, amount):
    name = NOMBRES.get(str(resource), str(resource))
    return f"{amount} de {name}"


def _amounts(events, action):
    by_resource = defaultdict(int)
    for ev, d in events:
        if ev.get("Accion") == action and d.get("resource") in NOMBRES:
            by_resource[d["resource"]] += integer(d.get("amount"))
    return [ _resource(r, n) for r, n in by_resource.items() if n > 0 ]


def _joined(values):
    if not values:
        return ""
    if len(values) == 1:
        return values[0]
    return ", ".join(values[:-1]) + " y " + values[-1]


def _bullet(seq, title, text, category, *, options=None, chosen=None, turn=0):
    return {"secuencia": integer(seq), "tipo": category, "titulo": title,
            "texto": text, "opciones": options or [], "elegida": chosen,
            "turno": integer(turn)}


def _row_for(game, rnd, player):
    return next((t for t in game.get("turnos.csv", [])
                 if integer(t.get("Ronda")) == rnd
                 and integer(t.get("Jugador")) == player), None)


def _turn_events(events, turn, player=None):
    rows = [(e, d) for e, d in events if integer(e.get("Turno_global")) == turn]
    if player is not None:
        rows = [(e, d) for e, d in rows if _id(d.get("player")) == player]
    return rows


def _stage(game, rnd, player):
    current = _row_for(game, rnd, player)
    if current:
        return current.get("Etapa_antes") or current.get("Etapa_al_inicio_ronda") or "Etapa desconocida"
    previous = [t for t in game.get("turnos.csv", [])
                if integer(t.get("Jugador")) == player
                and integer(t.get("Ronda")) < rnd]
    if previous:
        previous.sort(key=lambda t: integer(t.get("Turno_global")))
        return previous[-1].get("Etapa_despues") or "Etapa desconocida"
    return "Etapa no registrada"


def _movement(t, events):
    stage = t.get("Etapa_antes") or ""
    origin = t.get("Pos_antes") or "?"
    destination = t.get("Pos_despues") or "?"
    card = t.get("Carta_Movimiento")
    die = t.get("Dado")
    consumed = t.get("Pasos_consumidos")
    discarded = integer(t.get("Pasos_descartados"))
    kind = t.get("Tipo_movimiento_infancia")
    if kind == "utn_exam_or_wait":
        return None
    if stage in ("Infancia", "UTN") and die not in (None, ""):
        intro = f"Salió {die} en el dado y avanzó del casillero {origin} al {destination}."
    elif card:
        choice = t.get("Desenlace_movimiento")
        amount = t.get("Distancia_movimiento") or "?"
        intro = (f"Usó la carta de Movimiento {card}"
                 + (f" (opción {choice})" if choice in ("A", "B") else "")
                 + f" para recorrer {amount} pasos: {origin} → {destination}.")
    else:
        return None
    extra = []
    if consumed not in ("", None) and discarded > 0:
        extra.append(f"Consumió {consumed} pasos y descartó {discarded}.")
    rebotes = decode(t.get("Rebotes_JSON"), []) or []
    if rebotes:
        extra.append(f"Rebotó {len(rebotes)} vez/veces en los bordes.")
    if stage == "Infancia":
        landing = integer(destination, -1)
        if landing in INFANCIA_CASILLEROS:
            extra.append(f"Cayó en el casillero de {INFANCIA_CASILLEROS[landing]}.")
    movement = next((e for e, d in events if e.get("Accion") == "paso_por_casillero"
                     and _id(d.get("player")) == integer(t.get("Jugador"))), None)
    if movement is None:
        movement = next((e for e, d in events if e.get("Accion") == "movement"
                         and _id(d.get("player")) == integer(t.get("Jugador"))), None)
    seq = movement.get("Secuencia") if movement else 0
    return _bullet(seq, "Movimiento", " ".join([intro, *extra]), "Movimiento",
                   turn=t.get("Turno_global"))


def _situation(t, events, cards):
    card_id = t.get("Carta_ID")
    if not card_id:
        return None
    card = cards.get(card_id) or {}
    title = card.get("title") or t.get("Situacion") or card_id
    context = card.get("context") or ""
    choice = t.get("Desenlace_elegido")
    # En SIMLOG estos son efectos realmente ejecutados: no confundirlos
    # con los valores máximos o teóricos de effects[A/B] del catálogo.
    economy = [(e, d) for e, d in events
               if _id(d.get("player")) == integer(t.get("Jugador"))
               and d.get("source") in FUENTES_CARTA]
    gains = _amounts(economy, "issue")
    losses = _amounts(economy, "spend")
    reserved_losses = [(e, d) for e, d in events
                       if e.get("Accion") == "reserve_loss"
                       and _id(d.get("player")) == integer(t.get("Jugador"))
                       and d.get("source") == "situacion_vigente_perdida"]
    losses.extend(f"{_resource(d.get('resource'), integer(d.get('amount')))}"
                  f" de la reserva de {d.get('reserve')}"
                  for _, d in reserved_losses)
    effects = []
    if gains:
        effects.append(f"ganó {_joined(gains)}")
    if losses:
        effects.append(f"perdió {_joined(losses)}")
    effective = " y ".join(effects) + "." if effects else "No tuvo cambios de recursos registrados."
    options = []
    for letter in ("A", "B"):
        opt = card.get("text_" + letter.lower())
        if opt:
            options.append((letter, str(opt)))
    if not options and t.get("Desenlace_texto") and choice in ("A", "B"):
        options = [(choice, t["Desenlace_texto"])]
    body = (f"{context} " if context else "")
    body += f"Eligió la opción {choice} y {effective}" if choice in ("A", "B") else effective
    # Los efectos de Afinidad están presentes en el propio turno.
    before, after = t.get("Afinidad_posicion_antes"), t.get("Afinidad_posicion_despues")
    zone0, zone1 = t.get("Afinidad_zona_antes"), t.get("Afinidad_zona_despues")
    if before not in (None, "") and after not in (None, "") and before != after:
        body += f" Su afinidad pasó de {before} ({zone0}) a {after} ({zone1})."
    anchor = next((e for e, d in events
                   if e.get("Accion") == "situation_context"
                   and _id(d.get("player")) == integer(t.get("Jugador"))), None)
    if anchor is None:
        anchor = next((e for e, d in events
                       if e.get("Accion") == "situation_resolved"
                       and _id(d.get("player")) == integer(t.get("Jugador"))), None)
    return _bullet(anchor.get("Secuencia") if anchor else 0,
                   f"Carta de Situación · {title} ({card_id})", body,
                   "Situación", options=options, chosen=choice,
                   turn=t.get("Turno_global"))


def _cash_events(events, player, turn):
    result = []
    for source, selection in _group_resource_events(events, player).items():
        if source in FUENTES_CARTA or source == "conversion_bancaria":
            continue
        category = "Casillero" if source.startswith("infancia_destino_") or source in FUENTES_DESTINO else "Recursos"
        gains = _amounts(selection, "issue")
        losses = _amounts(selection, "spend")
        phrases = []
        if gains:
            phrases.append(f"recibió {_joined(gains)}")
        if losses:
            phrases.append(f"gastó {_joined(losses)}")
        if not phrases:
            continue
        if source.startswith("infancia_destino_"):
            label = f"Casillero {source.rsplit('_', 1)[-1]}"
        else:
            label = {
                "adultez_casillero": "Casillero de Adultez",
                "juventud_universidad": "Casillero de Universidad",
                "juventud_tramite": "Casillero de Trámite",
                "colocacion_inicial_dublin": "Llegada a Dublín",
                "caida_perfil_adultez": "Perfil",
                "casa_banca": "Compra de Casa",
                "derrota_disputa_hito": "Disputa de un hito",
            }.get(source, source.replace("_", " ").capitalize())
        result.append(_bullet(selection[0][0].get("Secuencia"), label,
                              (" y ".join(phrases)[0].upper() + " y ".join(phrases)[1:]) + ".",
                              category, turn=turn))
    return result


def _group_resource_events(events, player):
    grouped = defaultdict(list)
    for e, d in events:
        if (e.get("Fuente") == "economia"
                and e.get("Accion") in ("issue", "spend")
                and _id(d.get("player")) == player
                and d.get("source")):
            grouped[d["source"]].append((e, d))
    return grouped


def _conversion(events, player, turn):
    group = _group_resource_events(events, player).get("conversion_bancaria", [])
    if not group:
        return []
    spent, received = _amounts(group, "spend"), _amounts(group, "issue")
    text = []
    if spent:
        text.append(f"entregó {_joined(spent)}")
    if received:
        text.append(f"recibió {_joined(received)}")
    return [_bullet(group[0][0].get("Secuencia"), "Canje con la banca",
                    (" y ".join(text)[0].upper() + " y ".join(text)[1:]) + ".", "Canje", turn=turn)]


def _duel(e, d, player, manifest):
    challenger, defender = _id(d.get("challenger")), _id(d.get("defender"))
    if player not in (challenger, defender):
        return None
    other = defender if player == challenger else challenger
    target = _player_name(manifest, other)
    kind = {"ordinario": "por recursos", "perfil": "por un Perfil",
            "hito": "por un hito"}.get(d.get("kind"), "de tipo " + str(d.get("kind")))
    outcome = d.get("result")
    if player == challenger:
        intro = f"Desafió a {target} en un duelo {kind}"
    else:
        intro = f"Recibió un desafío de {target} en un duelo {kind}"
    won = (outcome == "victoria" and player == challenger) or (outcome == "derrota" and player == defender)
    lost = (outcome == "derrota" and player == challenger) or (outcome == "victoria" and player == defender)
    if outcome == "retirada":
        result = ("se retiró y pagó 1 de Personalidad" if player == challenger else
                  f"{target} se retiró y le entregó 1 de Personalidad")
    elif outcome == "empate":
        result = "empataron"
    elif won:
        result = "ganó el duelo"
    elif lost:
        result = "perdió el duelo"
    else:
        result = f"resultado registrado: {outcome}"
    paid = integer(d.get("paid"))
    resource = d.get("paid_resource")
    if d.get("kind") == "ordinario" and paid and outcome in ("victoria", "derrota"):
        result += f" y {'recibió' if won else 'entregó'} {_resource(resource, paid)}"
    elif d.get("kind") == "hito" and outcome == "derrota" and player == challenger and paid:
        result += f" y gastó {_resource(resource, paid)}"
    elif d.get("kind") == "hito" and won and d.get("project"):
        result += f" (disputa por {d['project']})"
    if d.get("kind") == "perfil" and won and outcome == "victoria":
        result += " (se intercambiaron los Perfiles)"
    dice = []
    if d.get("challenger_die") is not None:
        dice.append(f"retador: {d['challenger_die']}")
    if d.get("defender_die") is not None:
        dice.append(f"defensor: {d['defender_die']}")
    if dice:
        result += f". Dados: {', '.join(dice)}"
    return _bullet(e.get("Secuencia"), "Duelo", intro + ": " + result + ".",
                   "Duelo", turn=e.get("Turno_global"))


def _invest(e, d, player, manifest, states):
    project = d.get("project", "proyecto")
    receipt = str(d.get("receipt") or "")
    sub = receipt.rsplit("-S", 1)[-1] if "-S" in receipt else None
    cost = None
    moment = integer(e.get("Turno_global"))
    for s in states:
        if (integer(s.get("Turno_global")) != moment or
                integer(s.get("Jugador")) != player or
                s.get("Momento") != "despues"):
            continue
        receipts = decode(s.get("Comprobantes_JSON"), []) or []
        cost = next((x for x in receipts if x.get("id") == receipt), None)
        if cost:
            break
    text = f"Invirtió en {project}"
    if sub:
        text += f", subhito {sub}"
    if cost:
        text += f": destinó {_resource(cost.get('resource'), cost.get('amount'))}"
    if receipt:
        text += f" (comprobante {receipt})"
    return _bullet(e.get("Secuencia"), "Inversión en subhito", text + ".",
                   "Subhito", turn=moment)


def _social(e, d, player, manifest):
    action = e.get("Accion")
    a = _id(d.get("player"))
    t = _id(d.get("target"))
    when = e.get("Turno_global")
    if action == "noviazgo_propuesta":
        other = _player_name(manifest, t if player == a else a)
        text = (f"Le propuso formar pareja a {other}." if player == a else
                f"Recibió una propuesta de pareja de {other}.")
        return _bullet(e.get("Secuencia"), "Propuesta de noviazgo", text,
                       "Noviazgo", turn=when)
    if action == "noviazgo_resultado":
        text = ("La propuesta fue aceptada y formaron pareja." if d.get("accepted")
                else "La propuesta no llegó a concretarse.")
        return _bullet(e.get("Secuencia"), "Resultado de la propuesta", text,
                       "Noviazgo", turn=when)
    if action == "pair":
        others = [_id(p) for p in d.get("players", []) if _id(p) != player]
        mate = _player_name(manifest, others[0]) if others else "otro jugador"
        return _bullet(e.get("Secuencia"), "Pareja formada",
                       f"Formó pareja con {mate}. La reserva de Pareja se constituye con 5 de Amor por integrante.",
                       "Noviazgo", turn=when)
    if action == "pair_broken":
        return _bullet(e.get("Secuencia"), "Ruptura", "La pareja se separó.",
                       "Noviazgo", turn=when)
    return None


def _other_event(e, d, player, manifest):
    action = e.get("Accion")
    turn = e.get("Turno_global")
    seq = e.get("Secuencia")
    other = lambda pid: _player_name(manifest, pid)
    if action == "transfer":
        sender, receiver = _id(d.get("source")), _id(d.get("dest"))
        r = _resource(d.get("resource"), integer(d.get("amount")))
        if player == sender:
            phrase = f"Le entregó {r} a {other(receiver)}."
        elif player == receiver:
            phrase = f"Recibió {r} de {other(sender)}."
        else:
            return None
        return _bullet(seq, "Transferencia de recursos", phrase, "Acuerdo", turn=turn)
    if action == "invest" and _id(d.get("player")) == player:
        return None  # Se prepara con datos de comprobante en _invest.
    if action == "adjudicate" and _id(d.get("player")) == player:
        outcome = "obtuvo" if d.get("won") else "no consiguió"
        return _bullet(seq, "Adjudicación de hito",
                       f"Intentó adjudicarse {d.get('project', 'el proyecto')} y {outcome} el hito.",
                       "Hito", turn=turn)
    if action == "house_attempt":
        result = "superó" if d.get("won") else "no superó"
        return _bullet(seq, "Intento de Casa",
                       f"Intentó adquirir Casa: tiró {d.get('dice_buyers')} contra "
                       f"{d.get('dice_owners_or_bank')} y {result} la tirada. "
                       f"Precio requerido: {d.get('price_per_player')} de Dinero por integrante.",
                       "Casa", turn=turn)
    if action == "house_bought":
        return _bullet(seq, "Casa conseguida", "Su pareja adquirió la Casa.",
                       "Casa", turn=turn)
    if action == "married":
        return _bullet(seq, "Casamiento", "La pareja alcanzó el Casamiento y ganó la partida.",
                       "Hito", turn=turn)
    if action == "enter_utn":
        return _bullet(seq, "Ingreso a UTN", "Entró al nodo de UTN.",
                       "Hito", turn=turn)
    if action == "utn_exam":
        res = "aprobó" if d.get("passed") else "desaprobó"
        return _bullet(seq, "Examen de UTN",
                       f"Rindió el examen de UTN: sacó {d.get('die')} y {res}.",
                       "Hito", turn=turn)
    if action == "utn_requirements_missing":
        return _bullet(seq, "Requisitos de UTN",
                       "No cumplió los requisitos de ingreso; deberá regresar al circuito.",
                       "Hito", turn=turn)
    if action == "utn_arrival_eligible":
        return _bullet(seq, "UTN",
                       "Llegó a UTN con los requisitos y podrá rendir en un turno posterior.",
                       "Hito", turn=turn)
    if action == "utn_to_youth":
        return _bullet(seq, "Juventud", "Pasó de UTN a Juventud.",
                       "Hito", turn=turn)
    if action in ("enter_dublin_from_youth", "enter_dublin"):
        return _bullet(seq, "Viaje a Dublín", "Inició el viaje a Dublín.",
                       "Hito", turn=turn)
    if action in ("land_dublin", "dublin_to_adult"):
        return _bullet(seq, "Adultez", "Llegó a Adultez desde Dublín.",
                       "Hito", turn=turn)
    if action == "profile_changed":
        return _bullet(seq, "Cambio de Perfil",
                       f"Cambió su Perfil de {d.get('from')} a {d.get('to')}.",
                       "Perfil", turn=turn)
    if action == "utn_profile_awarded":
        return _bullet(seq, "Perfil obtenido",
                       f"Obtuvo el Perfil {d.get('card')}.",
                       "Perfil", turn=turn)
    if action == "pair_reserve_repaired":
        return _bullet(seq, "Ayuda de pareja",
                       f"Se repusieron {d.get('amount') or d.get('lost')} de Amor a la reserva "
                       "de Pareja con ayuda del otro integrante.",
                       "Acuerdo", turn=turn)
    if action == "receipt_transfer":
        source, dest = _id(d.get("source")), _id(d.get("dest"))
        if player == source:
            narrative = f"Le transfirió el comprobante {d.get('receipt')} a {other(dest)}."
        elif player == dest:
            narrative = f"Recibió el comprobante {d.get('receipt')} de {other(source)}."
        else:
            return None
        return _bullet(seq, "Cesión de comprobante", narrative, "Subhito", turn=turn)
    if action == "house_lost":
        return _bullet(seq, "Pérdida de Casa",
                       "La pareja dejó de ser propietaria de la Casa.",
                       "Casa", turn=turn)
    if action == "return_youth_after_hito":
        return _bullet(seq, "Regreso a Juventud",
                       "Regresó a Juventud tras perder un hito.", "Hito", turn=turn)
    return None


def _covered_by_duel_transfer(e, d, player, events):
    """No contar de nuevo transferencias que fueron el pago de un duelo."""
    for duel_e, duel in events:
        if (duel_e.get("Accion") != "duel" or duel_e.get("Fuente") != "duelo"
                or integer(duel_e.get("Turno_global")) != integer(e.get("Turno_global"))
                or integer(duel_e.get("Secuencia")) < integer(e.get("Secuencia"))):
            continue
        if (duel.get("paid_resource") != d.get("resource")
                or integer(duel.get("paid")) != integer(d.get("amount"))):
            continue
        challenger, defender = _id(duel.get("challenger")), _id(duel.get("defender"))
        if duel.get("result") == "retirada":
            expected = challenger, defender
        elif duel.get("kind") == "ordinario" and duel.get("result") == "victoria":
            expected = defender, challenger
        elif duel.get("kind") == "ordinario" and duel.get("result") == "derrota":
            expected = challenger, defender
        else:
            continue
        if (_id(d.get("source")), _id(d.get("dest"))) == expected:
            return True
    return False


def _round_events(game, rnd):
    rows = []
    for e in game.get("eventos.csv", []):
        if integer(e.get("Ronda")) != rnd:
            continue
        d = decode(e.get("Detalle_JSON"), {}) or {}
        if not isinstance(d, dict):
            d = {}
        rows.append((e, d))
    return sorted(rows, key=lambda pair: integer(pair[0].get("Secuencia")))


def summarize_player_round(game, round_no, player, catalog=None):
    """Relato por etapas y sucesos: incluye interacciones en turnos ajenos.

    Las frases monetarias se basan en asientos efectivamente registrados;
    para las cartas el contexto y las dos opciones proceden del catálogo.
    """
    player = integer(player)
    round_no = integer(round_no)
    manifest = game.get("manifest", {})
    t = _row_for(game, round_no, player)
    stage = _stage(game, round_no, player)
    events = _round_events(game, round_no)
    card_map = {c.get("id"): c for c in (catalog or {}).get("cards", [])
                if c.get("id")}
    story = []

    if t:
        turn = integer(t.get("Turno_global"))
        own = _turn_events(events, turn)
        movement = _movement(t, own)
        if movement:
            story.append(movement)
        situation = _situation(t, own, card_map)
        if situation:
            story.append(situation)
        story.extend(_cash_events(own, player, turn))
        story.extend(_conversion(own, player, turn))

    # Eventos no contables y consecuencias ocurridas en turnos de terceros.
    has_proposal = {(integer(e.get("Turno_global")), _id(d.get("player")), _id(d.get("target")))
                    for e, d in events if e.get("Accion") == "noviazgo_propuesta"}
    for e, d in events:
        action = e.get("Accion")
        source = e.get("Fuente")
        involved = _actor_ids(d)
        active = _id(e.get("Jugador_activo"))
        if player not in involved and not (action == "house_attempt" and active == player):
            continue
        if action == "duel" and source == "duelo":
            item = _duel(e, d, player, manifest)
        elif action == "invest":
            item = _invest(e, d, player, manifest, game.get("estados_jugadores.csv", [])) if _id(d.get("player")) == player else None
        elif action in ("noviazgo_propuesta", "noviazgo_resultado", "pair", "pair_broken"):
            if action == "pair" and any(integer(e.get("Turno_global")) == tr and
                                      player in (a, b) for tr, a, b in has_proposal):
                # Hay relato explícito de propuesta y resultado; no repetir el acuerdo.
                continue
            item = _social(e, d, player, manifest)
        elif action == "transfer":
            item = None if _covered_by_duel_transfer(e, d, player, events) else _other_event(e, d, player, manifest)
        elif action in ("issue", "spend"):
            # Los ingresos y gastos de su propio turno se agrupan por origen
            # arriba; en el turno de otro jugador sí se pueden incluir.
            if active == player or integer(e.get("Turno_global")) == integer(t.get("Turno_global") if t else -1):
                item = None
            elif _id(d.get("player")) == player:
                kind = "Recibió" if action == "issue" else "Gastó"
                item = _bullet(e.get("Secuencia"), "Cambio de recursos",
                               f"{kind} {_resource(d.get('resource'), d.get('amount'))} durante "
                               f"el turno de {_player_name(manifest, active)}.",
                               "Recursos", turn=e.get("Turno_global"))
            else:
                item = None
        elif action in ("adjudicate", "house_attempt", "house_bought", "married",
                        "enter_utn", "utn_exam", "utn_requirements_missing",
                        "utn_arrival_eligible", "utn_to_youth", "enter_dublin_from_youth",
                        "enter_dublin", "land_dublin", "dublin_to_adult",
                        "profile_changed", "utn_profile_awarded",
                        "pair_reserve_repaired", "receipt_transfer", "house_lost",
                        "return_youth_after_hito"):
            item = _other_event(e, d, player, manifest)
        else:
            item = None
        if item:
            if active is not None and active != player and action not in ("transfer", "duel"):
                item["texto"] += f" (Durante el turno de {_player_name(manifest, active)}.)"
            story.append(item)

    story.sort(key=lambda item: (item["secuencia"], item["turno"]))
    return {
        "jugador": player, "nombre": _player_name(manifest, player),
        "etapa": stage, "ronda": round_no,
        "turno_propio": bool(t),
        "eventos": story,
    }
