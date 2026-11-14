# Laboratorio de Balance v3.0 — Fase 1: matriz económica integral

**Estado:** matriz v3.0 + modelo determinista de economía + optimizador entero multiobjetivo de escenarios explícitos. **No** es todavía un simulador v3.0 ni una calibración validada con partidas.

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

**Próxima implementación:** simulador económico reproducible v3.0 con instrumentación de frecuencia real de fuentes, demanda por actor, ventanas de pago, decisiones A/B, movimiento y final de partida. Solo entonces cerrar el ciclo de calibración cuantitativa y evaluar robustez de resultados.

---

### Próxima fase

Medir con trazas v3.0 reales la frecuencia `F_m` de cada mecanismo y el porcentaje efectivo de pérdidas, e implementar la optimización de **costos y premios conjuntamente** sobre rutas reproducidas con múltiples políticas y mesas de 6/10 jugadores. El modelo matemático actual ofrece la interfaz que consumirá ese simulador y el optimizador.

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
