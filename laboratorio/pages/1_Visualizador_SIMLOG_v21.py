"""Visualizador interactivo de partidas SIMLOG v2.1.

Página autónoma del Laboratorio de Balance. Solo lectura de trazas persistidas.
Para abrirla: streamlit run laboratorio/app.py (menú lateral SIMLOG v2.1)
o streamlit run laboratorio/pages/1_Visualizador_SIMLOG_v21.py
"""
from __future__ import annotations

import csv
import zipfile
from html import escape
from io import StringIO
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import plotly.graph_objects as go
import streamlit as st
from laboratorio.simlog_viewer_v21 import (
    CATEGORIES, CATEGORY_COLORS, CATEGORY_SYMBOLS, DEFAULT_CATEGORIES,
    STAGE_COLORS, audit, build_events, discover_games, integer, load_game,
    pair_from_manifest, role_name, stage_intervals, visible_events,
)
from laboratorio.narrativa_simlog_v21 import NOMBRES, RECURSOS, recursos_fin_ronda
from laboratorio.paneles_ronda_v21 import (
    estado_hitos, estado_noviazgo, decisiones_registradas,
    eventos_hitos_ronda, eventos_sociales_ronda,
)
from simulador.mazos_vigentes_v2 import load_current
from laboratorio.tablero_simlog_v23 import (
    snapshot_de_ronda, dibujar_tablero, resumen_ubicaciones,
    coincidencias_de_casilleros, etiqueta_jugador,
)

st.set_page_config(page_title="Visualizador SIMLOG v2.1 / v2.2 / v2.3", page_icon="📊", layout="wide")

@st.cache_data(show_spinner=False)
def catalogo_narrativo():
    return load_current()

@st.cache_data(show_spinner=False, max_entries=4)
def cached_discovery(path, zip_bytes):
    return discover_games(path, zip_bytes)

@st.cache_data(show_spinner=False, max_entries=3)
def cached_game(path, directory, zip_bytes):
    return load_game(path, directory, zip_bytes)

def prioridad_fuente(g):
    """Preferir trazas auditadas antes que copias anteriores de igual Run_ID."""
    origin = (str(g.get("source_root", "")) + "/" +
              str(g.get("directory", ""))).casefold()
    return (0 if "utn_corregido" in origin else
            1 if "duelos_corregidos" in origin else 2)


def pill_of_game(g):
    ending = "casamiento" if g["won"] else "sin victoria"
    return (f"{g.get('schema', 'SIMLOG-2.1')} · {g['size']} jugadores · Semilla {g['seed']} · "
            f"{g['rounds']} rondas · {ending} · {g['id']}")

RECURSO_ICONOS = {"A": "❤️", "P": "👤", "K": "📖", "M": "💰"}
RECURSO_ABREV = {"A": "Amor", "P": "Personal.", "K": "Conoc.", "M": "Dinero"}


def chips_recursos(cambios):
    """Indicadores accesibles: signo y nombre del recurso, además del color."""
    if cambios is None:
        return ""
    if not cambios or not any(cambios.values()):
        return '<span style="font-size:0.83rem;color:#64748b">Sin cambio de recursos</span>'
    parts = []
    for r in RECURSOS:
        n = int(cambios.get(r) or 0)
        if not n:
            continue
        color = "#166534" if n > 0 else "#991b1b"
        bg = "#dcfce7" if n > 0 else "#fee2e2"
        label = escape(f"{n:+d} {RECURSO_ICONOS[r]} {NOMBRES[r]}")
        parts.append(
            f'<span style="display:inline-block;padding:2px 7px;margin:2px 4px 2px 0;'
            f'border-radius:8px;background:{bg};color:{color};'
            f'font-weight:650;font-size:0.85rem;white-space:nowrap">'
            f'{label}</span>'
        )
    return " ".join(parts)


def panel_recursos(game, ronda, jugador):
    saldos = recursos_fin_ronda(game, ronda, jugador)
    st.caption("Recursos al finalizar la ronda · cambio respecto de la anterior")
    if saldos is None:
        st.info("SIMLOG no incluye los estados necesarios para calcular el saldo final.")
        return
    with st.container(border=True):
        cols = st.columns(4, gap="small")
        for col, r in zip(cols, RECURSOS):
            v = saldos[r]
            with col:
                st.metric(
                    f"{RECURSO_ICONOS[r]} {RECURSO_ABREV[r]}",
                    v["total"],
                    delta=f"{v['variacion']:+d}" if v["variacion"] is not None else None,
                    help=(f"{NOMBRES[r]} al cierre de la ronda: "
                          f"{v['libre']} libre + {v['reservado']} reservado. "
                          "No incluye recursos ya invertidos en proyectos."),
                )
                if v["reservado"]:
                    st.caption(f"{v['libre']} libre · {v['reservado']} reservado")
        if ronda == 1:
            st.caption("Ronda inicial: todavía no hay una ronda anterior para comparar.")


TONOS = {
    "success": ("#166534", "#dcfce7"),
    "danger": ("#991b1b", "#fee2e2"),
    "warning": ("#92400e", "#fef3c7"),
    "info": ("#1d4ed8", "#dbeafe"),
    "neutral": ("#475569", "#f1f5f9"),
}


def _pill(label, tone="neutral"):
    color, bg = TONOS.get(tone, TONOS["neutral"])
    return (
        f'<span style="color:{color};background:{bg};padding:3px 8px;'
        f'border-radius:999px;font-size:0.77rem;font-weight:700;'
        f'white-space:nowrap">{escape(str(label))}</span>'
    )


def mostrar_hitos_y_subhitos(game, ronda, jugador):
    data = estado_hitos(game, ronda, jugador)
    st.markdown("**Hitos y subhitos · estado al cierre**")
    if not data["disponible"]:
        st.caption("No se encontró un estado de jugador verificable para esta ronda.")
    boxes = []
    for item in data["hitos"]:
        description = escape(item["detalle"]) if item["detalle"] else ""
        boxes.append(
            '<div style="border:1px solid #d8dee8;border-radius:9px;'
            'padding:9px 11px;min-width:0">'
            f'<div style="font-size:.89rem;font-weight:650;margin-bottom:6px">'
            f'{escape(item["nombre"])}</div>'
            + _pill(item["estado"], item["tono"])
            + (f'<div style="font-size:.76rem;color:#64748b;margin-top:6px">'
               f'{description}</div>' if description else "")
            + '</div>'
        )
    st.markdown(
        '<div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));'
        'gap:8px;margin:7px 0 8px">'
        + "".join(boxes) + "</div>",
        unsafe_allow_html=True,
    )
    comprobantes = data["comprobantes"]
    if comprobantes:
        st.caption("Subhitos con comprobante propio")
        st.markdown(
            '<div style="display:flex;flex-wrap:wrap;gap:5px;margin-bottom:10px">'
            + "".join(_pill(f'{r["proyecto"]} · S{r["subhito"]}', "info")
                      for r in comprobantes)
            + '</div>',
            unsafe_allow_html=True,
        )


