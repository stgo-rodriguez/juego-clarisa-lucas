# Laboratorio de Balance — Fase 1: parametrización económica

## Resultado local verificado

- Motor original `simulador/motor_v13_base.py` intacto (SHA-256 `9ea6c0b19c8ff7f76e07bf13ab8831b5d48e373a57c7e3fb2ea3d1d349f8ef32`).
- Adaptador separado `simulador/motor.py`, parámetros validados en `simulador/economia.py`.
- Línea base: 1.000 partidas 6j (semilla 131028) y 1.000 partidas 10j (231028); incremento 103, tope 120, bots mixed.
- CSV generados con los parámetros originales: **coincidencia binaria exacta con las dos referencias** de Fase 0.
- Sin cambios de costos ni requisitos del juego, sin cambios en `main` ni en la web de GitHub Pages.

## Ejecutar

Requisitos: Python 3.11+; no dependencias externas para esta fase.

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
python -m laboratorio.verificar_baseline
python -m laboratorio.verificar_baseline --full
python -m laboratorio.ejecucion --escenario escenarios/experimento_10pct_menos.json --out /tmp/experimento
```

`--full` ejecuta **2.000 partidas nuevas** y compara los bytes de cada CSV generado con la referencia comprimida del repositorio.

Para extraer los originales manualmente:

```bash
gzip -dc referencias/resultados_6j.csv.gz > resultados_6j.csv
gzip -dc referencias/resultados_10j.csv.gz > resultados_10j.csv
```

## Controles

| Clave JSON | Base | Rango (MVP) |
|---|---|---|
| `perfiles_pct` | 100 | 50..150 |
| `cartas_ganancias_pct` | 100 | 50..150 |
| `cartas_perdidas_pct` | 100 | 50..150 |
| `infancia_pct` | 100 | 50..150 |
| `juventud_pct` | 0 | 0 o 100 |
| `adultez_pct` | 0 | 0 o 100 |

Para multiplicadores fraccionarios se usa redondeo estocástico reproducible con un generador independiente (`seed*13+4`). **El 100% no consume números aleatorios ni altera la secuencia original.**

## Pendientes y decisiones intencionales

1. Las políticas de bot todavía están físicamente dentro de `motor_v13_base.py`. Extraerlas sin cambiar el comportamiento es un refactor aparte, sujeto a regresión.
2. El mazo infantil usa una separación experimental I01–I12 Clarisa e I13–I24 Lucas. Los efectos de las 78 cartas se contrastaron con Drive, pero la asignación por rol necesita confirmación documental.
3. Los resultados basados en bots no certifican la duración de partidas humanas.
4. La Fase 2 fortalecerá invariantes, especialmente en escenarios extremos y registros de fuentes de recursos.
5. Streamlit y la interfaz de parametrización quedan fuera de esta fase: primero mantener una CLI y una línea base auditable.
