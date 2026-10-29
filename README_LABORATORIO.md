# Laboratorio de Balance de Clarisa & Lucas (fases 0–7)

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

El panel ejecuta dos escenarios con semillas apareadas y permite descargar datos y configuraciones. Se mantiene el sitio público existente (`index.html`) intacto. Los módulos de Gantt, economía, interacciones, actividad de turnos, historial y sensibilidad se encuentran implementados (fases 4–6).

## Fase 4.1 — Gantt de hitos

Después de ejecutar los escenarios, abrí **Detalle de una partida · selección
común** y elegí **Base o Experimento** y la **partida** una sola vez. Las cuatro
pestañas —Cronología, Economía, Interacciones y Actividad de turnos— usan esa
misma selección. **Los cuatro análisis se reconstruyen y verifican
automáticamente** al cambiar escenario o partida. Se reutilizan cuando
la selección no cambia; no hay botones de reconstrucción.

**Pantalla de análisis** abre una vista ampliada que oculta formularios y
resúmenes generales. El selector se mantiene visible al recorrer gráficos
y se puede volver al laboratorio con el botón correspondiente. No es
necesario activar el modo de pantalla completa del navegador.
Las partidas censuradas también son seleccionables, aunque no tienen pareja
ganadora para el Gantt.

El Gantt utiliza inversiones reales desde el primer aporte al proyecto
adjudicado hasta la obtención de Título o Pasaporte, y registra pérdidas y
recuperaciones. La reejecución verifica igualdad de `summary()`.
Más información: `docs/FASE4_1_GANTT.md`.

### Fase 4.2 — Economía de recursos

En la aplicación, tras ejecutar escenarios, la sección **5. Economía de recursos**
permite comparar flujos medios del lote sin atribución ficticia de etapas,
reconstruir la partida del selector común con el mismo motor y consultar:
entradas, pagos, inversiones, pérdidas, transferencias, stock libre y reservas.
La auditoría incluye exportación JSON y verificación de todos los movimientos
por jugador y recurso. Más detalles en `docs/FASE4_2_ECONOMIA.md`.

### Fase 4.3 — Interacciones y conflictos

Tras simular los dos escenarios, la sección **6. Interacciones: Duelos, negociación, Pareja y Casa** muestra los contadores reales de los CSV por partida. Usá la partida del selector común y pulsá **Reconstruir y auditar interacciones** para ver modalidades y resultados de Duelos, retiros, compras y traspasos de Casa, cesiones de comprobantes, rupturas e intercambio de recursos, con participantes, etapa, ronda y turno. La ayuda automática entre miembros de una pareja se muestra aparte y **no** cuenta como negociación.

Descargá el JSON para inspeccionar cada evento y su origen. El observador comprueba igualdad de semilla, resumen por partida y contadores del motor. Más detalles en `docs/FASE4_3_INTERACCIONES.md`; muestra de control en `docs/DIAGNOSTICO_INTERACCIONES_FASE4_3.json`. **Sin cambios en las reglas ni los bots.**

### Fase 4.4 — Actividad y calidad de turnos (medidas descriptivas)

Después de ejecutar escenarios, abrí **«7. Actividad de turnos y oportunidades detectadas»**, usá la selección común de escenario y partida, y presioná **Reconstruir actividad de turnos**. Obtendrás conteos de decisiones realmente ejecutadas, consecuencias automáticas y diez familias de acciones disponibles en checkpoints del motor, con distribución por etapa, bot y turno individual. Exportación JSON disponible.

**Interpretación:** no es una medida objetiva de diversión ni un censo de todas las alternativas legales. Las ofertas no formuladas y las opciones humanas no pueden inferirse desde el bot. Documentación: `docs/FASE4_4_TURNOS.md`; auditoría de 150 partidas: `docs/DIAGNOSTICO_TURNOS_FASE4_4.json`. Ningún cambio en reglas, bots ni RNG.

### Fase 5 — Historial local e intercambio de experimentos

El panel **Historial de experimentos · Fase 5** aparece antes de los resultados. Después de
simular se puede:

- **Guardar comparación en este equipo:** se escribe un ZIP completo y verificable en
  `.laboratorio/historial/` (ignorado por Git), con nombre y fecha. Persiste tras cerrar
  Streamlit. No se sube ni sincroniza con GitHub.