def mostrar_tarjetas_eventos(title, events, no_events, *, max_visible=4):
    st.markdown(f"**{title}**")
    if not events:
        st.caption(no_events)
        return

    def render(visible):
        cards = []
        for item in visible:
            role = item.get("participacion")
            title = escape(item["titulo"])
            detail = escape(item["descripcion"])
            role_label = (f'<span style="font-size:.76rem;color:#64748b">'
                          f' · {escape(role)}</span>' if role and role != "propio" else "")
            cards.append(
                '<div style="border:1px solid #d8dee8;border-radius:8px;'
                'padding:9px 10px;margin:6px 0">'
                '<div style="display:flex;flex-wrap:wrap;gap:6px;'
                'align-items:center;justify-content:space-between">'
                f'<div style="font-weight:650;font-size:.88rem">{title}{role_label}</div>'
                + _pill(item["estado"], item["tono"])
                + '</div>'
                f'<div style="font-size:.79rem;color:#64748b;margin-top:4px">'
                f'{detail}</div></div>'
            )
        st.markdown("".join(cards), unsafe_allow_html=True)

    render(events[:max_visible])
    if len(events) > max_visible:
        with st.expander(f"Ver {len(events) - max_visible} evento(s) más"):
            render(events[max_visible:])


def mostrar_estado_pareja(game, ronda, jugador):
    pareja = estado_noviazgo(game, ronda, jugador)
    complemento = (
        f' · Afinidad: {escape(pareja["afinidad"])}'
        if pareja.get("afinidad") else ""
    )
    st.markdown(
        '<div style="display:flex;align-items:center;flex-wrap:wrap;'
        'gap:8px;margin:4px 0 14px">'
        '<span style="font-size:.87rem;font-weight:650">Estado de pareja</span>'
        + _pill(pareja["estado"], pareja["tono"])
        + f'<span style="font-size:.83rem;color:#64748b">'
        f'{escape(pareja["detalle"])}{complemento}</span>'
        '</div>',
        unsafe_allow_html=True,
    )


def mostrar_decisiones_del_turno(game, ronda, jugador, catalogo, mostrar_opciones):
    info = decisiones_registradas(game, ronda, jugador, catalogo)
    st.markdown("**Decisiones registradas del turno**")
    if not info["turno"]:
        st.caption("No hay un turno propio registrado en esta ronda.")
        return
    move = info["movimiento"]
    if move:
        pieces = []
        if move.get("dado") not in (None, ""):
            pieces.append(f'Dado: {escape(str(move["dado"]))}')
        if move.get("carta"):
            pieces.append(f'Carta de movimiento: {escape(str(move["carta"]))}')
        if move.get("opcion") in ("A", "B"):
            pieces.append(f'Opción {move["opcion"]}')
        if move.get("inicio") is not None and move.get("fin") is not None:
            pieces.append(f'{escape(str(move["inicio"]))} → {escape(str(move["fin"]))}')
        if move.get("pasos") not in ("", None):
            pieces.append(f'Pasos: {escape(str(move["pasos"]))}')
        if move.get("descartados") not in ("", None, "0", 0):
            pieces.append(f'Descartados: {escape(str(move["descartados"]))}')
        st.markdown("**" + escape(move["tipo"]) + "** · " + " · ".join(pieces))
    card = info["carta"]
    if card is None:
        st.caption("Sin carta de Situación resuelta en este turno.")
        return
    st.markdown(f'**Carta de Situación · {escape(card["titulo"])} ({escape(card["id"])})**')
    if card["contexto"]:
        st.markdown(escape(card["contexto"]))
    selected = card.get("elegida")
    st.markdown(f'**Decisión registrada:** {escape(str(selected or "Sin elección"))}')
    if mostrar_opciones:
        for letter in ("A", "B"):
            item = card["opciones"].get(letter) or {}
            text_option = item.get("texto")
            effects = item.get("efecto_previsto")
            tag = " (elegida)" if letter == selected else ""
            st.markdown(
                f'- **Opción {letter}{tag}:** '
                f'{escape(str(text_option)) if text_option else "Texto no disponible en el catálogo"}',
            )
            if effects is not None:
                st.markdown("Efecto previsto · " + chips_recursos(effects),
                            unsafe_allow_html=True)
    if selected in ("A", "B"):
        st.markdown("**Efecto de la situación registrado en SIMLOG:** "
                    + chips_recursos(card.get("aplicado")),
                    unsafe_allow_html=True)


def event_dataframe(items, manifest):
    return [
        {
            "Ronda": e["ronda"], "Turno": e["turno"],
            "Jugador": role_name(manifest, e["jugador"]),
            "Tipo": e["categoria"], "Evento": e["evento"],
            "Detalle": e["detalle"], "Secuencia": e["secuencia"] or None,
        }
        for e in items
    ]

