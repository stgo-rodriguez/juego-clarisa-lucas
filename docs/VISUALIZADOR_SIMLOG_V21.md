# Visualizador SIMLOG v2.1 · Gantt de decisiones por partida

## Funcionalidad integrada

Nueva página multipágina de Streamlit: `laboratorio/pages/1_Visualizador_SIMLOG_v21.py`, enlazada desde `laboratorio/app.py`. Lee únicamente trazas ya generadas, sin reejecutar ni modificar motores, agentes, cartas o partidas. Código de consulta: `laboratorio/simlog_viewer_v21.py`.

### Selección
- Origen: carpeta local de resultados o ZIP que contenga subcarpetas con `manifest.json`. Solo se admiten partidas con `schema=SIMLOG-2.1`; no se mezclan v1.3/v2.0.
- Selector: 6/10 jugadores, semilla, rondas, estado, ID. Por defecto se muestran solo partidas con pareja ganadora registrada; el selector de partidas censuradas permite ver sus metadatos sin inventar una pareja.
- Se cargan únicamente los CSV de la partida elegida: `turnos.csv`, `eventos.csv`, y opcionalmente `hitos.csv`, `estados_jugadores.csv` y `recursos_por_ronda.csv`.

### Gantt y filtros
- Franjas de **Infancia, UTN, Juventud, Vuelo a Dublín y Adultez** derivadas de `Etapa_antes` en turnos reales; se evitan barras de duración inferidas para subhitos.
- Marcadores en la **ronda real** por los dos integrantes de la pareja ganadora, con identificadores de turno y secuencia, hover, paneo, zoom de rueda y navegador de rangos.
- Filtros múltiples: Situación A/B, Movimiento, Duelos, Canjes, Noviazgo, Subhitos, Acuerdos, Hitos, Afinidad, Perfil, Recursos, Otros. Recursos/Otros ocultos de forma predeterminada por densidad.
- **Ronda a ronda:** navegación anterior/siguiente y detalle A/B de situación, A/B o D6 de movimiento, etapas, casilleros, afinidad, eventos y JSON íntegro del turno.
- **Economía:** evolución de A/P/K/M, saldo libre o total, y movimientos de recursos asociados.
- **Interacciones:** duelos, pareja, acuerdos, inversiones y hitos, sin confundir el duelo detallado con el evento resumen de Competencia.
- **Afinidad:** trayectorias A–Neutro–B y compatibilidad, con zona neutral [−2,+2].
- **Auditoría:** manifiesto, validación bajo demanda de SHA-256, secuencia y procedencia de la partida; exportación de eventos filtrados a CSV/JSON.

## Relación con el Laboratorio de Balance

**Funcionalidades reutilizadas conceptualmente:** selección común de partida y tamaño de mesa, visualización temporal, análisis económico, interacciones, actividad de turnos, detalle a demanda, trazabilidad de semillas, verificaciones y descargas. Se usa la **nueva** traza SIMLOG v2.1 y no se reutilizan datos antiguos como si fueran compatibles.

**No integradas en esta página:** comparación Monte Carlo Base/Experimento, sensibilidad de parámetros, p80 entre partidas, historial de experimentos y calibración de mazos. Esas son métricas de lote (no eventos de una partida), y siguen en el laboratorio original. Se podrían conectar en una segunda etapa con un índice de corridas compartido.


### Registro de propuestas de noviazgo (instrumentación nueva)

En esta rama, `SIMLogV21` observa de forma pasiva cada llamada real del agente a `eco.form_pair` y escribe `noviazgo_propuesta` y `noviazgo_resultado` (aceptada/rechazada), sin cambiar la elección del bot, balances, dados ni RNG. La pareja efectivamente constituida sigue registrada por `pair`. Las trazas v2.1 **generadas antes** de esta mejora no incluyen propuestas fallidas y deben generarse nuevamente para inspeccionarlas. No se inventan las oportunidades que el agente nunca intentó.

## Límites de los datos

