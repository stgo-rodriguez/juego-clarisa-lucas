"""Visualizador interactivo de partidas SIMLOG v2.1.

Página autónoma del Laboratorio de Balance. Solo lectura de trazas persistidas.
Para abrirla: streamlit run laboratorio/app.py (menú lateral SIMLOG v2.1)
o streamlit run laboratorio/pages/1_Visualizador_SIMLOG_v21.py
"""
from __future__ import annotations

import csv
from html import escape
from io import StringIO
import json
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

st.set_page_config(page_title="Visualizador SIMLOG v2.1", page_icon="📊", layout="wide")

@st.cache_data(show_spinner=False)
def catalogo_narrativo():
    return load_current()

@st.cache_data(show_spinner=False, max_entries=4)
def cached_discovery(path, zip_bytes):
    return discover_games(path, zip_bytes)

@st.cache_data(show_spinner=False, max_entries=3)
def cached_game(path, directory, zip_bytes):
    return load_game(path, directory, zip_bytes)

def pill_of_game(g):
    ending = "casamiento" if g["won"] else "sin victoria"
    return (f"{g['size']} jugadores · Semilla {g['seed']} · "
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

st.title("Visualizador de partidas · SIMLOG v2.1")
st.caption("Decisiones y eventos SIMLOG v2.1 por partida y jugadores seleccionados. "
           "Solo lectura: no modifica simulaciones ni inventa resultados.")

with st.expander("Origen de los datos · carpetas y ZIP SIMLOG v2.1", expanded=False):
    src1, src2 = st.columns([2.4, 1.5], vertical_alignment="bottom")
    with src1:
        root_path = st.text_input(
            "Carpeta principal de resultados",
            value=str(ROOT / "resultados"),
            help="Se buscan de forma recursiva TODAS las partidas SIMLOG v2.1 "
                 "de esta carpeta, sin limitar semillas ni tamaño de mesa.")
    with src2:
        uploaded = st.file_uploader(
            "Agregar ZIP de trazas", type=["zip"],
            help="Las partidas del ZIP se suman a las de las carpetas locales.")
    extra_roots = st.text_area(
        "Otras carpetas de simulaciones (opcional, una ruta por línea)",
        value="", height=78, placeholder="/ruta/a/otra/corrida",
        help="Se suman al índice, incluso cuando están fuera de resultados/.")
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
    if zip_bytes is not None:
        for g in cached_discovery(root_path, zip_bytes):
            games.append({**g, "source_root": root_path, "source_type": "ZIP"})
except (ValueError, OSError, KeyError) as exc:
    st.error(f"No se pudo leer la fuente SIMLOG v2.1: {exc}")
    st.stop()
games.sort(key=lambda g: (g["size"], g["seed"], g["id"], g["directory"]))
if not games:
    st.info("No se encontraron trazas completas SIMLOG v2.1 compatibles. "
            "Buscá otras carpetas o agregá un ZIP de partidas. "
            "El historial v1.3 y las simulaciones anteriores sin SIMLOG v2.1 "
            "no permiten reconstruir estos eventos por ronda.")
    st.stop()

winners_count = sum(g["won"] for g in games)
six_count = sum(g["size"] == 6 for g in games)
ten_count = sum(g["size"] == 10 for g in games)
st.caption(
    f"**{len(games)} simulaciones SIMLOG v2.1 encontradas** · "
    f"{winners_count} con casamiento · {len(games)-winners_count} sin ganador · "
    f"{six_count} de 6 jugadores · {ten_count} de 10 jugadores. "
    "Se incluyen todos los archivos compatibles encontrados en las fuentes seleccionadas."
)

a, b, c = st.columns([1, 3, 1], vertical_alignment="bottom")
with a:
    only_won = st.checkbox("Solo partidas con ganador", value=False)
available = [g for g in games if g["won"]] if only_won else games
if not available:
    st.warning("El filtro no devuelve partidas con casamiento. Desactivalo para ver todas.")
    st.stop()
with b:
    selected = st.selectbox(
        "Seleccionar partida", available,
        format_func=lambda g: (
            pill_of_game(g) + f" · {g['source_type']}: "
            + (Path(g["directory"]).parent.parent.name
               if g["source_type"] == "carpeta" else g["directory"])
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
                              value=(1, max_round), key=f"window_{selected['id']}")
    with right:
        st.button("Ver todo", use_container_width=True,
                  on_click=lambda: st.session_state.update(
                      {f"window_{selected['id']}": (1, max_round)}))

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
                "Interacciones", "Afinidad", "Auditoría"])

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
st.caption("SIMLOG v2.1 · Vista de solo lectura · Resultados del simulador experimental; "
           "no constituyen una certificación del balance ni de reglas pendientes.")
