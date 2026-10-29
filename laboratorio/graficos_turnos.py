"""Fase 4.4: gráficos de actividad observada, sin inventar oportunidades."""
from __future__ import annotations
import plotly.graph_objects as go


def figura_etapas(resumen:dict) -> go.Figure:
    fig=go.Figure()
    filas=resumen.get('por_etapa',[])
    if filas:
        etapas=[x['Grupo'] for x in filas]
        fig.add_bar(name='Turnos con decisión',x=etapas,y=[x['Turnos con decisiones'] for x in filas])
        fig.add_bar(name='Sin decisión ejecutada',x=etapas,
                    y=[x['Turnos']-x['Turnos con decisiones'] for x in filas])
    fig.update_layout(barmode='stack',title='Turnos según actividad y etapa inicial',
                      xaxis_title='Etapa',yaxis_title='Turnos')
    return fig


def figura_familias(resumen:dict) -> go.Figure:
    filas=resumen.get('por_oportunidad',[])
    fig=go.Figure()
    if filas:
        x=[x['Acción'] for x in filas]
        fig.add_bar(name='Turnos donde estuvo disponible',x=x,
                    y=[x['Turnos disponibles'] for x in filas])
        fig.add_bar(name='Turnos con ejecución o resolución',x=x,
                    y=[x['Turnos con ejecución'] for x in filas])
    fig.update_layout(barmode='group',title='Disponibilidad detectada vs ejecución del bot',
                      xaxis_tickangle=-35,yaxis_title='Número de turnos')
    return fig
