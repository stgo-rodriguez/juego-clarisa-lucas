"""Lectura histórica de la última corrida SIMLOG v2.1; no usa el motor v1.3."""
from __future__ import annotations
import gzip
import json
from functools import lru_cache
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

DATA = Path(__file__).resolve().parents[1] / "docs" / "datos_v21_ultima"
RUN_URL = "https://github.com/stgo-rodriguez/juego-clarisa-lucas/actions/runs/42454007039"


@lru_cache(maxsize=1)
def cargar_resumen():
    d = json.loads((DATA / "resumen.json").read_text(encoding="utf-8"))
    games = d["games"]
    assert len(games) == d["summary"]["total_games"] == 200
    assert {(x["size"], x["seed"]) for x in games} == {
        (n, seed) for n in (6, 10) for seed in range(101, 201)}
    assert sum(x["a"] + x["b"] for x in games) == d["summary"]["total_decisions"] == 28708
    assert all(x["won"] for x in games)
    return d


@lru_cache(maxsize=8)
def cargar_partida(size: int, seed: int):
    size, seed = int(size), int(seed)
    if size not in (6, 10) or not 101 <= seed <= 200:
        raise ValueError("Mesa o semilla fuera del conjunto auditado")
    first = 101 if seed <= 150 else 151
    with gzip.open(DATA / f"detalle_{size}j_{first}_{first+49}.json.gz", "rt",
                   encoding="utf-8") as stream:
        data = json.load(stream)["by_game"][f"{size}-{seed}"]
    game = next(x for x in cargar_resumen()["games"]
                if x["size"] == size and x["seed"] == seed)
    if len(data["turns"]) != game["turns"]:
        raise ValueError("Los turnos no coinciden con el manifiesto de la partida")
    if (sum(x["op"] == "A" for x in data["turns"]), 
        sum(x["op"] == "B" for x in data["turns"])) != (game["a"], game["b"]):
        raise ValueError("Las elecciones A/B no coinciden con la partida")
    return data


def cronologia(game, detalle):
    """Solo hitos y primeras inversiones comprobables en eventos reales."""
    winner = set(game["pair"])
    first = {}
    for e in detalle["events"]:
        if e["action"] == "invest":
            first.setdefault(e["detail"]["project"], e["r"])
    hits = []
    for e in detalle["events"]:
        action, d = e["action"], e["detail"]
        pair = set(d.get("players", []))
        if action == "utn_profile_awarded" and d.get("player") in winner:
            hits.append(("UTN", f"Jugador {d['player']}", None, e["r"]))
        elif action == "adjudicate" and d.get("won") and d.get("player") in winner:
            project = str(d.get("project", ""))
            label = "Título" if project.startswith("Titulo-") else "Pasaporte"
            hits.append((label, f"Jugador {d['player']}", first.get(project), e["r"]))
        elif action == "pair" and pair == winner:
            hits.append(("Pareja formada", "Pareja", None, e["r"]))
        elif action == "dublin_to_adult" and pair == winner:
            hits.append(("Adultez", "Pareja", None, e["r"]))
        elif action == "house_bought" and set(d.get("owners", [])) == winner:
            hits.append(("Casa", "Pareja", None, e["r"]))
        elif action == "married" and pair == winner:
            hits.append(("Casamiento", "Pareja", None, e["r"]))
    return sorted(hits, key=lambda x: (x[3], x[1], x[0]))


def figura_hitos(hits, rondas):
    fig = go.Figure()
    for i, (hito, actor, inicio, fin) in enumerate(hits):
        y = f"{actor} · {hito}"
        color = "#188c6a" if hito == "Casamiento" else (
            "#9a70af" if actor == "Pareja" else "#4b85c4")
        if inicio is None:
            fig.add_scatter(x=[fin], y=[y], mode="markers", showlegend=False,
                            marker=dict(color=color, size=11),
                            hovertemplate=f"{y} · R{fin}<extra></extra>")
        else:
            fig.add_scatter(x=[inicio, fin], y=[y], mode="lines+markers",
                            showlegend=False, line=dict(width=13, color=color),
                            marker=dict(size=9, color=color),
                            hovertemplate=f"{y}<br>Primera inversión R{inicio} → R{fin}<extra></extra>")
    fig.add_vline(x=rondas, line_dash="dot", line_color="#188c6a")
    fig.update_layout(height=max(330, len(hits)*38+110),
                      margin=dict(l=160, r=28, t=20, b=55),
                      xaxis_title="Ronda", yaxis=dict(autorange="reversed"),
                      xaxis=dict(range=[0, rondas+1]))
    return fig


