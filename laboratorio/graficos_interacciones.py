"""Visualización de métricas de conflicto y negociación; datos de Fase 4.3."""
from __future__ import annotations
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd


def figura_interacciones_por_tipo(datos: dict):
    df = pd.DataFrame(datos['por_tipo'])
    if df.empty:
        return go.Figure().update_layout(title='Sin interacciones observadas')
    return px.bar(df, x='Cantidad', y='Evento', color='Categoría', orientation='h',
                  title='Eventos efectivos por tipo').update_layout(yaxis={'categoryorder': 'total ascending'})


def figura_interacciones_por_ronda(datos: dict):
    df = pd.DataFrame(datos['por_ronda'])
    if df.empty:
        return go.Figure().update_layout(title='Sin interacciones observadas')
    return px.bar(df, x='Ronda', y='Cantidad', color='Categoría',
                  title='Interacciones efectivas por ronda').update_layout(barmode='stack')