1. Se presenta una **propuesta de noviazgo** solo si existe un evento explícito de propuesta. En el motor actual suele quedar registrado el **acuerdo/pareja constituida** (`pair`), pero no todos los intentos rechazados o no realizados. No inferirlos.
2. Un movimiento de un tercero puede afectar las reservas de un ganador entre sus turnos. Las curvas de economía/afinidad usan los estados **después del turno propio**: para intervalos en los que cambian durante un turno ajeno, el CSV `estados_jugadores.csv` conserva la evidencia más fina.
3. Los recursos automáticos, traspasos y ayudas se muestran como tales, no se etiquetan como negociaciones voluntarias sin evidencia.
4. La posición temporal de los eventos en el Gantt está anclada a rondas discretas; el desplazamiento horizontal diminuto de los símbolos solo evita superposiciones, nunca implica subrondas nuevas.
5. Los resultados SIMLOG v2.1 siguen siendo un **modelo experimental**. El visualizador no certifica conformidad con todas las reglas pendientes ni balance definitivo.

## Relato «Ronda a ronda» (actualización)

Cada ronda presenta dos columnas independientes (Clarisa y Lucas ganadores) con una narración breve, ordenada por la **secuencia real de eventos** y sin depender del filtro visual del Gantt.

- **Movimiento:** dado de Infancia, carta A/B de Juventud/Adultez, origen, destino, pasos descartados y rebotes observados. En UTN el dado del examen **no se presenta como movimiento**.
- **Casillero:** solo ingresos realmente cobrados; en Infancia se identifica el casillero exacto de destino.
- **Situación compartida:** título, contexto, texto de las dos opciones A/B, opción elegida y premios/pérdidas **realmente contabilizados**. Se muestra la evolución de Afinidad cuando está registrada. No se confunde efecto teórico de la carta con recurso entregado.
- **Eventos sociales:** duelos iniciados y recibidos (rival, resultado, dados y pagos reales), propuestas y resultados registrados, formación/ruptura de pareja, transferencias, inversiones y adjudicaciones, Casa, UTN, Dublín, Perfiles y Casamiento.
- **Canjes con la banca:** detalle de recursos efectivamente entregados y recibidos a partir de movimientos con origen `conversion_bancaria`.
- **Transferencias:** distinción entre enviar y recibir; se evita mostrar una segunda vez la transferencia contable correspondiente al pago de un duelo.
- **Inversiones en subhitos:** importe concreto si consta en el comprobante del estado de cierre; de lo contrario, se relata la inversión sin inventar cantidades.
- **Terceros:** también se incorporan eventos donde un ganador fue afectado durante el turno de otro participante. En ausencia de turno propio, esa condición queda explícita.
- **Registro completo:** sigue disponible en el desplegable de cada jugador y en la tabla de eventos de la ronda. Los filtros del Gantt no ocultan el relato.

El catálogo narrativo `catalogo_102_v03_v04.json` es la fuente de las opciones A/B. Si no existe, se usa únicamente el texto almacenado por el turno SIMLOG. Las trazas anteriores a la instrumentación `noviazgo_propuesta` no permiten recuperar propuestas fallidas retroactivamente.

**Pruebas:** `tests/test_narrativa_simlog_v21.py` verifica las fuentes de cada efecto, orden temporal, duelos recibidos, canjes, subhitos y una traza real escrita por el simulador de la versión v2.1.

## Recursos por ronda y efectos visuales de las opciones A/B

La pestaña **Ronda a ronda** incorpora un panel por ganador con cuatro indicadores (Amor, Personalidad, Conocimiento y Dinero):

- **Valor grande:** recursos al **cierre efectivo de la ronda** (`estados_jugadores.csv`, último `Turno_global` con `Momento=despues` en esa ronda, para el jugador seleccionado). Esto incluye efectos de acciones que ocurren en turnos de terceros.
- **Variación con signo:** diferencia con el cierre de la ronda inmediatamente anterior; en ronda 1 no se calcula una referencia inexistente.
- **Stock representado:** `libre + reservas de Pareja/Casa`, sin incluir recursos ya invertidos en proyectos compartidos. Si existen reservas, se indica cuánto está libre y cuánto reservado.
- **Cobertura:** si falta la evidencia de estados completa, se indica que no hay información, sin interpolar saldos.