def mostrar_v21():
    try:
        data = cargar_resumen()
    except Exception as exc:
        st.error(f"No están disponibles los resultados verificados v2.1: {exc}")
        return
    summary, audit = data["summary"], data["audit"]
    st.title("Última simulación registrada · Clarisa & Lucas v2.1")
    st.caption("8 de noviembre de 2026 · SIMLOG v2.1 · 200 partidas · política planificador")
    st.info("**Resultados históricos v2.1, solo lectura.** No se han recalculado las "
            "partidas ni mezclado sus datos con el motor v1.3. Los mazos de Situación "
            "son experimentales; no constituyen un balance definitivo.")
    with st.expander("Configuración de la ejecución y trazabilidad"):
        st.markdown(f"[GitHub Actions: ejecución original]({RUN_URL}) · "
                    f"Artefacto {data['source']['artifact_id']} · "
                    f"commit \`{data['source']['commit_sha'][:12]}\`")
        st.json(summary["config"], expanded=False)
        st.caption(data["source"]["validation"])
    a,b,c,d = st.columns(4)
    a.metric("Partidas", "200")
    b.metric("Casamientos", str(summary["total_marriages"]))
    c.metric("Decisiones A/B", f"{summary['total_decisions']:,}".replace(",", "."))
    d.metric("Ganadoras en Neutro", f"{summary['winners_by_zone']['Neutro']}/200")
    col6,col10 = st.columns(2)
    for size,col in [(6,col6),(10,col10)]:
        with col:
            row = next(x for x in summary["summary"] if x["size"] == size)
            p80 = next(x["P80_rondas"] for x in audit["duracion"] if x["Mesa"] == size)
            st.markdown(f"**{size} jugadores · 100 partidas · mediana "
                        f"{row['median_rounds_censored']:g} rondas**")
            st.caption(f"Media {row['avg_rounds_censored']:.2f} · P80 {p80} · "
                       "100/100 casamientos")
    general,economia,decisiones,partidas = st.tabs([
        "Resultados generales", "Economía", "Decisiones A/B", "Partidas y SIMLOG"])
    with general:
        df = pd.DataFrame(data["games"])
        st.plotly_chart(px.histogram(df, x="rounds", color="size", nbins=28,
                                    barmode="overlay", title="Duración de las partidas",
                                    labels={"rounds":"Ronda de casamiento","size":"Jugadores"}),
                        use_container_width=True)
        zones = pd.DataFrame([{"Zona":k,"Parejas":v}
                              for k,v in summary["winners_by_zone"].items()])
        st.plotly_chart(px.bar(zones,x="Zona",y="Parejas",
                               title="Afinidad de parejas ganadoras"),use_container_width=True)
        st.dataframe(df.rename(columns={"size":"Jugadores","seed":"Semilla",
             "rounds":"Rondas","turns":"Turnos","zone":"Zona"}),
             hide_index=True,use_container_width=True)
    with economia:
        st.subheader("Recursos generados por etapa")
        table = pd.DataFrame(audit["economia_por_etapa"])
        long = table.melt(id_vars=["Etapa","Recurso"],
                          value_vars=["Porcentaje","Objetivo_pct"],
                          var_name="Tipo",value_name="Proporción (%)")
        long["Tipo"] = long["Tipo"].replace(
            {"Porcentaje":"Observado","Objetivo_pct":"Objetivo"})
        st.plotly_chart(px.bar(long,x="Recurso",y="Proporción (%)",color="Tipo",
                               barmode="group",facet_col="Etapa",
                               title="Generación de recursos frente a objetivos"),
                        use_container_width=True)
        st.dataframe(table,hide_index=True,use_container_width=True)
        st.markdown("**Producción por mecanismo**")
        st.dataframe(pd.DataFrame(audit["fuentes"]),hide_index=True,
                     use_container_width=True)
    with decisiones:
        st.subheader("Resoluciones A/B por etapa y rol")
        prefs = pd.DataFrame(data["preferences_stage_role"])
        prefs[["A","B"]] = prefs[["A","B"]].apply(pd.to_numeric)
        tall = prefs.melt(id_vars=["etapa","rol"],value_vars=["A","B"],
                          var_name="Opción",value_name="Decisiones")
        st.plotly_chart(px.bar(tall,x="etapa",y="Decisiones",color="Opción",
                               facet_col="rol",barmode="stack"),
                        use_container_width=True)
        st.dataframe(prefs,hide_index=True,use_container_width=True)
        cards=pd.DataFrame(data["preferences_cards"])
        st.markdown("**Dominancia y preferencia por carta compartida**")
        st.dataframe(cards,hide_index=True,use_container_width=True)
    with partidas:
        st.subheader("Explorar las 200 partidas registradas")
        l,r=st.columns([1,3])
        with l:
            size=st.radio("Jugadores",options=[6,10],horizontal=True,key="v21_mesa")
        with r:
            seed=st.selectbox("Semilla",options=list(range(101,201)),key="v21_semilla")
        game=next(x for x in data["games"] if x["size"]==size and x["seed"]==seed)
        try:
            detail=cargar_partida(size,seed)
        except Exception as exc:
            st.error(f"La traza no superó la verificación: {exc}")
            return
        st.caption(f"**{size} jugadores · semilla {seed}** · {game['rounds']} rondas · "
                   f"pareja ganadora {game['pair']} · zona {game['zone']} · "
                   f"A {game['a']} / B {game['b']} · {game['duels']} duelos")
        hitos = cronologia(game,detail)
        htab,rtab,atab,etab=st.tabs(
            ["Cronología","Economía de la partida","Afinidad y decisiones","Eventos"])
        with htab:
            st.caption("Las barras corresponden exclusivamente a la primera inversión "
                       "registrada en el proyecto que se adjudicó. No implican trabajo continuo.")
            st.plotly_chart(figura_hitos(hitos, game["rounds"]),use_container_width=True)
            st.dataframe(pd.DataFrame(hitos,columns=["Hito","Actor","Primera inversión","Ronda"]),
                         use_container_width=True,hide_index=True)
        with rtab:
            res=pd.DataFrame(detail["resources"]).rename(columns={
                "r":"Ronda","a":"Amor","p":"Personalidad",
                "k":"Conocimiento","m":"Dinero"})
            st.plotly_chart(px.line(res.melt(id_vars="Ronda",
                var_name="Recurso",value_name="Fichas libres"),x="Ronda",
                y="Fichas libres",color="Recurso",
                title="Recursos libres de todos los jugadores"),use_container_width=True)
            st.dataframe(res,use_container_width=True,hide_index=True)
        with atab:
            turns=pd.DataFrame(detail["turns"])
            selected=st.multiselect("Jugadores",list(range(1,size+1)),
                                    default=list(range(1,size+1)),key="v21_jugadores")
            turns=turns[turns["j"].isin(selected)].copy()
            turns["Jugador"]=turns["j"].astype(str)
            fig=px.line(turns,x="t",y="afin_desp",color="Jugador",markers=True,
                        title="Posición de afinidad por turno",hover_data=[
                            "r","etapa","carta","op","zona"])
            fig.add_hline(y=-2,line_dash="dot",line_color="gray")
            fig.add_hline(y=2,line_dash="dot",line_color="gray")
            st.plotly_chart(fig,use_container_width=True)
            st.dataframe(turns,hide_index=True,use_container_width=True)
        with etab:
            events=pd.DataFrame(detail["events"])
            options=sorted(events["action"].unique())
            acts=st.multiselect("Tipo de evento",options,default=options,key="v21_eventos")
            st.dataframe(events[events["action"].isin(acts)],use_container_width=True,
                         hide_index=True)
            st.caption("SIMLOG compactado para navegación; el registro íntegro "
                       "permanece disponible en el artefacto de GitHub.")
    st.caption(f"Fuente: [SIMLOG v2.1 · ejecución verificada]({RUN_URL}).")
