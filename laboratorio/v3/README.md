# Laboratorio de Balance v3.0 — Fase 1: matriz económica integral

**Estado:** matriz v3.0 + modelo de economía + optimizador multiobjetivo + simulador económico **experimental de primera versión** con partidas reales bajo reglas simplificadas. NO es todavía una calibración de v3.0 validada ni un reglamento completo.

**Documento rector:** [Clarisa_y_Lucas_Especificacion_Conceptual_v3_0.docx](https://docs.google.com/document/d/1AfX65pZX_XmXwsPLMwkXAqg5gL1BfzKB/edit) (14/11/2026).

## Propósito que no debe perderse

Determinar, con matemáticas, experimentación y simulaciones, **cuánto debe generar, consumir, reservar o requerir cada mecanismo** para equilibrar economía, ritmo de las etapas y caminos de victoria de Clarisa & Lucas v3.0. La optimización modifica **cantidades**; no rediseña las mecánicas. Los importes de v2.x no se importan automáticamente.

## Archivos

- `matriz_economica_v3.json`: fuente canónica del catálogo de 181 parámetros sin valores numéricos.
- `matriz_economica_v3.csv`: exportación tabular para revisar en Excel/Sheets.
- `catalogo.py`: lector, auditor de integridad, exportador CSV y calculador de emisión esperada, sujeto a frecuencias y cantidades explícitas.
- `modelo_matematico.py`: proyecciones de flujos, reparto inverso de premios, demanda de rutas y tasas objetivo por etapa.
- `escenario_didactico_NO_CALIBRADO.json`: ejemplo sintético con cantidades arbitrarias claramente rotuladas.
- `ejecutar_modelo.py`: ejecución sin simulación de las tres rutas conceptuales usando el ejemplo.
- `optimizar.py`: búsqueda entera conjunta de premios/costos, cinco objetivos y soluciones no dominadas.
- `escenario_optimizacion_NO_CALIBRADO.json`: supuestos didácticos con ocho parámetros ajustables (1.296 combinaciones), sin datos v3.0 observados.
- `tests/test_optimizador_economico_v3.py`: pruebas de evaluación económica, búsqueda reproducible y Pareto.
- `tests/test_matriz_economica_v3.py`: controles del catálogo.
- `tests/test_modelo_matematico_v3.py`: pruebas del modelo, reservas, transferencias, metas, Casa y comparación de rutas.

Las 96 filas `SIT_*` corresponden a **plantillas** etapa × rol × opción × recurso × signo (ganancia/pérdida). No son 96 cartas distintas ni reemplazan el catálogo final de cartas. Las ocho filas `PERFIL_*` representan una plantilla por rol × recurso; en la siguiente fase se expandirán por tipo real de Perfil.

## Glosario de flujos

| Flujo | Relevancia para la contabilidad | Cuenta como creación? |
|---|---|---|
| EMISION | Aumenta el saldo libre | Sí |
| CONSUMO | Reduce recursos disponibles definitivamente | No |
| RESERVA | Pasa recursos libres a reserva, sin destruir fichas | No |
| INVERSION | Pasa recursos libres a proyecto, protegido | No |
| REQUISITO | Comprueba saldo sin mover fichas | No |
| TRANSFERENCIA | Mueve fichas entre jugadores, total global igual | No |
| CONSUMO/TRANSFERENCIA | Casa: banca o propietarios según resultado | No |
| CONVERSION | Banco: retira origen y crea destino según tasa; contabilizar ambos lados | No como creación externa neta sin compensación |
| OBJETIVO | Cuota a alcanzar para ganar, sin importe aprobado | No |
| CONTROL | Decisión reglamentaria abierta, no cuantificar aún | N/A |
| OBJETIVO_ANALITICO | Meta de tiempo o de participación, no una regla | N/A |

Cada unidad solo puede encontrarse en **un estado**: libre, reservada, invertida o consumida/transferida.

## Contrato matemático para la siguiente fase

Para jugador `i`, recurso `r` y turno `t`:

```text
Libre_fin = Libre_inicio
          + Emisiones
          + Transferencias_entrantes - Transferencias_salientes
          - Consumos - Perdidas_efectivas
          - Nuevas_reservas + Reservas_liberadas
          - Nuevas_inversiones + Reintegros_legales
          + Conversión_recibida - Conversión_entregada

Reserva_fin = Reserva_inicio + Nuevas_reservas - Reservas_liberadas - Perdidas_de_reserva
Inversión_fin = Inversión_inicio + Nuevas_inversiones - Inversiones_liquidadas
```

No sumar `REQUISITO` a `CONSUMO`; no contar `TRANSFERENCIA` como producción de la mesa.

Para fuente `m`, etapa `s`, recurso `r`:

```text
Emisión_esperada(s,m,r) = frecuencia_observada(s,m) * premio_medio(s,m,r)
Emisión_bruta(s,r)      = sum_m Emisión_esperada(s,m,r)
Participación(s,r)      = Emisión_bruta(s,r) / sum_k Emisión_bruta(s,k)
```

Las frecuencias se estimarán con SIMLOG-3.0; las cantidades se optimizan y **permanecen vacías** hasta que existan escenarios explícitos. La función `emisiones_esperadas` exige cantidades conocidas para cualquier evento con frecuencia positiva.

### Evaluación de objetivos

- **UTN/Dublín**: son umbrales, no pagos (salvo nueva regla expresa).
- **Título/Pasaporte**: subhitos invertidos y adjudicación individual, con variabilidad y disputas.
- **Pareja/Casa**: reservas inmovilizadas pero no consumidas por el solo hecho de reservar.
- **Cartas de Afinidad**: mismo recurso = cuota única; distintos recursos = dos cuotas. La cantidad sigue abierta. Pago terminal B es contabilidad de cierre, sin suponer que altera la fecha de victoria frente a simple tenencia.
- **Falso Lucas**: objetivo individual de Dinero más Casa vigente, no una cuota compartida con Clarisa.

Los tres tipos de victoria deben analizarse por separado, sin asumir que tienen idéntica probabilidad óptima.

## Fase 2 — Modelo matemático implementado

El objetivo que se mantiene es cuantificar **cuánto debe generar y exigir cada mecanismo**, dados una duración deseada, una frecuencia de activación y una demanda por etapa. La matriz de 181 filas sigue sin valores; el modelo usa exclusivamente parámetros que se suministran en cada escenario.

### Componentes y ecuaciones

1. **Proyección de flujos (`proyectar_flujos`)**. Para evento económico `e` del mecanismo `m`, etapa `s` y recurso `r`:
   `Emision(s,r,m) = sum_e frecuencia_observada(e) × importe_efectivo(e)`.
   Reporta emisiones, consumos, inversiones, reservas y volumen transferido en categorías distintas. Los consumos negativos de Situación deben utilizar pérdidas **efectivas**; los valores nominales emiten advertencia. Las activaciones por carta de Situación y Perfil pueden declarar `instancia` con su importe particular, evitando presupuestar todas las cartas con un único promedio. La frecuencia de cada plantilla debe normalizarse por jugador/ronda de la etapa.

2. **Demanda secuencial (`calcular_demanda_secuencial`)**. Recorre una ruta explícita de hitos y calcula la **inyección mínima justo a tiempo**, con saldos libres por participante:
   `Faltante_evento = max(0, cuota - saldo_libre_elegible)`.
   Un `REQUISITO` solo exige stock, no lo descuenta. Una `RESERVA` inmoviliza; una `INVERSION` sale de libre y queda registrada como invertida; un `CONSUMO` descuenta; una `TRANSFERENCIA` no crea recursos de mesa. Las metas de cartas compartidas se comprueban/pagan conjuntamente (una sola cuota cuando coincide recurso), y la meta de Falso Lucas se evalúa **individualmente**. La transferencia de Casa a propietarios es egreso para el comprador, pero no destrucción global.

3. **Tasas objetivo (`tasas_desde_demanda`)**. Para objetivos por etapa y recurso:
   `Tasa(s,r) = (demanda_justo_a_tiempo(s,r) + pérdida_esperada(s,r) + holgura(s,r)) / (rondas(s) × participantes_productores(s))`.
   No se suponen rondas ni pérdidas por defecto cuando existe demanda positiva; se deben informar explícitamente. Estas tasas son una **cota optimista de planificación**, no una garantía de obtener los recursos a tiempo.

4. **Calibración inversa (`calibrar_emisiones`)**. Dada tasa objetivo `Tasa(s,r)`, cuota deseada `peso_m` para cada mecanismo y frecuencia `F_m`, propone:
   `Premio_medio_m = Tasa(s,r) × peso_m / F_m`, con `Σ_m peso_m = 1`.
   Reporta valores continuos y sus vecinos enteros; no afirma que redondear cada fuente sea una solución óptima. Si se asigna cuota a una fuente que nunca se activa, el escenario se rechaza.

### Tres vías de victoria

El ejemplo simula **exclusivamente su presupuesto económico**, no su viabilidad reglamentaria, trayectoria ni probabilidad:

| Ruta conceptual | Titulares de la victoria | Fórmula económica |
|---|---|---|
| Boda Clarisa + Lucas auténtico | Ambos | Reserva Casa + pago Casa + pago conjunto de dos metas de Afinidad |
| Boda Clarisa + Falso Lucas | Solo Clarisa | Mismo presupuesto de boda, distinta titularidad de victoria |
| Casa + M de Falso Lucas | Solo Falso Lucas | Reserva Casa + pago Casa + comprobación individual de M |

Las cantidades de demostración son **arbitrarias**: los resultados no deben publicarse como valores calibrados. El Falso Lucas no gana por casamiento. El modelo permite comparar demanda, pero aún no calcula probabilidad de victoria ni dinámica de consentimiento/pareja. Los pasos de inversión/hitos en Juventud pueden configurarse como una secuencia, pero la muestra didáctica comienza en Adultez con proyectos y Pareja previamente satisfechos.

### Ejecutar los cálculos de forma reproducible

```bash
python -m unittest discover -s tests -p 'test_modelo_matematico_v3.py' -v
python -m laboratorio.v3.ejecutar_modelo --salida /tmp/modelo_economico_v3_ejemplo.json
```

Para escenarios personalizados, copiar `escenario_didactico_NO_CALIBRADO.json` a un archivo separado y pasar `--escenario archivo.json`. **No modificar el archivo de muestra en sí como si fuera la configuración aprobada.**

### Lo que NO se ha demostrado

- No hay frecuencias medidas a partir de partidas **v3.0**: las frecuencias del ejemplo son hipótesis explícitas. La frecuencia real de llegada a casilleros y activación de Perfiles depende del movimiento, emparejamiento y agentes.
- No se ha corrido un simulador v3.0 ni un optimizador multiobjetivo.
- No se han fijado metas de rondas, pesos de composición, márgenes ni cantidades definitivas.
- La demanda secuencial es una cota inferior **idealizada**, pues presupone transferencias legales instantáneas entre participantes autorizados, obtención de Casa al primer intento y recursos disponibles justo antes de cada hito; no considera azar, carreras contra otras parejas, pérdidas futuras o consentimientos.
- El método no adjudica proyectos ni devuelve automáticamente inversiones: solo modela recursos libres comprometidos; el futuro simulador deberá registrar las liquidaciones reales.
- Las variantes reglamentarias abiertas no se aprueban por ejecutar el ejemplo.


## Fase 3 — Optimizador conjunto inicial (NO simulación)

**Finalidad:** recomendar combinaciones de cantidades de premios, costos y metas bajo **frecuencias, ventanas de tiempo y funciones de utilidad dadas explícitamente**. Ninguno de esos datos es una regla o un resultado v3.0 observado: el motor de partidas sigue pendiente.

### Qué optimiza

1. `deficit`: faltantes económicos de rutas y etapas, divididos por la demanda de cada ruta. Nunca se compensa un faltante en A con exceso de M.
2. `excedente`: recursos disponibles al final de cada ruta tras descontar sus demandas.
3. `desviacion_mezcla`: diferencia entre proporción real de emisión bruta y composición objetivo expresamente configurada por etapa.
4. `disparidad_rutas`: diferencia relativa de presión económica entre rutas de boda auténtica, boda con Falso Lucas y victoria individual.
5. `desviacion_presion`: distancia entre recursos demandados/emitidos y la tensión económica de referencia (hipótesis de diseño, no duración predicha).

El puntaje escalar se utiliza **solo** para ordenar alternativas con pesos declarados en el escenario. Además, se devuelve la frontera de Pareto de las combinaciones **evaluadas**. En una búsqueda exhaustiva (espacio pequeño), esa frontera es completa para los dominios proporcionados; con búsqueda local, no se garantiza globalidad.

**Importante:** el presupuesto de emisión usa `activaciones_por_ronda_mesa` —cantidad de activaciones del mecanismo en la **mesa entera** por ronda— y `rondas_por_etapa`. Por ejemplo, un aterrizaje que acredite el premio a ambos integrantes debe computar **dos activaciones**, no una. No multiplicar esas frecuencias nuevamente por el número de participantes.

### Experimento reproducible de prueba

```bash
python -m unittest discover -s tests -p 'test_optimizador_economico_v3.py' -v
python -m laboratorio.v3.optimizar \
  --escenario laboratorio/v3/escenario_optimizacion_NO_CALIBRADO.json \
  --max-evaluaciones 1500 \
  --salida /tmp/optimizacion_v3.json
```

La muestra introduce **8 parámetros enteros variables** (recompensas de casillero, Situación y Perfil; precio de Casa; dos metas de Afinidad; cuota de Falso Lucas), con un espacio de 1.296 combinaciones. Incluye rutas para los **tres cierres v3.0**, con pesos de evaluación, intervalos de valores, presión objetivo, mezcla y duraciones arbitrarias etiquetadas como hipótesis. No deben confundirse con parámetros de juego aprobados.

El resultado JSON informa la mejor combinación **condicionada a esos supuestos**, desglose de emisiones, demanda por ruta, déficit por recurso, y frontera Pareto de alternativas.

### Límites y prerrequisitos de la siguiente fase

- La generación `G=F×Q` presupone frecuencias constantes; en partidas reales, **F cambia cuando modifican premios y costos** y los bots alteran sus rutas. La búsqueda real deberá reestimar activaciones simulando cada configuración o usando un sustituto verificado.
- La demanda secuencial supone recursos disponibles justo a tiempo y, para cuotas conjuntas, cooperación idealizada. **No comprueba** si los recursos de Falso Lucas son propios, si acepta pagos, ni si mantiene Casa cuando corresponde. La modelización del falso y de la pareja debe validarse en un motor de juego.
- Las pérdidas reales dependen del saldo; esta etapa no predice sus truncamientos estocásticos.
- No genera tiempos reales ni probabilidades de victoria. Las tres rutas son **presupuestos**; las recomendaciones no pueden declararse balance del juego.
- No se optimizan todavía los 181 parámetros simultáneamente: son el catálogo íntegro, no un número manejable de variables independientes a explorar exhaustivamente. Corresponde seleccionar ámbitos de sensibilidad y usar búsqueda local/por lotes.
- Las decisiones reglamentarias abiertas siguen como variantes; ninguna queda aprobada automáticamente por una puntuación.

**Siguiente implementación:** completar reglas de interacción que afectan la economía, reforzar políticas de agentes y conectar frecuencias observadas del simulador experimental con la optimización, sin atribuir resultados de muestra a una calibración definitiva.

---

### Próxima fase

Medir con trazas v3.0 reales la frecuencia `F_m` de cada mecanismo y el porcentaje efectivo de pérdidas, e implementar la optimización de **costos y premios conjuntamente** sobre rutas reproducidas con múltiples políticas y mesas de 6/10 jugadores. El modelo matemático actual ofrece la interfaz que consumirá ese simulador y el optimizador.

---

## Fase 4 — Simulador económico v3.0 ejecutable (VERTICAL EXPERIMENTAL)

**Objetivo:** sustituir frecuencias supuestas por activaciones observadas en partidas efectivamente recorridas; NO confundir esta maqueta de economía con la especificación reglamentaria completa ni con un balance calibrado.

**Código**:
- `simulador_experimental.py`: motor reproducible, 6/10 participantes, agentes `planificador` o `aleatorio`, lotes, eventos SIMLOG-3.0 y generación de indicadores.
- `estado_v3.py`: asientos contables con invariantes de saldo, reservas, inversiones y transferencias.
- `escenario_simulacion_NO_CALIBRADO.json`: **36 importes económicos arbitrarios**, 24 Situaciones sintéticas y Perfiles prototipo. Todos configurados fuera del motor, sin reutilizar valores históricos.
- `tests/test_simulador_experimental_v3.py`: pruebas de invariantes, regresión y casos de victoria.

**Soportado en este primer vertical**: seis mazos independientes por etapa y rol con Situación compartida por ronda; cobro infantil solo al caer; nodo UTN y reintentos; movimiento juvenil A/B acoplado a Situación, cartas individuales de movimiento repartidas por ronda; subhitos y adjudicación experimental de Título y Pasaporte con comprobantes simplificados; formación de Pareja y reserva A; movimiento conjunto con turnos individuales; vuelo a Dublín, Perfil inicial y revelación simultánea de identidades/cartas; Adultez 5×5 con ocho direcciones y rebote; mano adulta sin reposición por turno; Casa 2D6, reservas, pago a banca/propietarios; pago terminal de metas de Afinidad, y tres tipos de cierre (boda auténtica, boda con Falso Lucas —solo gana Clarisa—, victoria individual del falso con Casa y dinero propio).

**Contabilidad:** todos los movimientos de fichas se emiten como asientos cronológicos por jugador, recurso, origen y destino. `comprobar()` verifica tras cada turno `stock_total = fichas_emitidas - fichas_consumidas`. Los premios se clasifican por origen en Casillero, Situación y Perfil; pérdidas nominales versus efectivas, inversión y reserva se distinguen de emisión externa.

**Hipótesis reglamentarias explícitas, NO aprobadas**: 3 cartas de mano adulta, Neutro −2..+2, límites del eje, 30 pares de movimiento adulto sin A=B, repetición de mazos agotados, umbrales de adjudicación con D6, aceptación automática de Pareja, consentimiento de Falso Lucas, primera posición de retorno juvenil y opción del agente de entrar o no a UTN antes de alcanzar los umbrales. Todas las cantidades están en el escenario, no en el motor.

**NO soportado todavía:** duelos ordinarios, disputas completas y cesiones de Títulos/Pasaportes, cambio voluntario de rol y Perfil, mercado de Perfiles, negociaciones entre cualquier par de jugadores, banco de conversiones, variedad estratégica suficientemente realista ni diseño definitivo de las 102 cartas del catálogo de v2.x (v3.0 todavía no definió sus tamaños finales). El proyecto de hito se aproxima como un proyecto compartido activo por tipo; hay adjudicaciones, pero no las competencias avanzadas completas. La simulación NO valida reglas abiertas ni es todavía apta para balance económico final.

### Ejecutar

```bash
python -m unittest discover -s tests -p 'test_simulador_experimental_v3.py' -v

python -m laboratorio.v3.simulador_experimental \
  --jugadores 6 --partidas 12 --semilla 2001 --politica planificador \
  --salida /tmp/lote_v3_6.json --traza /tmp/traza_v3_6.json

python -m laboratorio.v3.simulador_experimental \
  --jugadores 10 --partidas 12 --semilla 2001 --politica planificador \
  --salida /tmp/lote_v3_10.json --traza /tmp/traza_v3_10.json
```

El reporte incluye cantidad de partidas cerradas y **censuradas**, mediana/p80 **solo de partidas terminadas**, generación por etapa/recurso/mecanismo, pérdidas efectivas y frecuencias de activación por jugador-ronda y por mesa-ronda de la etapa. El SIMLOG de la primera partida se exporta con `--traza`; las demás se resumen.

### Resultados iniciales de control — no calibrados

Escenario sintético, agentes planificadores, semillas 2001–2012:

| Métrica | 6 participantes | 10 participantes |
|---|---:|---:|
| Partidas | 12 | 12 |
| Bodas auténticas | 7 | 8 |
| Victoria individual de Falso Lucas | 5 | 4 |
| Bodas con Falso Lucas | 0 | 0 |
| Sin cierre | 0 | 0 |
| Mediana (cierres) | 23 | 23,5 |
| p80 (cierres) | 34 | 35 |

Estas 24 partidas confirman **ejecución y reproducibilidad del escenario**, no justicia, competitividad, duración objetivo ni dificultad equilibrada de recursos. No constituyen prueba de que las tres vías de victoria sean igualmente viables. Antes de validar v3.0 necesitamos completar las mecánicas omitidas, ampliar agentes, recalcular frecuencias cuando cambian los premios y simular miles de semillas diferentes para calibración y validación.

### Experimentos de sensibilidad apareada (cierre de primera conexión)

`sensibilidad_experimental.py` compara **las mismas semillas** para dos o más configuraciones, preservando el escenario económico base, identificando variables alteradas y midiendo nuevamente **las activaciones** en cada partida. Se exportan reportes con:
- Cierres, duración de ganadoras y censura.
- Variación observada de rondas por semilla.
- Cantidad de fuentes cuya frecuencia cambió y diferencia de activaciones por jugador-ronda.

`sensibilidad_v3_NO_CALIBRADA.json` incluye cuatro pruebas didácticas:
1. Casa de 4 a 6 M por integrante.
2. Casillero adulto de Dinero F3C5 de 4 a 6 M.
3. **Estrés**: Casa de 4 a 24 M por integrante.
4. **Estrés**: meta individual de Dinero de Falso Lucas de 13 a 45 M.

```bash
python -m unittest discover -s tests -p 'test_sensibilidad_v3.py' -v
python -m laboratorio.v3.sensibilidad_experimental \
  --jugadores 6 --partidas 12 --semilla 2001 \
  --salida /tmp/sensibilidad_v3_6.json
```

**Diagnóstico inicial** (24 partidas de dos tamaños, 12 por tamaño, semillas 2001–2012):

| Cambio en muestra sintética | 6 jugadores: bodas auténticas / victorias falso | 10 jugadores: bodas auténticas / victorias falso |
|---|---|---|
| Base | 7 / 5 | 8 / 4 |
| Casa +2 M | 7 / 5 | 8 / 4 |
| Casillero Dinero +2 M | 7 / 5 | 8 / 4 |
| Casa +20 M | 6 / 6 | 9 / 3 |
| Meta Falso Lucas 45 M | 7 / 5 | 9 / 3 |

Los cambios pequeños no alteraron rondas ni ganadores de la muestra; **no** es prueba de irrelevancia universal. El estrés de Casa modificó frecuencias de 58 y 62 fuentes, respectivamente, confirmando que el simulador puede detectar efectos económicos indirectos. El aumento de Casa en seis jugadores redujo la duración observada promedio en esta muestra; **no** significa que encarecer Casa acelere sistemáticamente la partida. Las vías de cierre y el azar competitivo pueden cambiar.

**Limitación estadística adicional:** aparear semillas no garantiza que los mismos dados/eventos aleatorios permanezcan perfectamente sincronizados cuando un cambio económico altera la cantidad u orden de tiradas. Antes de usar estos efectos como sensibilidad causal será conveniente emplear subflujos aleatorios separados por mecanismo y verificar los eventos en trazas. Las 12 partidas por tamaño son insuficientes para seleccionar valores definitivos.

### Siguiente dependencia del objetivo central

Conectar las **frecuencias observadas** de SIMLOG-3.0 al optimizador (que hoy todavía usa frecuencias declaradas), recalculándolas para cada escenario de premios/costos. La optimización deberá contrastar configuraciones con las **mismas semillas** y múltiples políticas, comparar rutas con ingresos individuales reales y no solamente presupuestos ideales. Un escenario con porcentajes aparentemente perfectos pero rutas bloqueadas o beneficios estratégicos inexistentes debe ser rechazado.

---

## Límites de la matriz y de los datos (Fases 1–2)

1. **No** se asignaron cantidades, frecuencias, costos ni distribuciones históricas.
2. La definición final de premios por paso/destino en Juventud sigue abierta.
3. Los casilleros A/P/K/M de Adultez se identifican según el tablero conceptual v3.0, no v2.3.
4. No se han resuelto por implicación reglas de consentimiento, devolución de reservas, empate de victorias, reciclado de cartas o cambio de rol de Falso Lucas.
5. No se ha calibrado ni simulado v3.0; el resultado actual es una **matriz inspeccionable**, no una recomendación numérica.

## Comandos locales

```bash
python -m laboratorio.v3.catalogo --validar
python -m laboratorio.v3.catalogo --csv /tmp/matriz_economica_v3.csv
python -m unittest discover -s tests -p 'test_matriz_economica_v3.py' -v
```

## Condición para pasar a Fase 2

Cobertura auditada de todas las fuentes, consumos, reservas, umbrales y objetivos de la v3.0, identidades únicas, descripciones trazables y cero valores heredados. A continuación: medir las frecuencias de activación, modelar la demanda por etapa e introducir escenarios de calibración sin modificar v2.x.
