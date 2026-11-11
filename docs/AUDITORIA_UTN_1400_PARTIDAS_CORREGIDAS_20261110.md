# Clarisa & Lucas — Corrección UTN: 1.400 partidas auditadas

**Fecha:** 10/11/2026. **Estado:** simulaciones completas, trazas auditadas y CI aprobado.  
**Fuente:** especificación integral v2.3 (sección 06) y equivalentes de v2.2.  
**Ejecución:** [GitHub Actions #42933927583](https://github.com/stgo-rodriguez/juego-clarisa-lucas/actions/runs/42933927583) (éxito).

## Error original y alcance de la corrección

En la última auditoría se reportó que **67,3 %** de personajes llegaban por primera vez a UTN sin 2 P + 1 K; el ejecutor utilizaba `choose_utn=True` sin consultar saldos. Esto es una **decisión deficiente de los bots**, no una entrada física prohibida: el reglamento 06.1 permite tomar la conexión, resuelve Situación A/B y solo después verifica recursos, sin examen en el turno de llegada; si faltan, retorna al circuito en el próximo turno.

La nueva política, previa al movimiento, exige a los **bots** 2 P + 1 K libres para elegir la bifurcación. Los recursos no se pagan ni reservan. El motor sigue admitiendo la elección manual sin recursos y las reglas de comprobación posteriores. Toda decisión queda registrada como `utn_entry_intent`, y cada `enter_utn` exige intención previa válida en los SIMLOG experimentales.

## Método reproducible

- Versiones: `SIMLOG-2.2` y `SIMLOG-2.3`, cada una 350 partidas con 6 y 350 con 10 jugadores.
- Semillas idénticas 2001–2350 por cohorte; 100 rondas máximo; política `planificador`, mano Adultez de 3 y conversión bancaria desactivada.
- Corrección previa de duelos ordinarios de mismo rol mantenida.
- Comparación directa adecuada: corrida **anterior corregida de duelos**, no la primera corrida afectada simultáneamente por ambos defectos.
- Los nombres de partidas incluyen `utn_gate` para no confundirse con trazas anteriores.
- El workflow comprueba cobertura íntegra de semillas, roles de duelos, SHA-256 de archivos de manifiesto y entradas a UTN con saldos previos suficientes.

## Resultados

| Métrica | v2.2 · 6 | v2.3 · 6 | v2.2 · 10 | v2.3 · 10 |
|---|---:|---:|---:|---:|
| Partidas | 350 | 350 | 350 | 350 |
| Casamientos | 350 | 350 | 350 | 350 |
| Bloqueadas por regla pendiente | 0 | 0 | 0 | 0 |
| Mediana rondas | 20 | 20 | 20 | 19,5 |
| P80 rondas | 23 | 23 | 22 | 22 |
| Media rondas | 20,780 | 20,703 | 19,991 | 19,777 |
| Turnos | 42.772 | 42.674 | 68.183 | 67.547 |
| Decisiones UTN evaluadas | 15.094 | 15.094 | 24.593 | 24.591 |
| Intenciones UTN rechazadas por falta de recursos | 9.193 | 9.193 | 14.988 | 14.980 |
| **Oportunidades reales de bifurcación rechazadas** | **3.251** | **3.250** | **5.298** | **5.296** |
| Entradas efectivas a UTN | 2.760 | 2.760 | 4.466 | 4.467 |
| **Entradas del bot sin requisitos previos** | **0** | **0** | **0** | **0** |
| Insuficiencia comprobada tras Situación en UTN | 721 | 721 | 1.077 | 1.074 |
| Duelos ordinarios de distinto rol (inválidos) | 0 | 0 | 0 | 0 |
| Duelos ordinarios válidos | 1.765 | 1.829 | 5.154 | 5.106 |
| Disputas de hitos cruzadas legales | 4 | 4 | 10 | 10 |
| Transferencias de Casa | — | 373 | — | 788 |

**Totales:** 1.400 partidas, 1.400 Casamientos, 1.400 trazas completas verificadas, **14.453 entradas UTN, 0 entradas sin recursos previos**, y 17.095 oportunidades de tomar la bifurcación descartadas por la nueva política. Los 3.593 eventos de insuficiencia detectados después de Situación incluyen llegadas y reintentos: **no deben interpretarse como primeras entradas ilegales**. Tras la Situación se aplica la sección 06.3 y la vuelta al circuito.

### Comparación contra corrida inmediatamente anterior (corregida de duelos)

| Cohorte | Mediana antes | Mediana con política UTN | P80 antes | P80 UTN |
|---|---:|---:|---:|---:|
| v2.2 · 6 | 21 | 20 | 24 | 23 |
| v2.3 · 6 | 20 | 20 | 24 | 23 |
| v2.2 · 10 | 20 | 20 | 22 | 22 |
| v2.3 · 10 | 20 | 19,5 | 22 | 22 |

La corrección elimina la **decisión de entrar con recursos insuficientes antes de mover**. No supone una mejora grande y uniforme en la duración: v2.2 de diez jugadores tiene una media ligeramente superior a la anterior, aunque la mediana coincide. La ganancia principal es fidelidad estratégica y trazabilidad.

## Archivos

[Resultados en GitHub Actions](https://github.com/stgo-rodriguez/juego-clarisa-lucas/actions/runs/42933927583), ocho artefactos (cuatro CSV/JSON resumidos y cuatro conjuntos de trazas). GitHub Actions empaqueta automáticamente los artefactos, **pero no se han cargado ZIP a Google Drive**. Conservación de artefactos: 30 días. Este documento y su [CSV](AUDITORIA_UTN_1400_PARTIDAS_CORREGIDAS_20261110.csv) permanecen en el repositorio.

- [PR #10 — v2.3 y motor experimental integrado](https://github.com/stgo-rodriguez/juego-clarisa-lucas/pull/10)
- [PR #11 — rama independiente de v2.2](https://github.com/stgo-rodriguez/juego-clarisa-lucas/pull/11)
- [CI UTN v2.2/v2.3 Python 3.11/3.13](https://github.com/stgo-rodriguez/juego-clarisa-lucas/actions/runs/42933630186)
- [CI UTN v2.2 independiente](https://github.com/stgo-rodriguez/juego-clarisa-lucas/actions/runs/42934424366)

## Pendientes no modificados

P4 — retorno a Juventud por ruptura adulta; composición del mazo físico adulto SYN-A; equivalencia de políticas de bot a decisiones humanas. La comprobación estratégica de recursos ANTES de entrar no sustituye la comprobación reglamentaria DESPUÉS de la Situación, ni evita pérdidas de recursos por cartas durante el turno.
