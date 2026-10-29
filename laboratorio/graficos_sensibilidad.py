"""Mapas y tablas de sensibilidad; sin código de Streamlit ni simulador."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from laboratorio.sensibilidad import PARAMETROS


def tabla_grilla(grilla: dict) -> pd.DataFrame:
    cells = grilla['celdas']
    return pd.DataFrame([{
        PARAMETROS[grilla['configuracion']['parametro_x']]+' (%)': c['x'],
        PARAMETROS[grilla['configuracion']['parametro_y']]+' (%)': c['y'],
        'Diferencia media rondas observadas': c['delta_rondas_observadas'],
        'IC95 inferior': c['ic95_rondas_observadas_inf'],
        'IC95 superior': c['ic95_rondas_observadas_sup'],
        'Finalizadas experimento': c['finalizadas_variante'],
        'Censuradas experimento': c['censuradas_variante'],
        'Cambio finalización (pp)': c['delta_finalizacion_pp'],
        'Delta media pares concluidos': c['delta_rondas_pares_concluidos'],
    } for c in cells])


def mapa_sensibilidad(grilla: dict, campo: str='delta_rondas_observadas') -> go.Figure:
    cfg = grilla['configuracion']
    xvalues, yvalues = cfg['valores_x'], cfg['valores_y']
    n = len(xvalues)
    grid = [[grilla['celdas'][j * n + i][campo] for i in range(n)]
            for j in range(len(yvalues))]
    fig = go.Figure(go.Heatmap(
        x=[str(x) for x in xvalues], y=[str(y) for y in yvalues], z=grid,
        colorscale='RdBu_r', zmid=0, colorbar=dict(title='Diferencia'),
        text=[[f'{v:+.2f}' for v in row] for row in grid],
        texttemplate='%{text}', hovertemplate='X=%{x}% · Y=%{y}%<br>Delta=%{z:.3f}<extra></extra>'))
    fig.update_layout(xaxis_title=f"{PARAMETROS[cfg['parametro_x']]} (%)",
                      yaxis_title=f"{PARAMETROS[cfg['parametro_y']]} (%)",
                      title='Diferencias apareadas respecto de la línea base',
                      margin=dict(l=25,r=20,t=55,b=50))
    return fig
