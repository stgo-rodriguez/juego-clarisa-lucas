"""Visualización de cronología, sin dependencias de Streamlit ni reglas."""
from __future__ import annotations

import plotly.graph_objects as go

PALETA = {
    'Individual': '#5D92CF', 'Pareja': '#9A81BD',
    'Afinidad': '#44A89A', 'Casa': '#CB9658', 'Final': '#499D62',
}


def grafico_gantt(cronologia: dict) -> go.Figure:
    fig = go.Figure()
    periodos = cronologia.get('periodos') or []
    hitos = cronologia.get('hitos') or []
    if not cronologia.get('finalizada') or not periodos:
        fig.add_annotation(text='No hay cronología de pareja ganadora', x=0.5, y=0.5,
                           xref='paper', yref='paper', showarrow=False)
        fig.update_layout(height=260)
        return fig
    for grupo, color in PALETA.items():
        sub = [p for p in periodos if p['grupo'] == grupo]
        if not sub:
            continue
        fig.add_trace(go.Bar(
            name=grupo, orientation='h', y=[p['hito'] for p in sub],
            x=[p['x_fin']-p['x_inicio'] for p in sub],
            base=[p['x_inicio'] for p in sub], marker_color=color,
            customdata=[[p['ronda_inicio'], p['turno_inicio'],
                         p['ronda_fin'], p['turno_fin']] for p in sub],
            hovertemplate=('<b>%{y}</b><br>Inicio: ronda %{customdata[0]}, turno %{customdata[1]}'
                           '<br>Fin: ronda %{customdata[2]}, turno %{customdata[3]}'
                           '<extra></extra>'),
        ))
    orden = [h['Hito'] for h in hitos]
    fig.update_layout(
        title=f"Hitos de la pareja ganadora · partida {cronologia['partida']}",
        height=max(430, 38 * len(orden) + 110),
        barmode='overlay', bargap=0.4, legend_title='Tipo de hito',
        xaxis_title='Ronda (progresión dentro del turno)',
        yaxis_title='', margin=dict(l=20, r=20, t=65, b=40),
    )
    fig.update_yaxes(categoryorder='array', categoryarray=list(reversed(orden)))
    fig.update_xaxes(range=[0, cronologia['ronda_casamiento'] + 1], dtick=5)
    fig.add_vline(x=cronologia['ronda_casamiento'], line_dash='dot',
                  line_color='#777777', opacity=0.55)
    return fig