def build_gantt(game, items, winners, first, last, focus=None):
    fig = go.Figure()
    manifest = game["manifest"]
    y_positions = {player: len(winners) - 1 - index for index, player in enumerate(winners)}
    # Duración de cada etapa: bandas de fondo separadas por jugador.
    for player, stage, start, end in stage_intervals(game, winners):
        y = y_positions[player]
        a, b = max(first, start) - .45, min(last, end) + .45
        if b <= a:
            continue
        color = STAGE_COLORS.get(stage, "#dbe1e8")
        fig.add_shape(type="rect", x0=a, x1=b, y0=y-.43, y1=y+.43,
                      fillcolor=color, line=dict(width=0), opacity=.43,
                      layer="below")
        if b - a >= 4:
            fig.add_annotation(x=(a+b)/2, y=y+.32, text=stage,
                               showarrow=False, font=dict(size=10, color="#475569"))
    # Diferenciar eventos coincidentes en la misma ronda sin moverlos fuera de ella.
    key_total = Counter((e["jugador"], e["ronda"]) for e in items)
    key_seen = defaultdict(int)
    offset = {cat: (idx - (len(CATEGORIES)-1)/2) * .052
              for idx, cat in enumerate(CATEGORIES)}
    series = defaultdict(lambda: dict(x=[], y=[], custom=[]))
    for e in items:
        k = e["jugador"], e["ronda"]
        number = key_seen[k]
        key_seen[k] += 1
        total = key_total[k]
        shift = (number - (total - 1)/2) * min(.085, .80/max(total, 1))
        category = e["categoria"]
        series[category]["x"].append(e["ronda"] + shift)
        series[category]["y"].append(y_positions[e["jugador"]] + offset[category])
        series[category]["custom"].append([
            str(e["ronda"]), role_name(manifest, e["jugador"]),
            escape(str(e["evento"])), escape(e["detalle"][:550]),
            str(e["turno"] or "—"), str(e["secuencia"] or "—"),
        ])
    for category in CATEGORIES:
        values = series.get(category)
        if not values:
            continue
        fig.add_trace(go.Scatter(
            x=values["x"], y=values["y"], customdata=values["custom"],
            mode="markers", name=category,
            marker=dict(size=13, color=CATEGORY_COLORS[category],
                        symbol=CATEGORY_SYMBOLS[category],
                        line=dict(color="#ffffff", width=1)),
            hovertemplate=(
                "<b>%{customdata[2]}</b><br>"
                "Ronda %{customdata[0]} · %{customdata[1]}<br>"
                "Turno %{customdata[4]} · Evento #%{customdata[5]}<br>"
                "%{customdata[3]}<extra>" + category + "</extra>"
            ),
        ))
    if focus is not None:
        fig.add_vline(x=focus, line_width=1, line_dash="dot", line_color="#0f172a")
    fig.update_layout(
        title=None, height=max(490, 150*len(winners)+150), margin=dict(l=20, r=20, t=12, b=65),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", y=-.26, x=0, font=dict(size=11)),
        hovermode="closest", dragmode="pan",
        xaxis=dict(title="Ronda", range=[first-.5, last+.5],
                   tickmode="linear", dtick=1 if last-first <= 20 else 5,
                   gridcolor="rgba(100,116,139,.13)",
                   rangeslider=dict(visible=True, thickness=.11)),
        yaxis=dict(title=None, range=[-.65, len(winners)-.35],
                   tickmode="array",
                   tickvals=[y_positions[p] for p in winners],
                   ticktext=[role_name(manifest, p) for p in winners],
                   showgrid=False, zeroline=False),
    )
    return fig

def plot_resource(game, winners, letter, free):
    fig = go.Figure()
    key = f"{letter}_{'libre_despues' if free else 'despues'}"
    for p in winners:
        rows = sorted([t for t in game["turnos.csv"]
                       if integer(t.get("Jugador")) == p],
                      key=lambda t: integer(t.get("Ronda")))
        xs = [integer(t["Ronda"]) for t in rows if t.get(key) not in (None,"")]
        ys = [integer(t[key]) for t in rows if t.get(key) not in (None,"")]
        fig.add_trace(go.Scatter(x=xs, y=ys, name=role_name(game["manifest"], p),
                                 mode="lines+markers", line_shape="hv"))
    fig.update_layout(height=370, margin=dict(l=18,r=20,t=8,b=45),
                      xaxis_title="Ronda", yaxis_title="Fichas",
                      hovermode="x unified")
    return fig

def plot_affinity(game, winners):
    fig = go.Figure()
    for p in winners:
        rows = sorted([t for t in game["turnos.csv"]
                       if integer(t.get("Jugador")) == p
                       and t.get("Afinidad_posicion_despues") not in (None, "")],
                      key=lambda t: integer(t.get("Ronda")))
        if rows:
            fig.add_trace(go.Scatter(
                x=[integer(t["Ronda"]) for t in rows],
                y=[integer(t["Afinidad_posicion_despues"]) for t in rows],
                mode="lines+markers", name=role_name(game["manifest"], p),
                line_shape="hv",
                customdata=[[t.get("Afinidad_zona_despues"),
                             t.get("Pareja_compatible_despues")] for t in rows],
                hovertemplate="Ronda %{x} · Posición %{y}<br>"
                              "Zona %{customdata[0]} · Compatible %{customdata[1]}<extra>%{fullData.name}</extra>",
            ))
    fig.add_hrect(y0=-2, y1=2, line_width=0, fillcolor="#94a3b8", opacity=.12)
    fig.add_hline(y=-2, line_dash="dash", line_color="#64748b")
    fig.add_hline(y=2, line_dash="dash", line_color="#64748b")
    fig.update_layout(height=390, margin=dict(l=20,r=20,t=8,b=45),
                      xaxis_title="Ronda", yaxis_title="Posición de afinidad",
                      hovermode="x unified")
    return fig


# -------- Inspección de una sola ronda: controles fijos y vistas compactas -------


def mostrar_coincidencias_tablero(snapshot):
    """Desglosa las ocupaciones múltiples; no reconstruye posiciones ni parejas."""
    coincidencias = coincidencias_de_casilleros(snapshot)
    if not coincidencias:
        st.caption("Sin casilleros compartidos por varias fichas en esta ronda.")
        return
    st.markdown(f"**Casilleros compartidos ({len(coincidencias)})**")
    cards = []
    for item in coincidencias:
        title = (f"{item['etapa'].upper()} · CASILLERO "
                 f"{item['posicion'] or '?'} · RONDA {item['ronda']}")
        groups = []
        pair_number = 0
        for group in item["grupos"]:
            is_pair = group["tipo"] == "pareja"
            if is_pair:
                pair_number += 1
            people = []
            for person in group["miembros"]:
                color = "#1d4ed8" if person["rol"] == "Clarisa" else (
                    "#c2410c" if person["rol"] == "Lucas" else "#475569"
                )
                people.append(
                    '<span style="font-weight:750;color:' + color +
                    ';font-size:.84rem;white-space:nowrap">' +
                    escape(etiqueta_jugador(person)) + '</span>'
                )
            label = f"Pareja {pair_number}" if is_pair else "Otra ficha"
            groups.append(
                '<div style="display:flex;align-items:center;gap:7px;'
                'padding:5px 8px;border-radius:7px;background:' +
                ('#ecfdf5' if is_pair else '#f1f5f9') +
                ';border:1px solid ' +
                ('#86efac' if is_pair else '#cbd5e1') + '">'
                + '<span style="font-size:.76rem;min-width:56px;color:#475569">'
                + escape(label) + '</span>'
                + '<span style="display:flex;flex-wrap:wrap;gap:8px">'
                + ''.join(people) + '</span></div>'
            )
        cards.append(
            '<div style="border:1px solid #cbd5e1;border-radius:10px;'
            'padding:9px 10px;min-width:0">'
            '<div style="font-size:.78rem;font-weight:750;'
            'margin-bottom:7px;color:#334155">' + escape(title) + '</div>'
            '<div style="display:grid;gap:5px">'
            + ''.join(groups) + '</div></div>'
        )
    st.markdown(
        '<div style="display:grid;grid-template-columns:'
        'repeat(auto-fit,minmax(235px,1fr));gap:8px;margin-bottom:8px">'
        + ''.join(cards) + '</div>',
        unsafe_allow_html=True,
    )
    st.caption("P1, P2, etc. identifican grupos solo en este casillero; "
               "las parejas se determinan exclusivamente a partir del vínculo "
               "recíproco registrado en SIMLOG.")


