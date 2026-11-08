# SIMLOG v2.1 · Implementación de la especificación consolidada 08/11/2026

**Implementación:** `simulador/reglas_v21.py` y `simulador/simlog_v21.py`.  
**Ejecutor:** `laboratorio/simular_mazos_vigentes_v2.py`.  
**Estado:** implementación experimental con pruebas de regresión; no implica balance validado.  
**Compatibilidad:** `simulador/turnos_v2.py`, `simulador/economia_v2.py` y `simulador/simlog_v2.py` mantienen su comportamiento histórico por defecto; en `PlayerState` se añadió un campo con valor inicial `False`.

## Reglas implementadas

- **Situaciones:** seis mazos independientes y mezclados; al comenzar la ronda se fija **una situación compartida por etapa y rol con participantes**, como máximo seis. Todos los participantes asignados resuelven esa misma carta, pero cada uno escoge su propio A/B al actuar. La asignación se fija al comienzo de la ronda, incluso si un cambio posterior modifica la etapa. No hay robos de situaciones por casillero.
- **Infancia:** se tira D6 y mueve; el premio se cobra **solo al terminar exactamente** en el casillero (1:+3A, 2:+2P, 3:+3A, 4:+2P, 5:+1K, 6:+3A); después se resuelve la situación del rol.
- **Ingreso UTN:** desde casillero 5, la conexión al nodo exterior requiere un paso adicional, consume ese paso y descarta los sobrantes. No se cobra el casillero 5 al entrar al nodo. Tras Situación se verifican **2P + 1K libres** como requisito sin consumirlos; no hay examen en el turno de llegada. En turno posterior, tras la Situación, se reevalúan los requisitos y se rinde D6: 4–6 aprueba; 1–3 desaprueba. Si no cumple requisitos, al turno siguiente regresa al circuito; su primer paso se dirige al 5. Se siguen resolviendo las situaciones de Infancia en UTN.
- **Juventud:** la Situación y la Carta de Movimiento comparten letra A/B. Salir hacia Dublín por Trámite (2/5) consume un paso adicional y descarta pasos restantes, sin exigir terminar exactamente en Trámite.
- **Adultez:** la situación es compartida dentro del rol y ronda; su A/B es independiente del A/B de la Carta de Movimiento. Se conserva la mano y el tablero 5×5.
- **Pérdidas ordinarias de cartas:** se descuentan recursos libres, luego reservas A de Pareja y Casa o P de Casa; pueden reparar la reserva de Pareja con ayuda inmediata de la otra persona. Si falta posición definida para una ruptura en Adultez, se detiene antes de alterar saldos con un error explícito en lugar de inventar una regla.
- **Casa:** se habilitan intentos progresivos de precio contra propietarios existentes, igual que contra la banca. El agente actual decide inicialmente un solo intento, pero el motor admite varios cuando se solicitan.
- **Dublín:** se usa la incorporación al comienzo de la ronda siguiente; la colocación en Cobrar perfil activa producción gratis y el jugador ya puede usar su carta de Movimiento adulta en su propio turno de esa ronda.
- **Mesas:** reparto equilibrado en las corridas de referencia: 3 Clarisa + 3 Lucas y 5 + 5.
- **Mazos vigentes:** 12+12 Infancia v0.3; 24+24 Juventud v0.3; 15+15 Adultez v0.4; se reutiliza el catálogo numérico de 102 cartas, no se reescriben premios.

## SIMLOG: nuevos datos

El exportador conserva los archivos existentes de SIMLOG v2.1 y agrega:

- `situaciones_por_ronda.csv`: `Partida, Ronda, Etapa, Rol, Carta_compartida_ID, Participantes_asignados, Participantes_que_resolvieron, Elecciones_A, Elecciones_B, Evento_revelacion`.
- En `turnos.csv`: `Etapa_al_inicio_ronda`, `Rol_al_inicio_ronda`, `Situacion_grupo_etapa`, `Situacion_grupo_rol`, `Carta_compartida_ID`, `Recursos_antes_AB_JSON`, `Posicion_antes_AB`, `Recursos_casillero_JSON`, `UTN_retorno_pendiente`, `Tipo_movimiento_infancia`, además de pasos/descartes D6 corregidos.
- En `eventos.csv` / `eventos.jsonl`: `situation_assignment_locked`, `situation_context`, `situation_revealed`, `situation_resolved`, `childhood_route`, `enter_utn`, `utn_requirements_missing`, `youth_route`, etc.
- El `manifest.json` indica esquema `SIMLOG-2.1`, identificador de reglas, configuración, conteo, archivo adicional y su SHA-256.

**Validaciones:** conservación de cartas, misma carta para cada grupo etapa×rol×ronda, A/B registrado individualmente, una sola resolución por jugador, premio infantil exclusivamente del destino y antes de situación, UTN y bifurcaciones con pasos consumidos y descartados.

## Reproducción

```bash
python -m unittest discover -s tests -p 'test_reglas_simlog_v21.py' -v
python -m unittest discover -s tests -p 'test_turnos_v2.py' -v
python -m unittest discover -s tests -p 'test_cartas_vigentes_v21.py' -v
python -m laboratorio.simular_mazos_vigentes_v2 --semillas 100 --rondas 100 --out resultados/simlog_v21_20261108
```

El comando de 100 semillas genera **200 partidas** (100 mesas de seis y 100 de diez), sin alterar archivos históricos. El escenario usa parámetros todavía experimentales de agentes, cartas y economía; las proporciones por etapa siguen siendo **objetivos de análisis**, no garantías automáticas.

## Alcance y pendientes de implementación

Esta intervención corrige el reparto de Situaciones, el rediseño físico de Infancia, UTN y bifurcación juvenil, y amplía la auditoría SIMLOG. **No certifica conformidad integral de los demás subsistemas** con todas las secciones de la especificación del 08/11. Se incorporan pruebas focalizadas para pérdidas de reservas, mantenimiento y Casa; siguen pendientes la resolución de rupturas adultas sin coordenada de retorno, reemplazo de pareja, adjudicación completa, política de agentes, mercado/cambio de Perfil, casos límite de cambio de etapa o rol y balance de cartas. La configuración no habilita subastas de situaciones adultas. El mecanismo de puntuación A/B del agente sigue siendo una heurística, no una demostración de preferencias humanas. La versión v2.0 y las trazas históricas de las 200 partidas de 04/11 **no se alteran** ni se tratan como resultados de esta nueva variante.
