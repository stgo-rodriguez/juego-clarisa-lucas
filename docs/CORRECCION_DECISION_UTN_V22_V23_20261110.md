# Corrección de decisión de ingreso a UTN — SIMLOG v2.2 / v2.3

**Fecha:** 10 de noviembre de 2026  
**Fuente:** Especificación Integral v2.3, secciones 05 y 06, consolidada en [Drive](https://drive.google.com/file/d/16IOCwC72fT__n5b19PQm-LRa7CenB5S_/view).  
**Contexto de auditoría:** se observó que el 67,3 % de los personajes ingresó a UTN por primera vez sin reunir los recursos de la sección 06, porque el simulador proporcionaba `choose_utn=True` indiscriminadamente.

## Diferenciar regla del juego y política del agente

**Reglamento vigente, sección 06.1–06.3:**
- Se puede tomar la bifurcación del circuito de Infancia desde la posición 5 con un paso disponible; el nodo exterior consume un paso y descarta los excedentes.
- En la llegada se resuelve la Situación A/B y **después** se verifican 2 P + 1 K libres; no se pagan ni reservan. No se toma examen ese turno.
- Si cumple, la próxima ronda se resuelve nueva Situación, se verifica de nuevo el requisito y se tira el examen (4–6 aprueba).
- Si faltan recursos al llegar o reintentar, acaba el turno en UTN sin examen, luego vuelve al circuito.
- Por ello **entrar a UTN sin recursos es reglamentariamente posible**, pero es una mala decisión para un bot que quiere evitar vueltas improductivas.

**Política automática corregida:** el bot elige `choose_utn=True` solo cuando ya cuenta con al menos 2 P y 1 K libres **antes de mover**. Para los demás casos sigue por el circuito y cobra únicamente el casillero de destino. La heurística no presume el resultado futuro de la Situación y no modifica las reglas del motor; por tanto, una pérdida posterior provocada por la carta puede obligar igualmente al regreso reglamentario.

## Implementación

- `simulador/decision_utn_v2.py`: función pura `choose_utn_entry(player,economy)` y emisión de intención `utn_entry_intent`.
- `laboratorio/simular_v22.py` y `laboratorio/simular_v23.py`: sustituyen el `choose_utn=True` constante por la política; se registran cantidad de intenciones permitidas/denegadas, entradas y fallos tras Situación.
- `simulador/experimento_politicas_v22.py`: valida que cada evento `enter_utn` de los bots vaya precedido por `utn_entry_intent` válido con recursos suficientes. SIMLOG v2.3 hereda el validador.
- Manifiesto: `utn_entry_policy: bot_requires_free_2P_1K_before_moving`, y `utn_physical_rule: entry_allowed_without_resources;check_after_situation`.
- Identificador de partida contiene `utn_gate`, preservando los anteriores sin sobreescribir sus trazas.

## Pruebas

[CI UTN y ambas versiones Python 3.11/3.13](https://github.com/stgo-rodriguez/juego-clarisa-lucas/actions/runs/42933630186), aprobada:
1. Bot con P insuficiente o K insuficiente no elige entrar.
2. Bot con ambos recursos entra y no los consume ni reserva.
3. Motor permite entrada manual sin requisitos, cumpliendo la sección 06.
4. Una Situación que quita recursos después de entrar habilita el retorno reglamentario, sin examen.
5. Simulación integrada v2.2 y v2.3 registra decisiones con recursos previos y verifica cada entrada.
6. Regresión de duelos, Casa, UTN y economía en ambas versiones Python.

## Repetición

[Matriz de 1.400 partidas en GitHub Actions](https://github.com/stgo-rodriguez/juego-clarisa-lucas/actions/runs/42933927583):
- Versiones: v2.2 y v2.3, cada una 350 partidas con 6 y 350 con 10 jugadores.
- Semillas: 2001–2350 por cohorte.
- Política de otros movimientos: planificador; mano de movimiento adulta 3; conversión bancaria desactivada; 100 rondas máximas.
- Los duelos entre roles distintos siguen prohibidos para duelos ordinarios.
- Se examinan: casamientos, rondas P50/P80, duelos, entrada a UTN con intención válida, oportunidades rechazadas por falta de recursos, retornos reglamentarios posteriores a Situación y economía/propiedad de Casa.

**Alcance:** la comparación evalúa la eficiencia de la nueva política del bot, no modifica el reglamento oficial de UTN. Las simulaciones históricas con política incondicional siguen etiquetadas como provisionales.