def _navegar_ronda(delta, max_round):
    actual = integer(st.session_state.get("selected_round_v21"), 1)
    st.session_state["selected_round_v21"] = min(max_round, max(1, actual + delta))


def _etiqueta_evento(item):
    estado = str(item.get("estado") or "")
    titulo = str(item.get("titulo") or "")
    descripcion = str(item.get("descripcion") or "")
    return (
        f'<li><strong>{escape(titulo)}</strong> '
        f'<span style="color:#64748b">({escape(estado)})</span>'
        + (f'<div class="inspector-secondary">{escape(descripcion)}</div>'
           if descripcion else "") + "</li>"
    )


def resumen_compacto_jugador(game, ronda, pid, catalogo, snapshot):
    """La síntesis solo usa asientos SIMLOG y el estado efectivo de cierre."""
    manifest = game["manifest"]
    datos = next((x for x in snapshot["jugadores"] if x["jugador"] == pid), None)
    etapa = datos["etapa"] if datos else "Sin estado"
    pareja = estado_noviazgo(game, ronda, pid)
    saldos = recursos_fin_ronda(game, ronda, pid)
    hitos = estado_hitos(game, ronda, pid)
    avances = eventos_hitos_ronda(game, ronda, pid)
    sociales = eventos_sociales_ronda(game, ronda, pid)
    decisiones = decisiones_registradas(game, ronda, pid, catalogo)
    resource_cells = []
    for letter in RECURSOS:
        val = (saldos or {}).get(letter)
        total = str(val["total"]) if val else "—"
        delta = val.get("variacion") if val else None
        variation = f'{delta:+d}' if delta is not None else "—"
        resource_cells.append(
            f'<div class="inspector-resource"><small>'
            f'{RECURSO_ICONOS[letter]} {escape(RECURSO_ABREV[letter])}</small>'
            f'<b>{total}</b><span>{variation}</span></div>'
        )
    achievements = "".join(
        f'<span class="inspector-hito">{escape(h["nombre"])}: '
        f'<strong>{escape(h["estado"])}</strong></span>'
        for h in hitos["hitos"]
    )
    movement = decisiones.get("movimiento") or {}
    card = decisiones.get("carta") or {}
    fragments = []
    if movement.get("dado") not in ("", None):
        fragments.append(f'D6 {escape(str(movement["dado"]))}')
    if movement.get("carta"):
        fragments.append(f'Mov. {escape(str(movement["carta"]))}')
    if movement.get("inicio") not in ("", None) and movement.get("fin") not in ("", None):
        fragments.append(f'{escape(str(movement["inicio"]))} → {escape(str(movement["fin"]))}')
    if card:
        fragments.append(f'Situación {escape(str(card.get("id") or ""))}: '
                         f'{escape(str(card.get("elegida") or "—"))}')
    mov_text = " · ".join(fragments) or "Sin decisión de movimiento registrada"
    no = '<span class="inspector-muted">Sin eventos registrados</span>'
    advances = "<ul>" + "".join(_etiqueta_evento(e) for e in avances[:3]) + "</ul>" if avances else no
    social = "<ul>" + "".join(_etiqueta_evento(e) for e in sociales[:3]) + "</ul>" if sociales else no
    extra = len(avances) + len(sociales) - min(3,len(avances)) - min(3,len(sociales))
    if extra:
        social += f'<div class="inspector-secondary">+{extra} eventos en la vista Detalle</div>'
    st.markdown(
        '<section class="inspector-player">'
        f'<div class="inspector-person-header"><strong>{escape(role_name(manifest,pid))}'
        f'</strong><span>{escape(etapa)} · {escape(pareja["estado"])}'
        f' · {escape(str(pareja.get("afinidad") or ""))}</span></div>'
        '<div class="inspector-resources">' + "".join(resource_cells) + '</div>'
        '<div class="inspector-hitos">' + achievements + '</div>'
        f'<div class="inspector-movement">{mov_text}</div>'
        '<div class="inspector-event-grid">'
        '<div><strong>Hitos e inversiones de la ronda</strong>' + advances + '</div>'
        '<div><strong>Interacciones sociales</strong>' + social + '</div>'
        '</div></section>', unsafe_allow_html=True,
    )


def _inspector_css():
    st.markdown("""
    <style>
    html, body, #root, [data-testid="stApp"] {
        height:100dvh !important; overflow:hidden !important;
    }
    [data-testid="stHeader"] {display:none !important;}
    [data-testid="stMain"] {overflow:hidden !important;}
    .block-container {max-width:100% !important;padding:0 !important;}
    .st-key-viewer_selection {display:none !important;}
    .st-key-inspector_header {
        position:fixed !important;top:0 !important;left:0 !important;
        right:0 !important;z-index:10010 !important;
        padding:.38rem .8rem !important;
        box-sizing:border-box !important;
        background:var(--background-color,#fff) !important;
        border-bottom:1px solid #cbd5e1;
        box-shadow:0 2px 8px rgba(0,0,0,.07);
    }
    .st-key-inspector_header [data-testid="stVerticalBlock"] {gap:.2rem !important;}
    .st-key-inspector_header [data-testid="stMarkdownContainer"] p {margin:0 !important;}
    .st-key-inspector_content {
        position:fixed !important;top:78px !important;bottom:0 !important;
        left:0 !important;right:0 !important;z-index:10000 !important;
        overflow-y:auto !important;overflow-x:hidden !important;
        overscroll-behavior:contain;
        background:var(--background-color,#fff) !important;
        padding:.25rem 1rem 2rem !important;
        box-sizing:border-box !important;
        scrollbar-gutter:stable;
    }
    .st-key-inspector_content [data-testid="stVerticalBlock"] {gap:.4rem !important;}
    .inspector-player {
        border:1px solid #dbe2ea;border-radius:10px;
        padding:9px 12px;margin:3px 0;
    }
    .inspector-person-header {display:flex;align-items:center;gap:14px;}
    .inspector-person-header strong {font-size:1.05rem;}
    .inspector-person-header span,.inspector-secondary,.inspector-muted {
        font-size:.79rem;color:#64748b;
    }
    .inspector-resources {
        display:grid;grid-template-columns:repeat(4,minmax(0,1fr));
        gap:5px;margin:8px 0;
    }
    .inspector-resource {background:#f1f5f9;border-radius:6px;
        padding:3px 7px;display:flex;align-items:center;gap:5px;}
    .inspector-resource small {font-size:.70rem;color:#64748b;}
    .inspector-resource b {font-size:1.25rem;}
    .inspector-resource span {margin-left:auto;font-size:.70rem;color:#166534;}
    .inspector-hitos {display:flex;gap:4px;flex-wrap:wrap;}
    .inspector-hito {font-size:.74rem;border:1px solid #dbe2ea;
        padding:2px 6px;border-radius:5px;}
    .inspector-movement {font-size:.80rem;margin-top:7px;
        border-top:1px solid #e2e8f0;padding-top:5px;}
    .inspector-event-grid {display:grid;grid-template-columns:1fr 1fr;
        gap:12px;margin-top:7px;font-size:.81rem;}
    .inspector-event-grid ul {margin:3px 0 0 0;padding-left:17px;}
    .inspector-event-grid > div > strong {display:block;margin-bottom:3px;}
    .inspector-event-grid .inspector-muted {display:block;}
    .inspector-event-grid li {margin-bottom:3px;}
    @media (max-width:850px) {
        .st-key-inspector_content {top:126px !important;padding:5px .5rem !important;}
        .inspector-event-grid {grid-template-columns:1fr;}
        .inspector-resources {grid-template-columns:repeat(2,minmax(0,1fr));}
    }
    </style>
    """, unsafe_allow_html=True)


