# Laboratorio de Balance — Fase 4.1: Gantt de los ganadores

## Alcance entregado

En la aplicación Streamlit, tras ejecutar y comparar escenarios, la sección
**4. Cronología de hitos de la pareja ganadora** permite elegir la
partida concluida de **Base** o **Experimento**, volver a ejecutar únicamente
esa semilla y observar la cronología de logros y, opcionalmente, el Gantt técnico de vigencia, con descarga JSON.

Se registran individualmente UTN, Título y Pasaporte de los **dos jugadores
ganadores**; en la pareja, la formación, la posesión simultánea de Título y
Pasaporte, la afinidad compatible, la Adultez, la Casa y el Casamiento. El
grupo "Casa" distingue adquisición inicial, pérdidas y recuperación final;
"Afinidad compatible" distingue coincidencia inicial y períodos posteriores.

## Precisión metodológica

- La fila original de Monte Carlo solo registra ciertos hitos como *primera
  vez*, que **no implica** mantenerlos hasta el casamiento. Los hitos pueden
  perderse por duelos, rupturas, retroceso de etapa o transferencia de Casa.
- `laboratorio/trazabilidad.py` define `JuegoObservado`, que extiende el
  **adaptador** y registra estados después de eventos significativos y tras
  cada turno; se registra el estado anterior al primer turno. No consume RNG.
- La **vista principal** es una cronología con Gantt de inversiones verificables.
  En Título y Pasaporte la barra comienza en la **primera inversión registrada
  en el proyecto concreto que terminó adjudicándose** y termina en el hito.
  Los proyectos pueden financiarse entre jugadores: se registra quién realizó
  esa primera inversión, aunque no sea la persona finalmente adjudicataria.
  El círculo señala la primera obtención, el rombo hueco una recuperación y
  la cruz roja una pérdida. Una recuperación del mismo proyecto no reinicia
  su período de inversión. Las demás filas muestran hitos puntuales cuando
  no existe un evento de inicio de trabajo verificable. Las barras **no**
  conectan hitos sucesivos ni indican que hubo trabajo continuo entre fechas.
- La **vista secundaria desplegable** conserva los períodos reales de tenencia;
  sus barras no son la duración que tomó obtener el hito. Se separan pérdidas y
  recuperaciones, incluso en una misma ronda, usando el orden de turnos.
- El Gantt se produce **a demanda** por partida seleccionada, no instrumenta
  las 2.000 partidas del lote; evita crecer en memoria y mantiene la
  equivalencia binaria de los CSV. Para una partida censurada no se inventa
  pareja ganadora.
- El Gantt toma exclusivamente los dos integrantes **de la pareja ganadora**.
  La afinidad solo se cuenta cuando esos integrantes son pareja entre sí.
- El momento de observación es **al término de eventos relevantes y turnos**.
  Cambios puramente transitorios dentro de una operación interna sin evento
  podrían no aparecer; el resultado se describe como cronología observada, no
  un registro de cada instrucción ejecutada.
- La persona puede cambiar su rol durante el juego. La etiqueta del Gantt
  corresponde al **rol final** al ganar; los estados observados conservan
  también el rol de cada instante.
- Antes de mostrar resultados, la reejecución exige **igualdad completa del
  diccionario `summary()`**, no solamente rondas/ganadores. Las diferencias
  bloquean el Gantt con un mensaje explícito.

## Archivos añadidos

- `laboratorio/trazabilidad.py` — observador y reconstrucción de períodos.
- `laboratorio/gantt.py` — cronología principal con barras de primera inversión a adjudicación y Gantt de vigencia opcional.
- `tests/test_gantt_fase4.py` — regresión, pérdidas y recuperaciones, censura,
  RNG invariante, pares de ganadores y prueba de interfaz en CI.
- `laboratorio/app.py` — sección de selección, gráfico, tabla, exportación.

## Validaciones realizadas localmente

- 80 pruebas descubiertas: 78 correctas, 2 omitidas por falta de Streamlit local; en la
  rama publicada se deberá verificar que las pruebas de Streamlit pasan en CI.
- 2.000 partidas de referencia: hashes SHA-256 idénticos para las 1.000 de
  seis jugadores y las 1.000 de diez jugadores.
- Prueba sintética de pérdida y recuperación dentro de la misma ronda.
- Igualdad de *eventlog* y estados de RNG del motor normal y observado.

## Fuera del alcance de 4.1

Economía desagregada (4.2), interacción y conflictos (4.3), y actividad de los
turnos (4.4). Se abordarán sin cambiar normativa ni bots.

## Actualización local en macOS

Desde la Terminal, primero detener Streamlit con `Ctrl+C`, luego:

```bash
cd ~/Documents/juego-clarisa-lucas
git pull origin feature/laboratorio-balance
source .venv/bin/activate
python -m streamlit run laboratorio/app.py
```

Ejecutar la comparación, ir a la sección 4, elegir escenario y partida
concluida, presionar «Ver cronología y verificar partida». El enlace de
descarga genera JSON con la cronología y los hashes del resultado original
siguen en los archivos existentes de la comparación.
