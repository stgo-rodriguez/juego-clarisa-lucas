# Ecualizador Teórico v3.1 · Clarisa & Lucas

Prototipo de balance analítico basado en la especificación conceptual del 14 de noviembre de 2026. El repositorio original no contenía la carpeta `laboratorio/v3`; esta implementación la crea, sin modificar los motores ni las pantallas anteriores.

## Abrir

GitHub Pages: [Ecualizador Teórico v3.0](https://stgo-rodriguez.github.io/juego-clarisa-lucas/laboratorio/v3/ecualizador.html)

En local, desde la raíz del repositorio:

```bash
python -m http.server 8000
# abrir http://localhost:8000/laboratorio/v3/ecualizador.html
```

## Componentes

- `matriz_economica_v3.json`: catálogo único, con importes económicos `null` hasta que se calibren.
- `engine.js`: cálculo determinista en navegador, instantáneo al variar parámetros.
- `modelo_matematico.py`: módulo Python reutilizable `evaluar(config)`.
- `ecualizador.html`: tablero de controles, producción por recurso, hitos, cuellos, comparación y exportación.
- `infancia_markov.js` / `infancia_markov.py`: modelo de Markov controlado (MDP) para tiempo esperado de aprobación UTN.
- `calibrador_utn.js`: búsqueda inversa de premios enteros P/K sin cambiar automáticamente la economía.
- `tests/`: pruebas de reglas económicas y estados absorbentes (Python y JavaScript).

Ejecutar la evaluación por línea de comandos:

```bash
python laboratorio/v3/modelo_matematico.py laboratorio/v3/matriz_economica_v3.json
python -m unittest discover -s laboratorio/v3/tests -p 'test_*.py'
node laboratorio/v3/tests/test_engine.cjs
node laboratorio/v3/tests/test_markov.cjs
```

## Alcance matemático del primer prototipo

Se usa la esperanza de producción por ronda y una **cota económica optimista** para reunir requisitos, con acumulación paralela de recursos y secuencia Infancia → Juventud → Adultez. En los proyectos juveniles se computan inversiones acumuladas de tres subhitos y pagos de adjudicación; se conservan por separado las comprobaciones UTN/Vuelo y las reservas Pareja/Casa. Las metas de afinidad compartidas nunca se duplican, y las metas diferentes se exigen conjuntamente. La victoria monetaria de Falso Lucas es individual.

El cálculo base no inventa valores ni interpreta `null` como cero. Una tasa conocida nula o negativa con déficit vuelve económicamente inalcanzable un objetivo; los valores faltantes muestran N/D. La frecuencia 1/6 de casilleros de Infancia proviene de la distribución del D6 en el circuito de seis destinos mientras se permanece en él. Las tasas de visita de Juventud y Adultez quedan por definir; no se impone uniformidad. Las Situaciones se diferencian por etapa/rol y se modelan con probabilidad A/B.

**No es aún una predicción completa de rondas de partida.** La ruta hacia UTN, la tirada de examen, distancias de movimiento, las visitas reales, la adjudicación por dados, la competencia entre parejas, la compatibilidad A–Neutro–B, el consentimiento y las interacciones no están integrados en un modelo probabilístico de primera llegada. Sin esos datos no hay tiempo central, conservador ni p80 justificables.

**Aproximaciones pendientes de refinar:** el modelo agrega recursos en flujos netos esperados, sin resolver la truncación por saldo libre de las pérdidas ordinarias; no modela deshacer reservas ni transferencias reales; usa un reparto parametrizado del precio de Casa; acredita el cobro único inicial de Perfil al entrar en Adultez, pero sus cantidades deben configurarse por rol; no modela frecuencia de intentos de adjudicación ni las demoras por posición. Al elegir la variante de pago terminal de afinidad, se ensaya esa hipótesis sin darla por aprobada como regla final.

## Cómo usar

1. En **Generación**, fijar premios por mecanismo y frecuencia de visitas o activaciones; los campos vacíos quedan sin identificar.
2. En **Costos y metas**, introducir cuantías de inversión, reserva, tenencia y pago.
3. En **Supuestos**, elegir objetivos de afinidad y el reparto del precio de Casa; las configuraciones de 6/10 jugadores son escenarios de mesa, pero no se introduce aún competencia dependiente del número.
4. Revisar el efecto en las tasas de A/P/K/M, hitos, objetivos de victoria y cuellos.
5. Guardar, duplicar, comparar y exportar el escenario como JSON o la matriz de flujos en CSV.

## Procedencia de reglas

[Especificación conceptual v3.0](https://docs.google.com/document/d/1AfX65pZX_XmXwsPLMwkXAqg5gL1BfzKB/edit). Ningún valor monetario o de recompensa de v2.x fue promovido a norma v3.0.

## v3.1 — Infancia y UTN probabilísticos

**Meta del diseñador:** 5 rondas **esperadas** para aprobar UTN. No es una nueva regla de recursos.

El modelo cuenta rondas hasta **aprobar** el examen (no hasta entrar en Juventud) para el rol seleccionado. Distingue estados de posición del circuito (1–6), P/K libres, UTN (examen), regreso obligatorio y aprobación absorbente. La transición de cada D6 es uniforme; entrar desde la bifurcación del casillero 5 consume un paso y pierde el excedente. Solo cobrar al terminar exactamente el movimiento. La Situación se aplica al final del turno, incluido el ingreso y los intentos de examen. Al entrar no se rinde hasta el turno siguiente; entonces el examen aprueba 4, 5 o 6 (probabilidad 1/2), se reintenta cada turno si se falla y se mantienen los recursos. Si después de una Situación en UTN faltan P/K, el turno siguiente se dedica a regresar a 5 sin tirada ni cobro de casillero. Este último detalle es una hipótesis operativa explícita de la ambigüedad procedimental en el regreso.

Cuando D6 permite entrar a UTN o continuar el circuito, el jugador elige la acción que minimiza **el número esperado de rondas** bajo la configuración. La elección óptima se decide después de ver D6, antes de la Situación. Esto es una cota estratégica favorable: el juego real puede durar más si los jugadores eligen distinto. La resolución es una iteración determinista de Bellman sobre un proceso de decisión de Markov absorbente, **no un muestreo ni una simulación**. Se reportan estados, iteraciones y residual de convergencia. El modelo presupone elecciones de Situación A/B independientes con probabilidades configuradas; el orden del mazo finito no está representado.

### Datos deliberadamente desconocidos

Posición inicial, P inicial, K inicial, requisito P UTN, requisito K UTN y recompensas P/K en casilleros permanecen **sin definir**. Para considerar las Situaciones se deben configurar las consecuencias P/K de A y B y su probabilidad. La opción `Omitir P/K de Situaciones (EXPERIMENTO)` permite aislar la economía de los casilleros y es un supuesto analítico transparente, no una decisión de diseño ni un valor económico real.

La compresión del estado al requisito es matemáticamente correcta mientras P/K no puedan perderse una vez obtenidos. **Si algún casillero o Situación tiene efectos P/K negativos, el solver bloquea la estimación**, porque al truncar los excedentes antes de pérdidas se obtendrían resultados falsos. También marca N/D si no se definieron importes relevantes, detecta déficits sin producción positiva y limita explícitamente el espacio de estados. El modelo no incorpora duelos, transferencias ni pérdidas agregadas no representadas en casilleros/Situaciones; las estimaciones son condicionales a su ausencia.

### Calibrador inverso

Con la meta de 5 rondas esperadas, el calibrador **ensaya** valores enteros de 0 al máximo exploratorio elegido (12 por defecto, no un premio asignado) para:
- premio P del casillero 2;
- premio P del casillero 4, igual al 2 en cada propuesta;
- premio K del casillero 5.

Mantiene sin modificar todos los demás parámetros. Utiliza búsqueda determinista monotónica por niveles P/K y ofrece hasta ocho combinaciones ordenadas por cercanía al objetivo, mostrando duración teórica y diferencia absoluta. La solución exacta no está garantizada porque los premios son enteros y la meta puede no ser alcanzable dadas la posición inicial, los requisitos y el movimiento. **Solo se modifica el escenario cuando se presiona «Aplicar al escenario»**; para conservarlo se debe guardar/exportar.

### Límites y siguiente fase

La cifra v3.1 es tiempo esperado individual de UTN bajo una política ideal, no tiempo garantizado, tiempo global de partida ni percentil. No hay tiempos de Título, Pasaporte y Casa probabilísticos todavía. Para incorporar pérdidas P/K deberán implementarse estados de excedentes con cotas de error; para representar mazos reales, estados de composición de cartas y dependencias entre rondas. El objetivo sigue siendo un balance de recursos y no un rediseño de reglas.