- **Descargar experimento completo (ZIP):** conserva resultados de todas las partidas,
  semillas, configuraciones, resúmenes, eventos de muestra, motor y mazo (SHA-256).
- **Importar:** admite ZIPs actuales y el formato de comparación de Fase 3. Este último
  únicamente proporcionaba SHA-256 de CSV; se informa la limitación al importar.
- **Comparar sin simular:** elegí cualquiera de los dos escenarios de dos archivos
  guardados. Deben coincidir **tamaño de mesa, semillas, cantidad de partidas,
  horizonte, mezcla de bots y huella de código/mazo**; no se fuerzan comparaciones
  incompatibles. El resultado recuperado alimenta los gráficos anteriores.

La recuperación del historial **no ejecuta el simulador**. Las reconstrucciones
por partida de las secciones Gantt/Economía/Interacciones/Turnos sí vuelven a
simular *solo la partida seleccionada* para obtener eventos detallados que no
están presentes para todas las partidas del lote; la semilla y resultado se auditan.

Para trasladar experimentos a otra computadora, descargá los ZIP y usá **Importar**.
Los ZIP tienen límites de tamaño y validación de rutas e integridad, pero los hashes
no son firmas criptográficas de procedencia. No cargues archivos de origen dudoso.

Especificación y pruebas: `docs/FASE5_HISTORIAL.md` y `tests/test_historial_fase5.py`.

### Fase 6 — Análisis de sensibilidad e incertidumbre

La sección **«8. Sensibilidad e incertidumbre»** se puede utilizar sin ejecutar
antes el comparador básico. Elegí dos variables económicas distintas, 1–5
valores por eje (0/100% para casilleros de Juventud y Adultez), política de
bots, cantidad de jugadores, semilla y cantidad de partidas. La matriz ejecuta
un máximo de **3.000 partidas** con semillas comunes y caché por configuración.

El mapa de calor muestra la **diferencia media de rondas observadas hasta el
horizonte**, y una tabla detalla IC95 bootstrap apareados, censura, tasa de
finalización y métricas de las partidas concluidas. Si hay partidas censuradas,
la duración observable NO es una estimación de la duración final esperada.

Podés **descargar el ZIP** de la matriz, guardarlo en
`.laboratorio/sensibilidad/` (excluido por Git), o importarlo/recuperarlo sin
volver a simular. Los archivos conservan métricas agregadas, configuraciones,
huellas de motor y mazo y SHA-256 de integridad; no incluyen partidas/eventos
individuales para evitar grandes tamaños. No se calculan correcciones por
comparaciones múltiples ni se infiere diversión humana.

Documentación técnica: `docs/FASE6_SENSIBILIDAD.md`. Ejemplo reproducible:
`docs/DIAGNOSTICO_SENSIBILIDAD_FASE6.json`.


### Fase 7 — Estabilización local

Se incluyen guía de usuario, autodiagnóstico offline, script de inicio local,
configuración segura de Streamlit y CI en Python 3.11 y 3.13. Esta versión **no
se publica en internet**. Para actualizar sin borrar el historial: 

```bash
cd ~/Documents/juego-clarisa-lucas
git switch feature/laboratorio-balance
git pull --ff-only origin feature/laboratorio-balance
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m laboratorio.diagnostico
./iniciar_laboratorio.sh
```

Para la primera instalación, problemas frecuentes, pruebas manuales y rendimiento:
`docs/GUIA_USUARIO.md`, `docs/FASE7_ESTABILIZACION.md` y
`docs/PRUEBA_MANUAL_FASE7.md`. Conservar los ZIP guardados en `.laboratorio/`:
los historiales no se sincronizan automáticamente con GitHub.

## Mejora de legibilidad de cronología (Fase 7, revisión visual)

La sección 4 abre por defecto una línea de tiempo con marcadores por **ronda exacta**
de primera obtención. Clarisa, Lucas y la pareja tienen bloques separados.
Los rombos huecos marcan recuperaciones; las cruces rojas, pérdidas.
El antiguo gráfico de barras permanece en «Ver períodos de vigencia y pérdidas»
porque esas barras indican cuánto se conservó un hito, no cuánto tardó en obtenerse.
La reconstrucción de semillas y el motor de reglas no cambian.
