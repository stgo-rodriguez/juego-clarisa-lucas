# Laboratorio de Balance de Clarisa & Lucas (fases 1–2)

Branch independiente; no modificar `index.html`, `README.md` ni `.github/workflows/pages.yml`.

## Ejecutar

Requiere Python 3.11 o posterior. En raíz del repositorio:

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
python -m laboratorio.verificar_baseline --full
python -m laboratorio.ejecucion --escenario escenarios/base_v13_6j.json --out /tmp/balance_6j
python -m laboratorio.ejecucion --escenario escenarios/base_v13_10j.json --out /tmp/balance_10j
```

SHA-256 esperados de `resultados_6j.csv` y `resultados_10j.csv` en `referencias/README.md`.

## Alcance

- `simulador/motor_v13_base.py`: copia **inmutable** del motor validado v1.3 (sha256 de referencia 9ea6c0b19c8ff7f76e07bf13ab8831b5d48e373a57c7e3fb2ea3d1d349f8ef32).
- `simulador/motor.py`: adaptador para economía experimental, sin cambios de reglas.
- `simulador/economia.py`: controles P01–P06, validación y redondeo estocástico por RNG independiente.
- `laboratorio/ejecucion.py`: CLI reproducible y manifiestos de cada lote.
- `tests/`: las 31 pruebas v1.3 adaptadas en sus imports y pruebas nuevas de economía.
- `escenarios/`: JSON de 6 y 10 jugadores; 0% de ingresos por casilleros en Juventud/Adultez.
- `referencias/`: hashes históricos y archivos CSV cuando se incluyan.

**Limitación intencional:** las políticas de bot permanecen temporalmente dentro del motor congelado. Extraerlas en `bots.py` implicaría un refactor de reglas/rutas RNG y requiere su propia prueba de equivalencia. La separación lógica de economía se alcanza con el adaptador; la separación física de bots es futura.

**Nota:** los multiplicadores afectan la economía, no los costos de hitos. En cartas se escalan antes de elegir el desenlace para que el bot observe los importes efectivos. El redondeo es estocástico sobre enteros y reproduce exactamente el motor original a 100% sin consumir RNG extra.

## Fase 2

Se incorporaron controles adicionales de invariantes, extremos y RNG. Véase `docs/FASE2_CALIDAD.md` y `docs/DIAGNOSTICO_EXTREMOS_FASE2.json`. No se modificaron reglas ni bots.

## Fase 3: interfaz web local (Streamlit)

Requiere Python 3.11 o superior. En macOS/Linux, desde la raíz del repositorio:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m streamlit run laboratorio/app.py
```

La interfaz abrirá en `http://localhost:8501` (salvo que el puerto esté ocupado).
Usá **Ctrl+C** para detener el servidor. Para volver a ejecutarla otro día:

```bash
cd juego-clarisa-lucas
source .venv/bin/activate
python -m streamlit run laboratorio/app.py
```

El panel ejecuta dos escenarios con semillas apareadas y permite descargar datos y configuraciones. Se mantiene el sitio público existente (`index.html`) intacto. El análisis completo de incertidumbre, sensibilidad y Gantt corresponde a fases posteriores.

## Fase 4.1 — Gantt de hitos

Después de ejecutar los dos escenarios, seleccioná un escenario y una
partida **concluida** en «4. Cronología de hitos» y presioná
**Construir Gantt y verificar partida**. El Gantt considera solamente
los dos integrantes ganadores, separa primera consecución de hito vigente
y reconstruye pérdidas y recuperaciones. Comprueba igualdad de `summary()`
por semilla antes de mostrarlo. Más información:
`docs/FASE4_1_GANTT.md`.

### Fase 4.2 — Economía de recursos

En la aplicación, tras ejecutar escenarios, la sección **5. Economía de recursos**
permite comparar flujos medios del lote sin atribución ficticia de etapas,
seleccionar una partida, reconstruir su economía con el mismo motor y consultar:
entradas, pagos, inversiones, pérdidas, transferencias, stock libre y reservas.
La auditoría incluye exportación JSON y verificación de todos los movimientos
por jugador y recurso. Más detalles en `docs/FASE4_2_ECONOMIA.md`.
