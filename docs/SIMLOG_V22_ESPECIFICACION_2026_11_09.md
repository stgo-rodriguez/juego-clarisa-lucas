# Clarisa & Lucas — Simulador y SIMLOG v2.2

**Fuente autoritativa:** [Especificación Integral v2.2, consolidada 09/11/2026](https://docs.google.com/document/d/1XvdzvRGT5ZGtgljpn5vVJYS4A0KDpqkw/edit), documento `Clarisa_y_Lucas_Especificacion_Integral_v2_2_Consolidada_2026-11-09.docx`.

**Alcance:** implementación funcional de las modificaciones explícitas v2.1 → v2.2, utilizando como base el motor v2.1 auditado. No se declara que se hayan resuelto los asuntos pendientes que ya existían en v2.1, ni los objetivos económicos experimentales.

## Cambios confirmados respecto de v2.1

| Área | v2.1 | v2.2 |
|---|---|---|
| Juventud, Universidad (1/4) | +1 K al pasar; +2 K al caer | **0 recursos**; sigue habilitando adjudicación de Título |
| Juventud, Trámite (2/5) | +1 P al pasar; +2 P al caer | **0 recursos**; sigue habilitando adjudicación de Pasaporte y conexión a Dublín |
| Juventud, casilleros 3/6 | Vacíos | Sin cambios |
| Juventud, vuelta 6 → 1 | Cobrar Perfil | Sin cambios: **sí se cobra el Perfil** |
| Adultez: casilleros A/P/K/M | Premios experimentales en destinos | **Todos pasan a Vacío** |
| Adultez: CASA en (3,3) | Disputa/compra | Se conserva |
| Adultez: COBRAR PERFIL en (5,3) | Cobro de Perfil, incluida colocación inicial | Se conserva |
| Adultez: tres accesos superiores | Salida a Casamiento | Se conserva |
| Infancia, UTN, Cartas A/B, Pareja, hitos y Afinidad | Reglas v2.1 | Sin modificación expresa |

**Tablero v2.2:** cuadrícula 5×5 con solo CASA (3,3) y COBRAR PERFIL (5,3) como casilleros no vacíos; los accesos a Casamiento continúan en (1,2), (1,3), (1,4) mediante conexión exterior y consumiendo un paso.

## Archivos

- `simulador/movimiento_v22.py`: nueva grilla de activación, misma geometría de rebote y conexión de Casamiento de la v2.1.
- `simulador/reglas_v22.py`: economía sin emisión por casilleros de Juventud ni por casilleros A/P/K/M de Adultez; motor con destino adulto interpretado según grilla v2.2.
- `simulador/agentes_v22.py`: planificador ya no premia recorrer ni aterrizar en posiciones productoras eliminadas; conserva puntuación por adjudicación, Perfil, Casa y Casamiento.
- `simulador/simlog_v22.py`: SIMLOG-2.2, referencia al documento, validaciones de fuentes prohibidas, herencia de trazabilidad de SIMLOG 2.1.
- `laboratorio/simular_v22.py`: corrida separada, etiquetas, manifiestos, trazas y resultados propios.
- `laboratorio/simular_versionado.py`: `--version 2.1` y `--version 2.2` seleccionan motores genuinamente distintos.
- `tests/test_reglas_simlog_v22.py`: pruebas de tablero, rutas, supresión de emisión, aislamiento v2.1 y partida con trazas.

## Ejecución

```bash
python -m unittest discover -s tests -p 'test_reglas_simlog_v22.py' -v
python -m unittest discover -s tests -p 'test_reglas_simlog_v21.py' -v
python -m laboratorio.simular_versionado --version 2.2 --semillas 100 --inicio 101 --rondas 100 --out resultados/simlog_v22_101_200
python -m laboratorio.analizar_simlog_v21_revision --out resultados/simlog_v22_101_200
```

Los identificadores de partidas, el esquema SIMLOG, los manifiestos y el nombre del directorio incluyen la versión; no mezclar trazas v2.1 y v2.2.

## Límites explícitos

- Los objetivos económicos por etapa son **metas**; no se alteraron los mazos de Situación ni sus efectos para alcanzarlas automáticamente.
- La mano adulta de 3 cartas y otros valores pendientes siguen siendo parámetros experimentales.
- Los casos extraordinarios previamente marcados pendientes (p. ej. retorno desde ruptura adulta) permanecen pendientes.
- Las estrategias automáticas son políticas heurísticas reproducibles, no decisiones humanas observadas. El resultado de la simulación no demuestra balance lúdico.
- La eliminación de ingresos de casilleros puede alterar ritmos, costos relativos y competitividad; esas diferencias requieren nuevas simulaciones y comparación con las mismas semillas v2.1.