Debajo de cada opción de **Carta de Situación**, el texto completo se acompaña con indicadores visuales con signo, icono, nombre y color: positivo/verde para recursos que suma, negativo/rojo para recursos que resta. Para ambas opciones se indican los efectos **previstos** del catálogo original. Cuando el desenlace seleccionado tuvo pérdidas truncadas por disponibilidad, se muestra adicionalmente el **efecto aplicado realmente**, reconstruido desde el ledger de eventos de Situación (`issue`, `spend`, `reserve_loss`). No se suman ingresos de casilleros, canjes, duelos ni efectos ajenos a la carta.

Las comprobaciones de regresión (`tests/test_narrativa_simlog_v21.py`) cubren cierre con reservas, efecto de un tercero posterior al turno propio, variación anterior, primera ronda, datos faltantes y diferencias entre efecto potencial y aplicado.

## Hitos, subhitos e interacciones visuales en «Ronda a ronda»

Debajo del resumen de recursos de **cada ganador**, se incorporan tres bloques:

1. **Hitos y subhitos · estado al cierre**: Título, Pasaporte/Ciudadanía, Casa y Casamiento, en tarjetas compactas de dos columnas. Estados observados: Logrado/Lograda, En progreso, Pendiente o Sin datos. Se muestran como chips los comprobantes/subhitos propios **vigentes al final de la ronda**, sin adjudicar automáticamente el hito por tener comprobantes.
2. **Avances de esta ronda**: inversiones en subhitos, adjudicaciones (acierto/fallo), compra de Casa (tirada ganada/fallida), Casa lograda/perdida, Casamiento y cesiones de comprobante. Se presentan una vez por evento con secuencia real y resultado.
3. **Interacciones y eventos sociales**: propuestas **realizadas y recibidas** con desenlace unido a la propuesta, pareja formada, duelos iniciados/recibidos (victoria, derrota, empate o retirada), transferencias, cesiones y ayuda con reservas. El pago de un duelo no duplica una segunda tarjeta de transferencia. Las transferencias se identifican como transferencias, **no como acuerdos voluntarios** si no hay constancia de negociación.

Los hitos se reconstruyen del **último snapshot «despues» de `estados_jugadores.csv` y `estados_globales.csv` en la ronda elegida**; nunca de resultados del manifiesto final ni de rondas futuras. Si faltan los snapshots globales se usa el último `turnos.csv` de la ronda como respaldo únicamente para Casa/Casamiento; cuando no hay evidencia se presenta «Sin datos».

El catálogo de costos de los subhitos es la definición vigente del motor v2.1, y el texto de inversión siempre conserva el comprobante registrado. El panel no genera nuevas simulaciones. Cuatro avances y cuatro interacciones por jugador son visibles inicialmente y el resto aparece bajo «Ver más».

Las pruebas de `tests/test_paneles_ronda_v21.py` incluyen estados históricos, sin fuga de resultados futuros, inversión/subhito, compraventa de Casa en pareja, propuestas agrupadas, duelo recibido, duplicación contable, trazas incompletas e integración con un SIMLOG generado realmente.

## Actualización: noviazgo, registro verificable y todas las partidas

