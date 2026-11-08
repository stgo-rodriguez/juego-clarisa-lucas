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

st.set_page_config(page_title="Visualizador SIMLOG v2.1", page_icon="📊", layout="wide")

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
        title=None, height=490, margin=dict(l=20, r=20, t=12, b=65),
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
st.caption("Decisiones y eventos reales de la pareja ganadora, ordenados por ronda. "
           "No modifica partidas ni ejecuta el simulador.")

with st.expander("Origen de los datos · carpeta o ZIP SIMLOG v2.1", expanded=True):
    src1, src2 = st.columns([2.4, 1.5], vertical_alignment="bottom")
    with src1:
        root_path = st.text_input(
            "Carpeta local de resultados",
            value=str(ROOT / "resultados"),
            help="Debe contener trazas/n6_s1/manifest.json, etc. "
                 "También puede apuntar directamente a una carpeta de partida.")
    with src2:
        uploaded = st.file_uploader("Alternativamente, cargar ZIP de trazas",
                                    type=["zip"], help="El ZIP tiene prioridad sobre la carpeta.")
    zip_bytes = uploaded.getvalue() if uploaded is not None else None
    if zip_bytes is not None and len(zip_bytes) > 120_000_000:
        st.error("ZIP demasiado grande para carga directa (>120 MB). Usá la carpeta local.")
        st.stop()

try:
    games = cached_discovery(root_path, zip_bytes)
except (ValueError, OSError, Exception) as exc:
    st.error(f"No se pudo leer la fuente SIMLOG: {exc}")
    st.stop()
if not games:
    st.info("No se encontraron trazas con manifest de esquema SIMLOG-2.1. "
            "Seleccioná una carpeta existente o subí un ZIP de resultados.")
    st.code(
        "python -m laboratorio.simular_mazos_vigentes_v2 "
        "--semillas 20 --rondas 100 --out resultados/simlog_v21_20261108",
        language="bash",
    )
    st.stop()

a, b, c = st.columns([1, 3, 1], vertical_alignment="bottom")
with a:
    only_won = st.checkbox("Solo partidas con ganador", value=True)
available = [g for g in games if g["won"]] if only_won else games
if not available:
    st.warning("No hay partidas con casamiento registrado en esta fuente. "
               "Desactivá el filtro para inspeccionar los metadatos.")
    st.stop()
with b:
    selected = st.selectbox("Seleccionar partida", available, format_func=pill_of_game)
with c:
    st.caption(f"{len(available)} partidas seleccionables")

try:
    game = cached_game(root_path, selected["directory"], zip_bytes)
except (ValueError, OSError, KeyError) as exc:
    st.error(f"No se pudo abrir la partida: {exc}")
    st.stop()
manifest = game["manifest"]
winners = pair_from_manifest(manifest)
if not winners:
    st.warning("Esta partida no tiene una pareja ganadora. No se asignan "
               "ganadores ficticios ni se construye un Gantt de ganadores.")
    with st.expander("Metadatos de la partida"):
        st.json(manifest)
    st.stop()

items = build_events(game)
max_round = max(1, selected["rounds"],
                max((integer(t.get("Ronda")) for t in game["turnos.csv"]), default=1))
summary = manifest.get("summary") or {}
st.caption(
    f"**Partida:** {selected['id']}  ·  **Mesa:** {selected['size']} jugadores  ·  "
    f"**Pareja:** {' + '.join(role_name(manifest, p) for p in winners)}  ·  "
    f"**Casamiento:** ronda {max_round}  ·  **Semilla:** {selected['seed']}"
)

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
        if st.button("Ver todo", use_container_width=True):
            st.session_state[f"window_{selected['id']}"] = (1, max_round)
            st.rerun()

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
    cards = st.columns(2)
    for index, pid in enumerate(winners):
        rows = [t for t in game["turnos.csv"]
                if integer(t.get("Jugador")) == pid and integer(t.get("Ronda")) == chosen_round]
        with cards[index]:
            st.markdown(f"**{role_name(manifest, pid)}**")
            if not rows:
                st.info("Sin turno registrado en esta ronda.")
                continue
            t = rows[0]
            st.markdown(
                f"**Etapa:** {t.get('Etapa_antes')} → {t.get('Etapa_despues')}  "
                f"\n**Casillero:** {t.get('Pos_antes')} → {t.get('Pos_despues')}  "
                f"\n**Situación:** {t.get('Carta_ID') or '—'} "
                f"· opción **{t.get('Desenlace_elegido') or '—'}**  "
                f"\n**Movimiento:** {t.get('Carta_Movimiento') or 'D6'} "
                f"· opción **{t.get('Desenlace_movimiento') or '—'}**  "
                f"\n**Afinidad:** {t.get('Afinidad_zona_antes') or '—'} → "
                f"{t.get('Afinidad_zona_despues') or '—'}"
            )
            st.caption(t.get("Desenlace_texto") or "Sin texto narrativo registrado.")
            with st.expander("Datos completos del turno"):
                st.json(t)
    round_events = [e for e in filtered if e["ronda"] == chosen_round]
    st.markdown(f"**Eventos observados en la ronda {chosen_round} ({len(round_events)})**")
    st.dataframe(event_dataframe(round_events, manifest), use_container_width=True,
                 hide_index=True, height=270)
    with st.expander("Detalle JSON de los eventos de esta ronda"):
        st.json(round_events)

with tabs[2]:
    st.caption("Saldos después del turno propio de cada ganador. "
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
    social_count = Counter(e["categoria"] for e in social)
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
