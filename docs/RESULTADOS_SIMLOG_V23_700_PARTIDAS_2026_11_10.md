# Clarisa & Lucas v2.3 — Simulación de 700 partidas (10/11/2026)

**Estado:** ejecución completa y auditoría de trazas aprobada.  
**Semillas:** 2001 a 2350, idénticas a la simulación de 700 partidas v2.2 anterior.  
**Corrida:** [GitHub Actions #42867872439](https://github.com/stgo-rodriguez/juego-clarisa-lucas/actions/runs/42867872439).

## Parámetros

- Reglas: `SIMLOG-2.3` / `especificacion-integral-2026-11-10`.
- 350 partidas con 6 jugadores (3 Clarisa + 3 Lucas), 350 partidas con 10 (5 + 5).
- Cada cohorte usa las semillas enteras 2001 a 2350.
- Política del agente: `planificador`.
- Mano de Movimiento Adultez: 3 cartas.
- Conversión bancaria: **deshabilitada**, para conservar los parámetros de la anterior corrida v2.2 de 700 partidas.
- Máximo de 100 rondas por partida; finalización reglamentaria por Casamiento.
- No se ha inventado la resolución de P4 (ruptura adulta): cualquier caso se habría etiquetado `rule_pending`. En esta corrida hubo **0**.
- Mazo adulto experimental con cartas SYN-A; no se atribuye validez humana a la estrategia de bots.

## Resultados auditados

| Indicador | 6 jugadores | 10 jugadores | Total |
|---|---:|---:|---:|
| Partidas ejecutadas | 350 | 350 | **700** |
| Casamientos | 350 | 350 | **700** |
| Regla pendiente bloqueante | 0 | 0 | 0 |
| Alcanzaron 100 rondas | 0 | 0 | 0 |
| Trazas completas verificadas | 350 | 350 | **700** |
| Mediana de rondas | 20 | 20 | — |
| P80 de rondas | 23 | 22 | — |
| Media de rondas | 20,91 | 19,79 | — |
| Rondas mínimas / máximas | 14 / 33 | 14 / 28 | — |
| Turnos totales | 42.977 | 67.656 | **110.633** |
| Encuentros con propietarios de Casa | 983 | 2.126 | **3.109** |
| Intentos de disputa de Casa | 948 | 2.060 | **3.008** |
| Cambios de dueño de Casa | 415 | 875 | **1.290** |
| Conversiones bancarias | 0 | 0 | 0 |

### Comparación descriptiva con la anterior simulación v2.2

| Indicador | v2.2 de 6 | v2.3 de 6 | v2.2 de 10 | v2.3 de 10 |
|---|---:|---:|---:|---:|
| Mediana rondas | 21 | 20 | 20 | 20 |
| P80 rondas | 24 | 23 | 22 | 22 |
| Casamientos | 350 | 350 | 350 | 350 |

**Límite de inferencia:** las semillas y las condiciones de mesa se han conservado, pero la rama v2.3 procede de la versión auditada con agentes individuales, no del ejecutor v2.2 original sin las correcciones posteriores. Las diferencias de duración no deben adjudicarse causalmente solo a la regla de Casa sin ejecutar un control del motor auditado v2.2 con idéntica política de agentes y la misma semilla.

## Validación por partida

El flujo de CI comprobó:
1. 350 filas por cohorte y cobertura sin duplicaciones de semillas 2001–2350.
2. `size`, `hand_size=3`, `policy=planificador`, `bank_enabled=False` en cada partida.
3. Partidas finalizadas, sin bloqueo y límites 1–100 rondas.
4. Un manifiesto `SIMLOG-2.3` por partida, asociándolo inequívocamente a la especificación del 10 de noviembre de 2026.
5. Verificación SHA-256 de todos los archivos declarados en cada manifiesto.
6. En eventos de Casa: coordenadas y tipo (`banca` o `propietarios`), y todas las compras a banca en (3,3).

## Archivos publicados

[Descargar en el apartado Artifacts de la ejecución](https://github.com/stgo-rodriguez/juego-clarisa-lucas/actions/runs/42867872439) (retención 30 días):

- `SIMLOG_v23_350_resultados_6jug_semillas_2001_2350`: CSV y JSON consolidados.
- `SIMLOG_v23_350_resultados_10jug_semillas_2001_2350`: CSV y JSON consolidados.
- `SIMLOG_v23_350_trazas_6jug_semillas_2001_2350`: detalle por partida, turno, carta, recurso, hito y evento.
- `SIMLOG_v23_350_trazas_10jug_semillas_2001_2350`: equivalente con 10 jugadores.

No se subieron ZIP a Google Drive. Los resultados resumidos permanecen en este documento del repositorio, pero las trazas individuales están sujetas a retención del artefacto.

El visualizador Streamlit puede abrir esta versión con la compatibilidad implementada en el [PR #7](https://github.com/stgo-rodriguez/juego-clarisa-lucas/pull/7), que reconoce el esquema `SIMLOG-2.3`. El código sigue sin integrarse en la rama principal.