def pantalla_inspeccion(game, selected, ids, winners, max_round):
    """Una única navegación compartida por Resumen, Detalle y Tablero."""
    _inspector_css()
    if "selected_round_v21" not in st.session_state or not (
        1 <= integer(st.session_state["selected_round_v21"]) <= max_round
    ):
        st.session_state["selected_round_v21"] = 1
    with st.container(key="inspector_header"):
        titulo, prev, num, nxt, vista, salir = st.columns(
            [2.4,.56,1.20,.56,3.3,.65], vertical_alignment="center")
        with titulo:
            st.markdown(
                f"**{escape(str(selected['schema']))} · "
                f"{selected['size']} jugadores · Semilla {selected['seed']}**")
        with prev:
            st.button("◀", key="ins_prev", help="Ronda anterior",
                      disabled=st.session_state["selected_round_v21"] <= 1,
                      on_click=_navegar_ronda, args=(-1,max_round))
        with num:
            st.number_input("Ronda", min_value=1,max_value=max_round,step=1,
                            key="selected_round_v21", label_visibility="collapsed")
        with nxt:
            st.button("▶", key="ins_next", help="Ronda siguiente",
                      disabled=st.session_state["selected_round_v21"] >= max_round,
                      on_click=_navegar_ronda, args=(1,max_round))
        with vista:
            modo = st.radio("Vista de inspección", ["Resumen","Detalle","Tablero"],
                            horizontal=True,key="inspector_vista_simlog",
                            label_visibility="collapsed")
        with salir:
            if st.button("Salir",key="ins_salir",help="Volver al visualizador"):
                st.session_state["inspector_simlog"] = False
                st.rerun()
    ronda = st.session_state["selected_round_v21"]
    snapshot = snapshot_de_ronda(game, ronda)
    with st.container(key="inspector_content"):
        if modo == "Tablero":
            st.caption(f"Ubicaciones al cierre de la ronda {ronda} · "
                       f"último turno global {snapshot['turno'] or 'sin datos'}. "
                       "Los circuitos se representan esquemáticamente.")
            if snapshot["sin_datos"]:
                st.warning("Esta traza no incluye estados de jugadores para la ronda indicada.")
            else:
                st.plotly_chart(dibujar_tablero(game,ronda,height=590),
                                use_container_width=True,
                                config={"displaylogo":False,"responsive":True})
                mostrar_coincidencias_tablero(snapshot)
                missing = snapshot["faltantes"]
                unplaced = [p for p in resumen_ubicaciones(snapshot)
                            if p["Ubicación dibujada"] == "No"]
                if missing:
                    st.warning(f"Faltan estados del cierre para: {', '.join(map(str, missing))}")
                if unplaced:
                    st.warning("Hay posiciones no dibujadas porque la traza no "
                               "contiene una coordenada reconocible.")
                st.dataframe(resumen_ubicaciones(snapshot),
                             use_container_width=True,hide_index=True)
            return
        try:
            catalogo = catalogo_narrativo()
        except (OSError, ValueError, AssertionError):
            catalogo = {}
        if modo == "Resumen":
            st.caption(f"Ronda {ronda} · Recursos al cierre · "
                       "Eventos observados · Elegí Detalle para consultar la traza completa.")
            for inicio in range(0,len(winners),2):
                columns=st.columns(2,gap="small")
                for col,pid in zip(columns,winners[inicio:inicio+2]):
                    with col:
                        resumen_compacto_jugador(game,ronda,pid,catalogo,snapshot)
        else:
            show_options=st.toggle("Mostrar opciones A/B de las cartas",
                                   value=False,key="inspector_opciones_ab")
            for inicio in range(0,len(winners),2):
                columns=st.columns(2,gap="small")
                for col,pid in zip(columns,winners[inicio:inicio+2]):
                    with col:
                        st.markdown(f"**{role_name(game['manifest'],pid)}**")
                        mostrar_estado_pareja(game,ronda,pid)
                        panel_recursos(game,ronda,pid)
                        mostrar_hitos_y_subhitos(game,ronda,pid)
                        mostrar_tarjetas_eventos(
                            "Avances de esta ronda",eventos_hitos_ronda(game,ronda,pid),
                            "No hay inversiones o adjudicaciones registradas.")
                        mostrar_tarjetas_eventos(
                            "Interacciones y eventos",eventos_sociales_ronda(game,ronda,pid),
                            "No hay interacciones registradas.")
                        mostrar_decisiones_del_turno(
                            game,ronda,pid,catalogo,show_options)


