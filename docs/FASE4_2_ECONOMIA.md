# Fase 4.2 — Economía por recurso, etapa, fuente y jugador

## Alcance y arquitectura

- **Motor intacto.** `simulador/motor_v13_base.py`, `simulador/motor.py` y `simulador/economia.py` no se modifican.
- `laboratorio/economia_trazable.py` contiene un observador `JuegoEconomico` que hereda del observador pasivo del Gantt. Reejecuta **una única partida seleccionada** con la semilla y los parámetros exactos del lote.
- Antes de entregar un desglose verifica `summary()` de la partida contra la fila original y concilia *por jugador y por recurso* el delta de existencias con las entradas, pérdidas, pagos, inversiones y transferencias registradas.
- `laboratorio/graficos_economia.py` contiene gráficos Plotly y un adaptador de `flujo_*` de los CSV originales.
- La interfaz añade la sección **5. Economía de recursos por origen, etapa y jugador**. Permite filtrar por etapa, recurso y jugador, inspeccionar movimientos, saldos y descargar el JSON auditado.

## Definiciones operacionales

| Término | Definición |
|---|---|
| Ingreso | Variación positiva de fichas atribuible a Perfiles, casilleros, cartas, conversiones 2:1 o venta de Casa. La venta de Casa redistribuye fichas ya pagadas por compradores: **no** es creación externa neta. |
| Pago | Salida del stock personal al resolver acciones, exámenes, Casa, Casamiento o canjes bancarios. |
| Inversión | Salida del stock personal para financiar un subhito de un proyecto: permanece comprometido en el proyecto hasta su adjudicación y no es necesariamente consumo definitivo en ese turno. |
| Pérdida | Descenso real por carta, después de truncar por disponibilidad y de aplicar las reglas de reservas y pareja. Se atribuye al jugador que pierde fichas. |
| Transferencia | Dos anotaciones de signos opuestos en el mismo recurso, con contraparte identificada. Incluye ayuda dentro de pareja, redistribución y duelo. |
| Stock | Fichas físicas presentes en el inventario personal (`p.r`), incluidas reservas. No incluye inversiones depositadas en proyectos. |
| Libre | `p.free(r)`. |
| Reservado | Para Amor: reserva de Pareja y Casa. Para Personalidad: reserva de Casa. |
| Stock medio por etapa | Media aritmética de snapshots individuales **al finalizar cada turno** en que el jugador se encuentra en esa etapa, incluidos turnos de otros jugadores. No es promedio por ronda, ni saldo final, ni promedio por partida. |

Las aportaciones por `settle_project` del ledger original son liquidaciones de recursos previamente invertidos, no nuevas salidas de `p.r`. Las ventas de comprobantes con precio se modelan como transferencia bilateral. Las conversiones bancarias contabilizan por separado las fichas entregadas y recibidas: no debe sumarse producción y saldo bruto como si fueran una misma magnitud.

## Limitación de datos agregados

Los CSV históricos contienen, por partida, `flujo_<fuente>_<recurso>`, sin etapa ni jugador. El resumen de todas las partidas solo agrupa esos flujos y normaliza por número de partidas; **no inventa desglose por etapa**. Para un desglose por jugador/etapa se reejecuta la partida seleccionada. La interfaz deja explícito el límite.

## Pruebas realizadas

- 92 pruebas locales correctas al integrar Fase 4.2 (incluidas 3 omitidas por depender de Streamlit instalado en CI).
- 180 partidas extra: 30 por combinación de 6/10 jugadores y tres configuraciones económicas (base, restrictiva y abundante), sin desajustes ni violaciones de integridad.
- 2.000 partidas originales (1.000 de 6 y 1.000 de 10) reproducidas byte a byte según SHA-256 de CSV.
- Comprobación de RNG (dados, cartas, bots y economía), resultados por partida, registros de eventos y partidas censuradas.

## Próximas tareas

- Fase 4.3: interacciones (duelos, disputas, compraventas, transferencias y rupturas) con definición de tasas y denominadores.
- Fase 4.4: calidad de turnos (oportunidades legales vs acciones ejecutadas; no inferir diversión objetiva).
- Ampliación posterior: event sourcing estructurado para **todos** los juegos de cada lote, sin costo excesivo de reejecución.
