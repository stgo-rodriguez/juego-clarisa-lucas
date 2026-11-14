# Ecualizador Teórico v3.0 · Clarisa & Lucas

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
- `tests/`: pruebas de reglas económicas (Python y JavaScript).

Ejecutar la evaluación por línea de comandos:

```bash
python laboratorio/v3/modelo_matematico.py laboratorio/v3/matriz_economica_v3.json
python -m unittest discover -s laboratorio/v3/tests -p 'test_*.py'
node laboratorio/v3/tests/test_engine.cjs
```

## Alcance matemático del primer prototipo

Se usa la esperanza de producción por ronda y una **cota económica optimista** para reunir requisitos, con acumulación paralela de recursos y secuencia Infancia → Juventud → Adultez. En los proyectos juveniles se computan inversiones acumuladas de tres subhitos y pagos de adjudicación; se conservan por separado las comprobaciones UTN/Vuelo y las reservas Pareja/Casa. Las metas de afinidad compartidas nunca se duplican, y las metas diferentes se exigen conjuntamente. La victoria monetaria de Falso Lucas es individual.

El cálculo base no inventa valores ni interpreta `null` como cero. Una tasa conocida nula o negativa con déficit vuelve económicamente inalcanzable un objetivo; los valores faltantes muestran N/D. La frecuencia 1/6 de casilleros de Infancia proviene de la distribución del D6 en el circuito de seis destinos mientras se permanece en él. Las tasas de visita de Juventud y Adultez quedan por definir; no se impone uniformidad. Las Situaciones se diferencian por etapa/rol y se modelan con probabilidad A/B.

**No es aún una predicción completa de rondas de partida.** La ruta hacia UTN, la tirada de examen, distancias de movimiento, las visitas reales, la adjudicación por dados, la competencia entre parejas, la compatibilidad A–Neutro–B, el consentimiento y las interacciones no están integrados en un modelo probabilístico de primera llegada. Sin esos datos no hay tiempo central, conservador ni p80 justificables.

**Aproximaciones pendientes de refinar:** el modelo agrega recursos en flujos netos esperados, sin resolver la truncación por saldo libre de las pérdidas ordinarias; no modela deshacer reservas ni transferencias reales; usa un reparto parametrizado del precio de Casa; no acredita todavía el cobro único inicial de Perfil al entrar en Adultez; no modela frecuencia de intentos de adjudicación ni las demoras por posición. Al elegir la variante de pago terminal de afinidad, se ensaya esa hipótesis sin darla por aprobada como regla final.

## Cómo usar

1. En **Generación**, fijar premios por mecanismo y frecuencia de visitas o activaciones; los campos vacíos quedan sin identificar.
2. En **Costos y metas**, introducir cuantías de inversión, reserva, tenencia y pago.
3. En **Supuestos**, elegir objetivos de afinidad y el reparto del precio de Casa; las configuraciones de 6/10 jugadores son escenarios de mesa, pero no se introduce aún competencia dependiente del número.
4. Revisar el efecto en las tasas de A/P/K/M, hitos, objetivos de victoria y cuellos.
5. Guardar, duplicar, comparar y exportar el escenario como JSON o la matriz de flujos en CSV.

## Procedencia de reglas

[Especificación conceptual v3.0](https://docs.google.com/document/d/1AfX65pZX_XmXwsPLMwkXAqg5gL1BfzKB/edit). Ningún valor monetario o de recompensa de v2.x fue promovido a norma v3.0.