- **Noviazgo al cierre de la ronda:** estado explícito `Sin pareja`, `De novios con [jugador]`, `Casados con [jugador]` o `Sin datos`. El dato se toma del **último** `estados_jugadores.csv` con `Momento=despues` de esa ronda; se utiliza `estados_globales.csv` para diferenciar noviazgo de casamiento. Nunca se usa la pareja ganadora del manifiesto final para atribuir una relación a rondas anteriores.
- **Relato de la ronda retirado de la interfaz:** aunque la función anterior producía un texto reproducible para un SIMLOG dado, sus frases contenían interpretaciones y no eran una transcripción literal. Se conservan las pestañas estructuradas de movimientos, decisiones A/B, efectos previstos del catálogo, efectos realmente contabilizados, duelos, hitos e interacciones con su evidencia. Ya no aparece el bloque «Relato de la ronda».
- **Todas las partidas compatibles:** se indexan recursivamente los manifiestos `SIMLOG-2.1` del ruleset vigente en la carpeta principal, carpetas adicionales (una por línea) y el ZIP adjunto. En lugar de reemplazar la fuente cuando se carga un ZIP, sus partidas se **suman** al índice. Se informa cantidad total, por tamaño de mesa, con casamiento y sin casamiento; el filtro `Solo partidas con ganador` empieza **desactivado**.
- **Partidas sin ganador:** no se asignan vencedores ficticios. Se permite seleccionar jugadores para comparar su Gantt y sus acciones ronda a ronda. La selección queda diferenciada por origen y directorio de simulación, incluso cuando coincidan semillas en corridas distintas.
- **Actualizar listado** limpia la caché de descubrimiento si se incorporan archivos mientras la aplicación ya está abierta. No ejecuta nuevos juegos ni modifica partidas previas.
- **Historial incompatible:** los registros de v1.3, v2.0 o salidas agregadas sin trazas SIMLOG v2.1 no pueden mostrar decisiones turno a turno. No se transforman en datos ficticios. Para importarlos es necesario disponer de las trazas reales compatibles.

## Cargar el lote auditado de 200 partidas (semillas 101–200)

Existe una ejecución real con **200 partidas SIMLOG v2.1**, 100 de 6 jugadores y 100 de 10 (semillas 101–200), asociada al GitHub Actions `42454003910` y al artefacto `13606568364` (`simlog-v21-nuevas-semilllas-101-200`). Su ZIP contiene **200 manifiestos** `SIMLOG-2.1` con `ruleset=especificacion-integral-2026-11-08` y trazas CSV por jugador/turno.

El archivo descargado `SIMLOG_v21_200_partidas_semillas_101_200.zip` puede dejarse **sin descomprimir** en `~/Downloads/`. El visualizador detecta automáticamente archivos `SIMLOG*.zip` en Descargas y dentro de `resultados/`, además de las carpetas de trazas y del ZIP elegido con el cargador de archivos. Todos los lotes compatibles se suman al mismo selector y los Run_ID idénticos se muestran una sola vez.

La pantalla ofrece **Actualizar listado de partidas** para incorporar ZIP nuevos sin reiniciar. El lanzador solo genera 10 partidas de demostración si no existe ninguna; no afirma haber ejecutado ni descargado automáticamente las 200 anteriores. Los otros históricos v1.x/v2.0 siguen excluidos del detalle porque no cumplen el esquema y ruleset vigentes.

## Ejecución local

Desde la raíz del repositorio en la rama `feature/visualizador-simlog-v21`:

```bash
python -m pip install -r requirements.txt
python -m streamlit run laboratorio/app.py
```

En el menú lateral o enlace de la portada, seleccionar **Visualizador SIMLOG v2.1**. También se puede abrir directamente:

```bash
python -m streamlit run laboratorio/pages/1_Visualizador_SIMLOG_v21.py
```

Si la carpeta `resultados/` está vacía, generar trazas reales con:

```bash
python -m laboratorio.simular_mazos_vigentes_v2 --semillas 20 --rondas 100 --out resultados/simlog_v21_20261108
```

La carpeta completa se puede seleccionar directamente en el visualizador; también admite un ZIP que contenga los manifiestos y CSV originales. No se altera la rama principal ni los archivos históricos.

## Pruebas

```bash
python -m unittest discover -s tests -p 'test_visualizador_simlog_v21.py' -v
```

Las pruebas incluyen ganadores/censuradas, versión estricta, ZIP y carpeta, clasificación de duelos, acciones de la pareja, canjes, inversión, cronología, filtros y SHA-256 alterado. CI: `.github/workflows/visualizador-simlog-v21.yml`.