with st.container(key="viewer_selection"):
    st.title("Visualizador de partidas · SIMLOG v2.1 / v2.2 / v2.3")
    st.caption("Decisiones y eventos SIMLOG v2.1/v2.2/v2.3 por partida y jugadores seleccionados. "
               "Solo lectura: no modifica simulaciones ni inventa resultados.")

    with st.expander("Origen de los datos · carpetas y ZIP SIMLOG v2.1/v2.2/v2.3", expanded=False):
        src1, src2 = st.columns([2.4, 1.5], vertical_alignment="bottom")
        with src1:
            root_path = st.text_input(
                "Carpeta principal de resultados",
                value=os.environ.get("SIMLOG_RESULTS_ROOT", str(ROOT / "resultados")),
                help="Se buscan de forma recursiva TODAS las partidas SIMLOG v2.1/v2.2/v2.3 "
                     "de esta carpeta, sin limitar semillas ni tamaño de mesa.")
        with src2:
            uploaded = st.file_uploader(
                "Agregar ZIP de trazas", type=["zip"],
                help="Las partidas del ZIP se suman a las de las carpetas locales.")
        extra_roots = st.text_area(
            "Otras carpetas de simulaciones (opcional, una ruta por línea)",
            value="", height=78, placeholder="/ruta/a/otra/corrida",
            help="Se suman al índice, incluso cuando están fuera de resultados/.")
        st.caption("También se detectan automáticamente los ZIP SIMLOG guardados "
                   "en Descargas (Downloads) y en la carpeta de resultados, "
                   "sin necesidad de extraerlos.")
        st.button(
            "Actualizar listado de partidas",
            on_click=lambda: (cached_discovery.clear(), cached_game.clear()),
            help="Volvé a buscar archivos nuevos o modificados, sin reiniciar el laboratorio.")
        zip_bytes = uploaded.getvalue() if uploaded is not None else None
        if zip_bytes is not None and len(zip_bytes) > 120_000_000:
            st.error("ZIP demasiado grande (>120 MB). Usá una carpeta local.")
            st.stop()

    roots = list(dict.fromkeys(
        [root_path] + [p.strip() for p in extra_roots.splitlines() if p.strip()]
    ))
    games = []
    try:
        for source_root in roots:
            for g in cached_discovery(source_root, None):
                games.append({**g, "source_root": source_root, "source_type": "carpeta"})
        # Buscar archivos ZIP de corridas ya ejecutadas; no generar partidas nuevas.
        auto_zips = set()
        downloads = Path.home() / "Downloads"
        if downloads.is_dir():
            auto_zips.update(downloads.glob("SIMLOG*.zip"))
        result_dir = Path(root_path).expanduser()
        if result_dir.is_dir():
            auto_zips.update(result_dir.rglob("SIMLOG*.zip"))
        for extra in roots[1:]:
            folder = Path(extra).expanduser()
            if folder.is_dir():
                auto_zips.update(folder.rglob("SIMLOG*.zip"))
        for local_zip in sorted(auto_zips):
            if not local_zip.is_file() or local_zip.stat().st_size > 150_000_000:
                continue
            try:
                for g in cached_discovery(str(local_zip), None):
                    games.append({**g, "source_root": str(local_zip),
                                  "source_type": "ZIP local"})
            except (OSError, ValueError, zipfile.BadZipFile):
                continue
        if zip_bytes is not None:
            for g in cached_discovery(root_path, zip_bytes):
                games.append({**g, "source_root": root_path, "source_type": "ZIP"})
    except (ValueError, OSError, KeyError) as exc:
        st.error(f"No se pudo leer la fuente SIMLOG: {exc}")
        st.stop()
    # La misma traza puede estar copiada en Descargas y también en resultados.
    # Se muestran una sola vez los Run_ID idénticos, preservando corridas distintas.
    # La misma semilla puede existir en una corrida previa y otra corregida.
    # Para Run_ID idénticos se conserva primero la fuente UTN corregida.
    games.sort(key=lambda g: (prioridad_fuente(g), g["schema"]))
    seen_runs = set()
    unique_games = []
    for g in games:
        identity = (g["id"], g["size"], g["seed"], g["rounds"])
        if identity not in seen_runs:
            seen_runs.add(identity)
            unique_games.append(g)
    games = unique_games
    games.sort(key=lambda g: (
        {"SIMLOG-2.3": 0, "SIMLOG-2.2": 1, "SIMLOG-2.1": 2}.get(g["schema"], 3),
        prioridad_fuente(g), g["size"], g["seed"], g["id"], g["directory"],
    ))
    if not games:
        st.info("No se encontraron trazas completas SIMLOG v2.1/v2.2/v2.3 compatibles. "
                "Buscá otras carpetas o agregá un ZIP de partidas. "
                "El historial v1.3 y las simulaciones anteriores sin SIMLOG v2.1 "
                "no permiten reconstruir estos eventos por ronda.")
        st.stop()

    winners_count = sum(g["won"] for g in games)
    six_count = sum(g["size"] == 6 for g in games)
    ten_count = sum(g["size"] == 10 for g in games)
    st.caption(
        f"**{len(games)} simulaciones SIMLOG v2.1/v2.2/v2.3 encontradas** · "
        f"{winners_count} con casamiento · {len(games)-winners_count} sin ganador · "
        f"{six_count} de 6 jugadores · {ten_count} de 10 jugadores. "
        "Se incluyen todos los archivos compatibles encontrados en las fuentes seleccionadas."
    )

    versiones = [v for v in ("SIMLOG-2.3", "SIMLOG-2.2", "SIMLOG-2.1")
                 if any(g["schema"] == v for g in games)]
    if "SIMLOG-2.3" not in versiones:
        st.warning(
            "Todavía no se encontraron trazas **SIMLOG-2.3**. La versión 2.2 que "
            "aparece en el selector es anterior. Descargá los artefactos de trazas "
            "v2.3 (6 y 10 jugadores) desde "
            "[GitHub Actions #42933927583]"
            "(https://github.com/stgo-rodriguez/juego-clarisa-lucas/actions/runs/42933927583), "
            "guardalos como ZIP en Descargas y pulsá 'Actualizar listado de partidas'."
        )
    vcol, mcol, woncol = st.columns([1.6, 1.1, 1.6], vertical_alignment="bottom")
    with vcol:
        version_elegida = st.selectbox("Versión SIMLOG", versiones + ["Todas"],
                                      index=0, key="simlog_filtro_version")
    with mcol:
        mesa_elegida = st.selectbox("Mesa", ["Todas", "6 jugadores", "10 jugadores"],
                                   key="simlog_filtro_mesa")
    with woncol:
        only_won = st.checkbox("Solo partidas con casamiento", value=False)
    available = [
        g for g in games
        if (version_elegida == "Todas" or g["schema"] == version_elegida)
        and (mesa_elegida == "Todas" or g["size"] == int(mesa_elegida.split()[0]))
        and (not only_won or g["won"])
    ]
    if not available:
        st.warning("No hay partidas que cumplan los filtros seleccionados.")
        st.stop()
    b, c = st.columns([5, 1], vertical_alignment="bottom")
    with b:
        selected = st.selectbox(
            "Seleccionar partida", available,
            format_func=lambda g: (
                pill_of_game(g) +
                (" · UTN corregida" if prioridad_fuente(g) == 0 else "") +
                f" · {g['source_type']}: "
                + (Path(g["directory"]).parent.parent.name
                   if g["source_type"] == "carpeta" else
                   Path(g["source_root"]).name if g["source_type"] == "ZIP local"
                   else g["directory"])
            ),
        )
    with c:
        st.caption(f"{len(available)} partidas seleccionables")

    try:
        game = cached_game(
            selected["source_root"], selected["directory"],
            zip_bytes if selected["source_type"] == "ZIP" else None,
        )
    except (ValueError, OSError, KeyError) as exc:
        st.error(f"No se pudo abrir la partida: {exc}")
        st.stop()

    manifest = game["manifest"]
    pair = pair_from_manifest(manifest)
    ids = sorted({
        int(pid) for pid in (manifest.get("roles") or {}) if str(pid).isdigit()
    } | {integer(t.get("Jugador")) for t in game["turnos.csv"] if integer(t.get("Jugador")) > 0})
    if not ids:
        st.warning("La partida no registra jugadores para seguir.")
        st.stop()
    if pair:
        defaults = [pid for pid in pair if pid in ids]
    else:
        first_clarisa = next((p for p in ids
                              if (manifest.get("roles") or {}).get(str(p)) == "Clarisa"), None)
        first_lucas = next((p for p in ids
                            if (manifest.get("roles") or {}).get(str(p)) == "Lucas"), None)
        defaults = [p for p in (first_clarisa, first_lucas) if p is not None]
    if not defaults:
        defaults = ids[:2]

    winners = st.multiselect(
        "Jugadores a recorrer en el Gantt y en Ronda a ronda",
        options=ids, default=defaults,
        key=f"players_{selected['source_type']}_{selected['directory']}",
        format_func=lambda pid: role_name(manifest, pid),
        help="Las partidas sin casamiento también pueden recorrerse. "
             "El selector no presenta a esos jugadores como ganadores.",
    )
    if not winners:
        st.warning("Seleccioná al menos un jugador para mostrar los eventos.")
        st.stop()

    items = build_events(game, winners)
    max_round = max(1, selected["rounds"],
                    max((integer(t.get("Ronda")) for t in game["turnos.csv"]), default=1))

    if st.button("Abrir inspección de rondas y tablero", type="primary",
                 key="abrir_inspector_simlog"):
        st.session_state["inspector_simlog"] = True
        st.rerun()
