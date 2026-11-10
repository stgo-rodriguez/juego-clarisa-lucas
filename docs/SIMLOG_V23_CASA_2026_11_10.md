# Clarisa & Lucas — adaptación del simulador y SIMLOG a v2.3

**Fuente autoritativa:** [Especificación Integral v2.3, consolidada el 10 de noviembre de 2026](https://drive.google.com/file/d/16IOCwC72fT__n5b19PQm-LRa7CenB5S_/view).  
**Implementación:** `feature/simlog-v23-casa-propietarios`, basada en la última variante v2.2 auditada con conversión 2:1, políticas individuales y tamaño de mano experimental 3/4.  
**No sustituye las trazas históricas v2.1/v2.2.**

## Único cambio de regla desde v2.2: adquisición de Casa

| Estado de propiedad | Dónde debe terminar la pareja retadora | Acción |
|---|---|---|
| Casa sin dueño | Centro del tablero (fila 3, columna 3) | Compra contra banca |
| Casa con dueño | Posición **actual de ambos propietarios** en la cuadrícula 5×5 | Disputa contra propietarios |
| Casa con dueño, retador termina en centro pero el propietario está en otro lugar | No habilitado | No se puede disputar |
| Retador pasa por propietarios pero termina en otra celda | No habilitado | No se puede disputar |

La casilla CASA permanece fija en (3,3); la propiedad se desplaza con la pareja propietaria. Se preservan los requisitos económicos de Casa, dados 2D6 vs 2D6 con empate desfavorable para compradores, pujas 15,20,25… M por integrante dentro de un turno, pago solo de la puja ganadora y transferencia del pago a propietarios si corresponde.

## Implementación

- `simulador/reglas_v23.py`: `EconomyV23.house_encounter` comprueba dueño, posición, pareja y destino exacto; `buy_house` aplica regla 2.3 sin modificar v2.2. `RoundEngineV23` conserva movimiento, Situación y rebotes de v2.2 auditada.
- `simulador/agentes_v23.py`: el planificador persigue el lugar actual de la pareja propietaria, no el centro cuando tiene dueños. El bot realiza la acción de Casa después de mover si finaliza en la celda habilitada.
- `simulador/simlog_v23.py`: `SIMLOG-2.3` con documento fuente y eventos de `house_encounter`, `house_attempt` y `house_bought` que guardan `location`, `mode`, `buyers`, `owners`, `prior` y oferta según el tipo.
- `laboratorio/simular_v23.py`: selección explícita de v2.3; resultados separados y métricas `house_encounters`, `house_dispute_attempts` y `house_owner_transfers`.
- `laboratorio/simular_versionado.py`: habilita `--version 2.3`, preservando ejecución v2.1/v2.2.

**No se aprobó un nuevo mazo ni se alteraron costos, afinidad, banco o requisito de Casamiento.**

## Pruebas de aceptación

1. Compra inicial posible únicamente en (3,3).
2. Compra/disputa contra propietarios posible fuera de (3,3) únicamente en posición del propietario actual.
3. No hay disputa al pasar por la celda de propietarios.
4. Caer en (3,3) mientras los propietarios están en otra celda no genera disputa.
5. Reintentos y precio 15→20 M por integrante funcionan fuera del centro.
6. Empate no produce transferencia.
7. La venta libera reservas de Casa de los antiguos dueños, transfiere Dinero al vendedor y constituye reservas de nuevos propietarios, sin crear recursos.
8. El planificador da prioridad a alcanzar a los propietarios (su posición actual).
9. El motor v2.2 conserva su regla anterior.
10. SIMLOG v2.3 registra coordenadas, tipo de adquisición y propietario previo; se mantiene validación de A/B y fuentes de recursos.

[Pruebas CI aprobadas 3.11 y 3.13](https://github.com/stgo-rodriguez/juego-clarisa-lucas/actions/runs/42866182701): 10 tests específicos v2.3, 10 del banco/estrategias v2.2, 7 de tablero v2.2 y 14 de reglas v2.1. Además se ejecutaron 10 partidas planificadoras y 4 mixtas de humo; 14/14 terminaron en Casamiento dentro del límite de 100 rondas. Se registraron 80 encuentros de Casa, 78 intentos de disputa y 41 transferencias de propiedad en esas 14 partidas. Estas frecuencias son resultados de bots heurísticos y no prueban por sí solas balance humano.

## Ejecución

```bash
python -m unittest discover -s tests -p 'test_casa_v23.py' -v
python -m laboratorio.simular_versionado \
  --version 2.3 --jugadores ambos --politica mixto --mano 3 \
  --semillas 40 --inicio 4201 --rondas 100 \
  --out resultados/simlog_v23_4201
```

Para consumir las trazas v2.3, el visualizador debe admitir el par `SIMLOG-2.3` y `especificacion-integral-2026-11-10`. Versiones anteriores del lector no reconocerán el esquema nuevo automáticamente.

## Pendientes anteriores no modificados

- **P4:** regreso a Juventud después de ruptura adulta, ubicación y mano al regresar. El simulador registra `rule_pending` y no inventa transición.
- Composición física y reciclado del mazo adulto (cartas sintéticas `SYN-A`); mano de 3/4 sigue experimental.
- Políticas individuales de los bots son heurísticas y no simulaciones validadas de humanos.
- Las proporciones de producción de recursos continúan como objetivos experimentales, no premios forzados en el reglamento.
