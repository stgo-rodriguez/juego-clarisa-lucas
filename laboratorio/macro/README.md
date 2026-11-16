# Ecualizador macro de recursos · Clarisa & Lucas

Segunda herramienta, **independiente** del Ecualizador Teórico v3.1 detallado:
- Macro: [abrir](https://stgo-rodriguez.github.io/juego-clarisa-lucas/laboratorio/macro/ecualizador.html)
- Detallado: [abrir](https://stgo-rodriguez.github.io/juego-clarisa-lucas/laboratorio/v3/ecualizador.html)

## Finalidad

Calibrar proporciones y volúmenes a escala de **etapa y mecanismo**, antes de discutir cuánto entrega cada casillero o qué números llevan las cartas.

Para cada etapa (Infancia, Juventud, Adultez), se modela:
- **Casilleros**: frecuencia esperada de cobro (activaciones/ronda), volumen recibido en múltiplos de V, proporción A/P/K/M. No se especifican casilleros.
- **Cartas de Situación**: frecuencia esperada, volumen que entregan y volumen que **quitan** por separado, con mezclas A/P/K/M distintas. Promedia decisiones A/B sin atribuir frecuencias no medidas.
- **Perfiles**: producción por activación y frecuencia de activación equivalente por ronda. Solo Juventud y Adultez. No presupone circuitos, vueltas ni cobros de entrada.
- **Interacciones/otros**: mecanismo opcional con balance neto y frecuencia, desactivado por defecto.
- **Objetivos**: cuota total N×V y ponderaciones por recurso. Incluye UTN (P/K), Título, Pasaporte, vuelo a Dublín, Casa, Casamiento, o ruta alternativa de Falso Lucas. Las ponderaciones son hipótesis de presupuesto macro, no requisitos reglamentarios.
- **Duración objetivo** por etapa. En Infancia se adopta la meta de diseño indicada por el usuario de 5 rondas; Juventud y Adultez están inicialmente sin definir.

## Cálculo y unidades

La **unidad V** es un cambio de escala uniforme, inicialmente V=1 unidad normalizada. Las cantidades de mecanismos y objetivos se introducen en múltiplos de V, nunca como importes aprobados:

Para mecanismo m, recurso r, etapa e:

    fraccion_positiva[m,r] = peso_positivo[m,r] / Σ_peso_positivo[m,*]
    fraccion_negativa[m,r] = peso_negativo[m,r] / Σ_peso_negativo[m,*]
    produccion[e,m,r] / V =
        frecuencia[e,m] ×
        (ganancia[e,m] × fraccion_positiva[m,r]
         − perdida[e,m] × fraccion_negativa[m,r])

Para objetivos g seleccionados por ruta:

    presupuesto[e,r] / V =
        Σ_g multiplicador_N[g] × fraccion_objetivo[g,r]

La tasa neta por recurso suma la contribución de todas las fuentes. Se calcula:

    rondas_cobertura[e] =
        máximo de presupuesto[e,r] / tasa_neta[e,r] entre recursos requeridos

Con una demanda positiva y tasa neta no positiva, el presupuesto es inalcanzable por generación neta. Con parámetros faltantes, el resultado es N/D, **no cero**. Un recurso con demanda cero no genera cuello de botella.

La herramienta muestra por etapa el **factor uniforme de volumen neto** requerido para cubrir el presupuesto dentro de las rondas objetivo:

    factor = rondas_cobertura / rondas_objetivo

Por ejemplo, factor 1,5 significa que, conservando proporciones y todos los N, las tasas netas deberían multiplicarse por 1,5 para cubrir el presupuesto dentro del horizonte fijado. No significa que subir las cartas un 50% baste si también aumentan sus pérdidas.

**La cantidad de rondas es independiente de la escala V** cuando todo lo demás permanece en múltiplos de V. Se puede elegir V=1 o V=100 y los tiempos económicos no cambian.

## Qué se considera dato y qué hipótesis

- Los **ratios históricos de mezcla** que se ofrecen como referencia por etapa son: Infancia A50/P30/K20/M0; Juventud A17/P25/K42/M17; Adultez A27/P18/K9/M45. Se normalizan porque algunos porcentajes redondeados no suman 100. Son objetivos orientativos, no premios reglamentarios.
- Por defecto todos los **volúmenes** y las **metas N** permanecen en \`null\`, sin definir. En las cartas se conoce únicamente una activación por turno/rol; en infancia se usa una frecuencia estructural de un cobro de casillero por turno en el circuito, que deja de corresponder cuando se entra a UTN.
- Para mostrar resultados rápidos existe **«Cargar ejemplo ilustrativo»**. Los valores de ese ejemplo son deliberadamente hipotéticos; ninguna regla del juego cambia.
- La edad y el rol del personaje no se modelan por separado: se usa un **jugador representativo** como unidad de análisis.
- Las cuotas de acceso/tenencia (UTN, vuelo, Casa) se agregan al presupuesto como si fueran demandas de volumen, aunque **en el reglamento pueden ser comprobaciones o reservas y no consumos**. Si las sumas afectan al orden de pagos, la estimación de tiempo puede sobrecontar o infracontar la dificultad. Solo sirve como indicador de presión de recursos.
- Las cartas A/B no son independientes en una partida; el macro no modela elecciones, afinidad, duelos, posiciones, mano de movimiento, rutas ni competencia.
- **No es una simulación ni un pronóstico de duración de juego**. Son tasas esperadas y un índice de cobertura de presupuesto. Para el tiempo de acceso y examen de UTN se mantiene el ecualizador detallado de Markov v3.1.

## Uso práctico

1. Abrir la página macro.
2. Pulsar **Cargar ejemplo ilustrativo**, o introducir volúmenes y metas N manualmente desde cero.
3. Elegir Infancia, Juventud o Adultez.
4. Seleccionar una fuente, ajustar **activaciones/ronda**, **ganancia por activación**, **pérdida por activación** y proporción por recurso (sus pesos se normalizan a 100%).
5. Seleccionar un objetivo, ajustar **N × V** y la mezcla requerida A/P/K/M.
6. Observar la composición de la producción, el presupuesto por recurso, los déficits, el recurso limitante, las rondas de cobertura y el factor de aumento de producción neta que exigiría el horizonte objetivo.
7. Cambiar la ruta adulta entre boda y Falso Lucas sin mezclar ambos desenlaces.
8. Exportar o importar JSON del escenario. La aplicación guarda cambios automáticamente en un espacio de almacenamiento local **diferente** del usado por el ecualizador detallado.

## Archivos y pruebas

- \`catalogo_macro.json\`: parámetros abiertos y mezclas de referencia.
- \`engine.js\`: evaluador de flujos y presupuesto sin dependencia de DOM.
- \`ejemplo.js\`: escenario demostrativo puro, nunca aplicado por defecto.
- \`app.js\`, \`ecualizador.html\`: interfaz.
- \`tests/test_macro.cjs\`: pruebas del modelo y sintaxis JS.

Ejecutar:

\`\`\`bash
node laboratorio/macro/tests/test_macro.cjs
\`\`\`

El ecualizador detallado existente permanece en \`laboratorio/v3/\`.
