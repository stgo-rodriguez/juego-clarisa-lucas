"""Tablas y gráficos descriptivos de Fase 3, sin dependencia de Streamlit."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

def tabla_distribucion(base: dict, variante: dict) -> go.Figure:
    """Histogramas de casamientos terminados; las censuradas se informan aparte."""
    fig = go.Figure()
    for name, result in (("Base", base), ("Experimento", variante)):
        completed = [int(x["rondas_observadas"]) for x in result["filas"]
                     if int(x["terminada"])]
        if completed:
            fig.add_trace(go.Histogram(x=completed, name=name, opacity=0.60,
                                       histnorm="probability", xbins=dict(size=2)))
    fig.update_layout(barmode="overlay", xaxis_title="Ronda del casamiento (solo partidas concluidas)",
                      yaxis_title="Proporción de partidas concluidas", legend_title_text="Escenario",
                      margin=dict(l=15, r=15, t=20, b=15))
    return fig


def metricas_comparadas(base: dict, variante: dict) -> pd.DataFrame:
    rows = []
    for name, result in (("Base", base), ("Experimento", variante)):
        s = result["resumen"]
        c = s["casamiento"]
        rows.append({"Escenario": name, "Partidas": s["partidas"],
                     "Finalizadas": s["finalizadas"], "Censuradas": s["censuradas"],
                     "Finalización (%)": s["tasa_finalizacion"],
                     "Media (rondas)": c["media"], "Mediana": c["mediana"],
                     "P75": c["p75"], "P90": c["p90"], "P95": c["p95"]})
    return pd.DataFrame(rows)
