# Fase 4.3 — Interacciones entre jugadores

## Objetivo y alcance

Instrumentar sin alterar el simulador v1.3 ni las decisiones de los bots. La sección **6. Interacciones: Duelos, negociación, Pareja y Casa** aparece tras ejecutar dos escenarios. Presenta: (a) indicadores agregados que realmente están en los CSV del lote, y (b) una reconstrucción detallada de **una partida elegida**, con la misma semilla, configuración y cotejo exacto de `summary()`.

Archivos nuevos: `laboratorio/interacciones.py` (observador, agregaciones y auditoría), `laboratorio/graficos_interacciones.py` (dos gráficos), `tests/test_interacciones_fase4.py` (12 pruebas) y `laboratorio/diagnosticar_interacciones.py` (diagnóstico por lotes determinista). Se agregó el panel a `laboratorio/app.py`.

## Taxonomía y medición

| Evento emitido por motor | Presentación | Notas |
|---|---|---|
| `duelo` | Duelo resuelto | Modalidad (`recursos`, `perfil`, `Titulo`, `Pasaporte`), tiradas de defensor y retador, resultado según dados. |
| `duelo_retirada` | Retirada de duelo | Se contabiliza como **duelo iniciado**, pero no como duelo decidido por dos dados. En este evento el dado defensor no está registrado. |
| `venta_comprobante` | Cesión de comprobante | Cesión consumada; `precio` puede ser 0. No contabiliza una oferta rechazada. |
| `intercambio_recursos` | Intercambio de recursos | Transferencia bilateral consumada; bot actual puede no proponerla. |
| `transferencia_hito` | Transferencia voluntaria de hito | Título o Pasaporte; no infiere transferencia de los comprobantes. |
| `formacion_pareja`, `ruptura` | Pareja formada / ruptura | La ruptura identifica su causa en el evento. |
| `transfer_pair` | Ayuda automática en pareja | **No** es una negociación; se contabiliza en categoría `Redistribución`. |
| `compra_casa` | Compra o traspaso de Casa | Es traspaso **solo** si el evento contiene `expropietarios` distintos de `null`. Una compra de Casa sin dueños previos no es un duelo. |
| `perdida_casa` | Pérdida de Casa | Registra causa; no supone que hubo un oponente. |

Un **duelo iniciado** = `duelo` + `duelo_retirada`. Los resultados excluyentes son: gana retador (`dado_retador > dado_defensor`), gana defensor (`<`), empate (`=`) y retirada. **Defensa sin pérdida** = gana defensor + empate; no considera retirada como éxito de defensa por dados. Ambos jugadores se contabilizan una vez como retador y defensor, respectivamente, incluso en retirada. Los eventos no emitidos (por ejemplo, propuestas fallidas o oportunidades legales) no se infieren.

Los resultados de un lote agregado (100, 500, 1.000 partidas) utilizan exclusivamente contadores almacenados en cada CSV; no identifican actores, rondas ni etapas que no estén registrados. El nivel fino vuelve a simular una semilla y conserva su evidencia para descarga JSON.

## Controles de calidad

1. `summary()` del replay es **idéntico** a la fila original por partida: si no, el sistema se niega a mostrar el resultado detallado.
2. Conteos de eventos comparados contra contadores del motor: `duels_started`, `duels_won`, `duels_lost`, `duels_tied`, `duel_retreats`, `receipts_traded`, `resource_trades`, `hitos_traded`, `rupturas`, `pair_formed`, `house_bought`, `house_transfers`, `transfer_pair`, `duel_<modalidad>` y `house_lost_<causa>`.
3. Ninguna función del observador toma decisiones o números aleatorios. Pruebas verifican mismo estado de RNG, fila y evento original con `log=True`.
4. Reconciliación de resultados y categorías, pruebas de errores inducidos y JSON exportable.
5. Escenarios normales, restrictivos, abundantes y partidas censuradas, para 6 y 10 jugadores.

## Evidencia de validación

- Suite local tras incorporar el módulo: **104 pruebas ejecutadas**, 100 correctas y 4 omitidas porque Streamlit no está instalado en el entorno de ejecución local; las 4 se ejecutan en GitHub Actions.
- Línea base: **2.000 partidas**, 1.000 de 6 y 1.000 de 10 jugadores, CSV reproducidos con el mismo SHA-256.
- Diagnóstico complementario: **150 partidas** (25 por tamaño de mesa y por economía base, restrictiva y abundante). **0 discrepancias** en indicadores y contadores. Resultado en `docs/DIAGNOSTICO_INTERACCIONES_FASE4_3.json`.

## Limitaciones

- La partida registrada representa **políticas de bots v1.3**, no negociaciones humanas ni diversión objetiva.
- Las compras de Casa y ayudas automáticas se separan de conflictos entre personas; no deben sumarse indiscriminadamente como «interacción estratégica».
- La reejecución registra interacciones consumadas: no hay un registro completo de elecciones posibles, oportunidades no utilizadas o propuestas rechazadas. Eso pertenece a Fase 4.4.
- El destino futuro de la Fase 4.3 sería comparaciones apareadas de frecuencia de Duelos entre escenarios, con medidas de incertidumbre (Fase 6), no conclusiones causales basadas en pocos juegos.

## Mac: actualización

Detener Streamlit con `Ctrl+C`, ejecutar `cd ~/Documents/juego-clarisa-lucas && git pull origin feature/laboratorio-balance`, activar `.venv` y arrancar `python -m streamlit run laboratorio/app.py`. Después de simular, usar la sección 6 y el botón **Reconstruir y auditar interacciones**.
