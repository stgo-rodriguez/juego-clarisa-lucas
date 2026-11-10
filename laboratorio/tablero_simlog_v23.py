"""Tablero SIMLOG de solo lectura: posiciones comprobables al cierre de cada ronda.

La fuente de verdad es estados_jugadores.csv, Momento=despues, último Turno_global
de la ronda. No se infiere movimiento de compañeros desde turnos individuales.
Compatible con trazas SIMLOG-2.1, SIMLOG-2.2 y SIMLOG-2.3.
"""
from __future__ import annotations

from collections import Counter
import json
import math
import re

import plotly.graph_objects as go

from laboratorio.simlog_viewer_v21 import integer

AZUL = "#2563eb"
NARANJA = "#ea580c"
VERDE = "#16a34a"
GRIS = "#64748b"

def _role(manifest, pid, row):
    return str(row.get("Rol") or (manifest.get("roles") or {}).get(str(pid)) or "Desconocido")

def _partner(value):
    if value in ("", None, "null", "None", "[]"):
        return None
    try:
        value = json.loads(value) if isinstance(value, str) else value
    except (ValueError, TypeError):
        return None
    if isinstance(value, bool) or isinstance(value, (dict, list)):
        return None
    n = integer(value, 0)
    return n if n > 0 else None

def _adult_coord(value):
    """Aceptar solo coordenadas físicas fila,columna 1..5 registradas."""
    if isinstance(value, (tuple, list)) and len(value) == 2:
        components = list(value)
    else:
        raw = str(value or "").strip()
        found = re.fullmatch(r"\(?\s*([1-5])\s*[,;]\s*([1-5])\s*\)?", raw)
        components = list(found.groups()) if found else []
    if len(components) != 2:
        return None
    row, col = integer(components[0]), integer(components[1])
    return (row, col) if 1 <= row <= 5 and 1 <= col <= 5 else None

def _normalize_stage(value):
    txt = str(value or "").strip().casefold()
    if txt in ("infancia", "niñez"):
        return "Infancia"
    if "utn" in txt:
        return "UTN"
    if txt in ("juventud", "joven"):
        return "Juventud"
    if "dubl" in txt or txt == "vuelo":
        return "Vuelo a Dublín"
    if txt in ("adultez", "adulto"):
        return "Adultez"
    if "casa" in txt and "casamiento" in txt:
        return "Casamiento"
    if "casamiento" in txt:
        return "Casamiento"
    return str(value or "")

def snapshot_de_ronda(game: dict, ronda: int) -> dict:
    """Última instantánea común de la ronda, no último turno propio de cada ficha."""
    rows = [r for r in game.get("estados_jugadores.csv", [])
            if integer(r.get("Ronda")) == integer(ronda)
            and str(r.get("Momento") or "").strip().lower() == "despues"]
    expected = {
        integer(k) for k in (game.get("manifest", {}).get("roles") or {})
        if integer(k) > 0
    }
    if not expected:
        expected = {integer(t.get("Jugador")) for t in game.get("turnos.csv", [])
                    if integer(t.get("Jugador")) > 0}
    if not rows:
        return {"ronda": int(ronda), "turno": None, "jugadores": [],
                "faltantes": sorted(expected), "sin_datos": True}
    last_turn = max(integer(r.get("Turno_global")) for r in rows)
    close_rows = [r for r in rows if integer(r.get("Turno_global")) == last_turn]
    by_player = {}
    for r in close_rows:
        pid = integer(r.get("Jugador"))
        if pid > 0:
            by_player[pid] = r
    manifest = game.get("manifest", {})
    players = []
    for pid, row in sorted(by_player.items()):
        players.append({
            "jugador": pid,
            "rol": _role(manifest, pid, row),
            "etapa": _normalize_stage(row.get("Etapa")),
            "posicion": str(row.get("Posicion") or "").strip(),
            "pareja": _partner(row.get("Pareja")),
            "afinidad": row.get("Afinidad_zona") or "",
        })
    return {"ronda": int(ronda), "turno": last_turn, "jugadores": players,
            "faltantes": sorted(expected - set(by_player)), "sin_datos": False}

def _coordinates(p):
    stage, pos = p["etapa"], str(p["posicion"])
    role = p["rol"]
    # Distribuir visualmente el circuito de 6 posiciones; la numeración real
    # procede de SIMLOG, la geometría circular es un esquema topológico.
    if stage in ("Infancia", "UTN") or pos.casefold() in ("utn", "ingreso utn"):
        yc = 12.5 if role == "Clarisa" else 4.5
        if stage == "UTN" or pos.casefold() in ("utn", "ingreso utn"):
            return (10.0, yc)
        n = integer(pos, 0)
        if 1 <= n <= 6 and pos.strip().isdigit():
            theta = math.pi / 2 - (n - 1) * math.pi / 3
            return (5.4 + 2.9 * math.cos(theta),
                    yc + 2.3 * math.sin(theta))
    if stage == "Juventud":
        n = integer(pos, 0)
        if 1 <= n <= 6 and pos.strip().isdigit():
            theta = math.pi / 2 - (n - 1) * math.pi / 3
            return (17.3 + 3.0 * math.cos(theta),
                    8.5 + 5.6 * math.sin(theta))
    if stage == "Adultez":
        coordinate = _adult_coord(pos)
        if coordinate:
            row, col = coordinate
            return (25.3 + (col - 1) * 2.75,
                    14.0 - (row - 1) * 2.75)
    if stage == "Vuelo a Dublín":
        return (23.0, 1.5)
    if stage == "Casamiento":
        return (37.2, 16.0)
    return None