if st.session_state.get("inspector_simlog"):
    pantalla_inspeccion(game,selected,ids,winners,max_round)
    st.stop()

st.caption(
    f"**Partida:** {selected['id']} · **Mesa:** {selected['size']} jugadores · "
    f"**Resultado:** {'Casamiento' if selected['won'] else 'Sin ganador registrado'} · "
    f"**Jugadores observados:** {' + '.join(role_name(manifest,p) for p in winners)} · "
    f"**Rondas:** {max_round} · **Semilla:** {selected['seed']}"
)
if not selected["won"]:
    st.caption("Partida sin casamiento: se presentan acciones de los jugadores seleccionados, "
               "sin atribuirles una victoria.")

with st.container(border=True):
    left, mid, right = st.columns([4.3, 2.3, 1.2], vertical_alignment="bottom")
    with left:
        categories = st.multiselect(
            "Eventos visibles",
            options=list(CATEGORIES), default=list(DEFAULT_CATEGORIES),
            help="Cada categoría corresponde a eventos realmente registrados. "
                 "Recursos y Otros están ocultos inicialmente por volumen.")
    with mid:
        low, high = st.slider("Intervalo de rondas", min_value=1, max_value=max_round,
                              value=(1, max_round), key=f"window_{selected['source_type']}_{selected['directory']}")
    with right:
        st.button("Ver todo", use_container_width=True,
                  on_click=lambda: st.session_state.update(
                      {f"window_{selected['source_type']}_{selected['directory']}": (1, max_round)}))

filtered = visible_events(items, categories, low, high)
distinct_events = len({
    (x["turno"], x["secuencia"], x["categoria"], x["evento"])
    for x in filtered
})
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Rondas", max_round)
m2.metric("Eventos visibles", len(filtered))
m3.metric("Acciones únicas", distinct_events)
m4.metric("Duelos registrados", len({
    x["secuencia"] for x in items if x["categoria"] == "Duelos"
}))
m5.metric("Decisiones A/B", sum(x["categoria"] == "Situación A/B" for x in items))

tabs = st.tabs(["Gantt", "Ronda a ronda", "Economía",
                "Interacciones", "Afinidad", "Auditoría", "Tablero"])

with tabs[0]:
    st.plotly_chart(build_gantt(game, filtered, winners, low, high),
                    use_container_width=True, config={"scrollZoom": True, "displaylogo": False})
    st.caption("Las bandas indican etapas observadas; los símbolos, acciones en rondas "
               "concretas. Arrastrá para recorrer, usá la rueda para zoom y el "
               "minimapa inferior para cambiar de tramo. "
               "Los símbolos se desplazan mínimamente dentro de su ronda para evitar superposiciones.")
    st.subheader("Eventos del intervalo")
    st.dataframe(event_dataframe(filtered, manifest), use_container_width=True,
                 hide_index=True, height=330)
    export_buffer = StringIO()
    cols = ["Ronda", "Turno", "Jugador", "Tipo", "Evento", "Detalle", "Secuencia"]
    writer = csv.DictWriter(export_buffer, fieldnames=cols)
    writer.writeheader()
    writer.writerows(event_dataframe(filtered, manifest))
    st.download_button("Exportar eventos filtrados (CSV)",
                       export_buffer.getvalue().encode("utf-8-sig"),
                       file_name=f"eventos_ganadores_{selected['seed']}.csv", mime="text/csv")

with tabs[1]:
    if st.button("Abrir vista compacta con navegación fija y Tablero",
                 key="inspector_desde_ronda"):
        st.session_state["inspector_simlog"] = True
        st.rerun()
    if "selected_round_v21" not in st.session_state or st.session_state["selected_round_v21"] > max_round:
        st.session_state["selected_round_v21"] = low
    rcol1, rcol2, rcol3 = st.columns([1, 4, 1], vertical_alignment="bottom")
    with rcol1:
        if st.button("← Anterior", disabled=st.session_state["selected_round_v21"] <= 1):
            st.session_state["selected_round_v21"] -= 1
            st.rerun()
    with rcol2:
        chosen_round = st.number_input(
            "Ronda a inspeccionar", min_value=1, max_value=max_round,
            step=1, key="selected_round_v21")
    with rcol3:
        if st.button("Siguiente →", disabled=st.session_state["selected_round_v21"] >= max_round):
            st.session_state["selected_round_v21"] += 1
            st.rerun()
    st.caption("Información extraída de los estados, turnos y eventos SIMLOG de esta "
               "ronda. Las opciones A/B provienen del catálogo vigente; "
               "los efectos aplicados provienen de los asientos de SIMLOG.")
    mostrar_opciones = st.toggle(
        "Mostrar las dos opciones A/B y sus efectos previstos",
        value=True, key="mostrar_opciones_estructuradas",
    )
    try:
        catalogo = catalogo_narrativo()
    except (OSError, ValueError, AssertionError) as exc:
        st.warning(f"El catálogo de cartas no está disponible: {exc}. "
                   "Solo se mostrarán los valores registrados en SIMLOG.")
        catalogo = {}
    cards = st.columns(2, gap="large")
    for index, pid in enumerate(winners):
        own_turns = [
            t for t in game["turnos.csv"]
            if integer(t.get("Jugador")) == pid
            and integer(t.get("Ronda")) == chosen_round
        ]
        stage = own_turns[0].get("Etapa_antes") if own_turns else "Sin turno registrado"
        with cards[index % 2]:
            st.subheader(f"{role_name(manifest,pid)} · {stage}")
            mostrar_estado_pareja(game, chosen_round, pid)
            panel_recursos(game, chosen_round, pid)
            mostrar_hitos_y_subhitos(game, chosen_round, pid)
            mostrar_tarjetas_eventos(
                "Avances de esta ronda",
                eventos_hitos_ronda(game, chosen_round, pid),
                "Sin inversiones, adjudicaciones ni cambios de hitos registrados.",
            )
            mostrar_tarjetas_eventos(
                "Interacciones y eventos sociales",
                eventos_sociales_ronda(game, chosen_round, pid),
                "Sin duelos, propuestas ni transferencias registrados en esta ronda.",
            )
            mostrar_decisiones_del_turno(
                game, chosen_round, pid, catalogo, mostrar_opciones,
            )
            if own_turns:
                with st.expander("Ver registro técnico del turno"):
                    st.json(own_turns[0])
            st.divider()
    round_events = [e for e in items if e["ronda"] == chosen_round and e["categoria"] in categories]
    st.markdown(f"**Eventos observados en la ronda {chosen_round} ({len(round_events)})**")
    st.dataframe(event_dataframe(round_events, manifest), use_container_width=True,
                 hide_index=True, height=270)
    with st.expander("Detalle JSON de los eventos de esta ronda"):
        st.json(round_events)