def _shape_ellipse(fig, x, y, size=.69, **kwargs):
    fig.add_shape(type="circle", x0=x-size, x1=x+size, y0=y-size, y1=y+size,
                  line=dict(color=kwargs.get("line", "#cbd5e1"), width=1),
                  fillcolor=kwargs.get("fill", "#f8fafc"), layer="below")

def dibujar_tablero(game: dict, ronda: int, *, height: int = 590) -> go.Figure:
    snapshot = snapshot_de_ronda(game, ronda)
    fig = go.Figure()
    fig.update_layout(
        height=height, autosize=True,
        margin=dict(l=4, r=4, t=35, b=16),
        plot_bgcolor="white", paper_bgcolor="white",
        showlegend=False,
        xaxis=dict(range=[.3, 39], visible=False, fixedrange=True),
        yaxis=dict(range=[-.2, 17.4], visible=False, fixedrange=True),
        hovermode="closest",
    )
    for (title, x, y, color) in [
        ("INFANCIA · CLARISA", 5.4, 16.3, AZUL),
        ("INFANCIA · LUCAS", 5.4, 8.1, NARANJA),
        ("JUVENTUD", 17.3, 16.3, "#475569"),
        ("ADULTEZ · 5×5", 30.8, 16.3, "#475569"),
    ]:
        fig.add_annotation(x=x, y=y, text=f"<b>{title}</b>", showarrow=False,
                           font=dict(size=12, color=color))
    for role, cy in [("Clarisa", 12.5), ("Lucas", 4.5)]:
        for pos in range(1, 7):
            theta = math.pi / 2 - (pos - 1) * math.pi / 3
            x, y = 5.4 + 2.9 * math.cos(theta), cy + 2.3 * math.sin(theta)
            _shape_ellipse(fig, x, y)
            fig.add_annotation(x=x, y=y+.46, text=str(pos), showarrow=False,
                               font=dict(size=10, color=GRIS))
        _shape_ellipse(fig, 10.0, cy, .6, fill="#fef3c7")
        fig.add_annotation(x=10.0, y=cy+.5, text="UTN", showarrow=False,
                           font=dict(size=10, color="#92400e"))
    for pos in range(1, 7):
        theta = math.pi / 2 - (pos-1) * math.pi / 3
        x, y = 17.3 + 3.0*math.cos(theta), 8.5+5.6*math.sin(theta)
        _shape_ellipse(fig, x, y, .72)
        fig.add_annotation(x=x, y=y+.46, text=str(pos), showarrow=False,
                           font=dict(size=10, color=GRIS))
    for row in range(1, 6):
        for col in range(1, 6):
            cx, cy = 25.3 + (col-1)*2.75, 14.0-(row-1)*2.75
            name = "CASA" if (row,col)==(3,3) else "PERFIL" if (row,col)==(5,3) else ""
            access = row==1 and col in (2,3,4)
            fill = "#dcfce7" if name=="CASA" else "#dbeafe" if name=="PERFIL" else "#f1f5f9" if access else "#f8fafc"
            fig.add_shape(type="rect",x0=cx-1.17,x1=cx+1.17,y0=cy-1.09,y1=cy+1.09,
                          line=dict(color="#cbd5e1",width=1),
                          fillcolor=fill,layer="below")
            label = name or (f"{row},{col}" if not access else f"{row},{col} ↑")
            fig.add_annotation(x=cx,y=cy+.74,text=label,showarrow=False,
                               font=dict(size=9,color="#64748b"))
    for x, y, label in [(23,1.5,"DUBLÍN"), (37.2,16.0,"CASAMIENTO")]:
        _shape_ellipse(fig, x, y, .85, fill="#fef3c7" if label=="DUBLÍN" else "#dcfce7")
        fig.add_annotation(x=x,y=y+1.0,text=label,showarrow=False,
                           font=dict(size=9,color="#475569"))
    locations = {}
    unplaced = []
    for p in snapshot["jugadores"]:
        coords = _coordinates(p)
        if coords is None:
            unplaced.append(p)
        else:
            locations.setdefault(coords, []).append(p)
    for (x,y), players in locations.items():
        for idx,p in enumerate(players):
            # Hasta 10 fichas pueden ocupar el mismo casillero.
            columns = 3
            dx = (idx%columns-1) * .47
            dy = (idx//columns) * -.48 + .19
            color = AZUL if p["rol"]=="Clarisa" else NARANJA if p["rol"]=="Lucas" else GRIS
            border = VERDE if p["pareja"] is not None else "#fff"
            label = ("C" if p["rol"]=="Clarisa" else "L" if p["rol"]=="Lucas" else "J")+str(p["jugador"])
            fig.add_trace(go.Scatter(
                x=[x+dx],y=[y+dy],mode="markers+text",text=[label],
                textposition="middle center",
                textfont=dict(color="white",size=10),
                marker=dict(size=26,color=color,line=dict(color=border,width=3)),
                hovertemplate=(
                    f"<b>{p['rol']} #{p['jugador']}</b><br>"
                    f"Etapa: {p['etapa']}<br>Posición: {p['posicion']}<br>"
                    f"Pareja: {p['pareja'] or 'No'}<extra></extra>"
                ),
                showlegend=False,
            ))
    return fig

def resumen_ubicaciones(snapshot: dict) -> list[dict]:
    return [{
        "Jugador": ("C" if p["rol"]=="Clarisa" else "L" if p["rol"]=="Lucas" else "J")+str(p["jugador"]),
        "Etapa": p["etapa"],
        "Posición registrada": p["posicion"] or "Sin posición",
        "Pareja": "Sí" if p["pareja"] else "No",
        "Ubicación dibujada": "Sí" if _coordinates(p) is not None else "No",
    } for p in snapshot["jugadores"]]