with tabs[2]:
    st.caption("Saldos después del turno de cada jugador observado. "
               "Un movimiento de un tercero puede reflejarse recién en el siguiente turno del jugador.")
    ec1, ec2 = st.columns(2)
    with ec1:
        resource = st.selectbox("Recurso", ["A · Amor", "P · Personalidad",
                                           "K · Conocimiento", "M · Dinero"])
    with ec2:
        free = st.radio("Tipo de saldo", ["Libre", "Total (libre + reservas)"],
                        horizontal=True) == "Libre"
    st.plotly_chart(plot_resource(game, winners, resource[0], free),
                    use_container_width=True)
    economic = [e for e in items if e["categoria"] in ("Recursos", "Canjes", "Subhitos")
                and low <= e["ronda"] <= high]
    st.dataframe(event_dataframe(economic, manifest), use_container_width=True,
                 hide_index=True, height=290)

with tabs[3]:
    st.caption("Interacciones consumadas y propuestas expresamente registradas. "
               "No se reconstruyen ofertas ni intentos que el motor no emitió.")
    social = [e for e in items if e["categoria"] in ("Duelos", "Noviazgo", "Acuerdos",
                                                   "Subhitos", "Hitos")
              and low <= e["ronda"] <= high]
    social_count = {cat: len({(e["secuencia"], e["turno"], e["evento"]) for e in social
                              if e["categoria"] == cat}) for cat in CATEGORIES}
    st.markdown(" · ".join(f"**{cat}:** {social_count[cat]}" for cat in
                         ("Duelos", "Noviazgo", "Acuerdos", "Subhitos", "Hitos")))
    st.dataframe(event_dataframe(social, manifest), use_container_width=True,
                 hide_index=True, height=430)

with tabs[4]:
    st.caption("Eje A–Neutro–B (zona Neutro entre −2 y +2). "
               "Cada punto procede de los estados de SIMLOG al terminar el turno.")
    st.plotly_chart(plot_affinity(game, winners), use_container_width=True)
    focus = [t for t in game["turnos.csv"]
             if integer(t.get("Jugador")) in winners]
    st.dataframe([
        {
            "Ronda": t.get("Ronda"),
            "Jugador": role_name(manifest, integer(t.get("Jugador"))),
            "Posición antes": t.get("Afinidad_posicion_antes"),
            "Posición después": t.get("Afinidad_posicion_despues"),
            "Zona después": t.get("Afinidad_zona_despues"),
            "Compatible": t.get("Pareja_compatible_despues"),
        }
        for t in focus
        if low <= integer(t.get("Ronda")) <= high
    ], use_container_width=True, hide_index=True, height=280)

with tabs[5]:
    st.caption("Procedencia, integridad y cobertura de la partida seleccionada.")
    if st.button("Verificar hashes, secuencias e identidad de la partida"):
        with st.spinner("Leyendo los archivos originales de esta partida…"):
            try:
                issues = audit(game, root_path, zip_bytes)
                if not issues:
                    st.success("Sin discrepancias en las verificaciones realizadas.")
                else:
                    for issue in issues:
                        st.error(issue)
            except (ValueError, OSError, KeyError) as exc:
                st.error(f"Error de auditoría: {exc}")
    st.json({
        "esquema": manifest.get("schema"),
        "reglas": manifest.get("ruleset"),
        "semilla": manifest.get("seed"),
        "jugadores": manifest.get("player_count"),
        "ganadores": list(winners),
        "estado": manifest.get("status"),
        "policy": manifest.get("policy"),
        "conteos": manifest.get("counts"),
    })
    with st.expander("Manifest completo"):
        st.json(manifest)
    st.download_button(
        "Exportar eventos visibles (JSON)",
        json.dumps(filtered, ensure_ascii=False, indent=2),
        file_name=f"simlog_v21_analisis_{selected['seed']}.json",
        mime="application/json",
    )
with tabs[6]:
    st.caption("Posiciones de todos los jugadores al final de la ronda seleccionada. "
               "Para cambiar de ronda sin desplazar la página, abrí el inspector.")
    numero_tablero = integer(st.session_state.get("selected_round_v21"), 1)
    if numero_tablero > max_round:
        numero_tablero = max_round
    if st.button("Abrir tablero con controles fijos",key="inspector_desde_tablero"):
        st.session_state["inspector_vista_simlog"] = "Tablero"
        st.session_state["inspector_simlog"] = True
        st.rerun()
    snap_tablero = snapshot_de_ronda(game,numero_tablero)
    if snap_tablero["sin_datos"]:
        st.warning("No hay estados físicos de SIMLOG en esta ronda.")
    else:
        st.plotly_chart(dibujar_tablero(game,numero_tablero),
                        use_container_width=True)
        mostrar_coincidencias_tablero(snap_tablero)
        st.dataframe(resumen_ubicaciones(snap_tablero),
                     use_container_width=True,hide_index=True)
        if snap_tablero["faltantes"]:
            st.warning(f"Faltan jugadores al cierre: {snap_tablero['faltantes']}")

st.caption("SIMLOG v2.1/v2.2/v2.3 · Vista de solo lectura · Resultados del simulador experimental; "
           "no constituyen una certificación del balance ni de reglas pendientes.")
