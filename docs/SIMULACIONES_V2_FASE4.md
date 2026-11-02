# Simulaciones v2.x — Fase 4: transiciones y sincronización entre etapas

**Reglamento rector**: *Especificación Integral v2.0 Consolidada*, 1/11/2026.  
**Rama**: `feature/simulaciones-v2-movimiento`.  
**Alcance**: integración UTN → Juventud → Dublín → Adultez y evaluación controlada de dos convenciones **experimentales** para el ingreso adulto.

## Implementación

- `simulador/turnos_v2.py` incorpora bifurcación voluntaria a UTN al pisar casillero 5 de Infancia, **después** de cobrar +2 P y verificar 2 P + 1 K **libres**. El ingreso detiene el movimiento y descarta pasos sobrantes. Rinde D6 (4–6 aprueba, 1–3 permanece en UTN). La reprobación permite reintentar en el turno siguiente, sin robo de Situación ni desplazamiento. La aprobación asigna Perfil y el siguiente turno comienza en Juventud, con carta propia A/B y Situación compartida por rol.
- `simulador/transiciones_v2.py` contiene el adaptador de transición conectado a `EconomyV2` y un mazo de 16 Perfiles por rol (4 perfiles productivos × 4 afinidades). Cada carta se baraja y queda retenida de forma individual, sin doble adjudicación. El mercado de cambios y duelos de Perfil **no** se simula todavía.
- `simulador/economia_v2.py` comprueba la disponibilidad **individual** de 5 K y 5 M antes de Dublín. Son requisitos, no pagos: no se deducen ni se transfieren automáticamente de un miembro al otro. La pareja toma la bifurcación desde Trámite **con caída exacta** y mantiene sus reservas de 5 A.
- El ingreso desde el nodo exterior de Dublín coloca a ambos en `(5,3)` sin gastar movimiento, activa la producción de Perfil **una vez por integrante** y permite iniciar cartas adultas desde ese mismo casillero.

## Comparación: cuándo llega la pareja a Adultez

**Todavía no existe una regla definitiva para la sincronización dentro de la ronda global.** Se ofrecen dos políticas parametrizadas:

1. `next_round` (valor por defecto **del prototipo**, no norma del juego): la pareja se coloca en Adultez al comienzo de la siguiente ronda. Si uno de los integrantes tiene un turno pendiente de la ronda del vuelo, se registra como `dublin_wait_experimental` y no roba Situación ni gasta cartas.
2. `next_turn` (comparativa): la pareja se coloca al comienzo del siguiente turno **propio de cualquiera de los dos**. Si ocurre dentro de la misma ronda, puede aparecer una cohorte adulta que no estaba al inicio. Se revela entonces la Situación correspondiente al personaje solo una vez por ronda y se reutiliza para todos los adultos de ese rol, incluidos los que ya estaban en Adultez.

La segunda opción reduce los turnos inactivos, pero modifica la exposición a Situaciones adultas y la secuencia de cobro del Perfil. Se mantiene ambas para análisis de sensibilidad; **ninguna queda aprobada por su implementación**.

## Pruebas

Desde la raíz del repositorio:

```bash
python -m unittest discover -s tests -p 'test_*_v2.py' -v
python -m laboratorio.smoke_transiciones_v2 --dublin-policy both
python -m laboratorio.comparar_dublin_v2 --semillas 50 --out resultados/fase4
```

**Resultado local: 64/64 pruebas aprobadas.** Además se completaron 200 recorridos técnicos (50 semillas × 2 tamaños × 2 variantes), en ambas configuraciones de 6 y 10 participantes.

| Jugadores | Política | Recorridos | Turnos espera Dublín | Media movimientos reales hasta observación final | Media ronda inicial de Dublín |
|---|---|---:|---:|---:|---:|
| 6 | `next_round` | 50 | 36 | 18,24 | 2,16 |
| 6 | `next_turn` | 50 | 0 | 18,96 | 2,16 |
| 10 | `next_round` | 50 | 36 | 30,68 | 2,14 |
| 10 | `next_turn` | 50 | 0 | 31,40 | 2,14 |

**Limitaciones decisivas del experimento:** cada participante recibe artificialmente 1 K para poder presentarse a UTN con Situaciones neutrales. Tras entrar a Juventud se constituyó una pareja mediante encuentro inicial y se le adjudicaron **como fixtures** los hitos Título/Pasaporte y los recursos suficientes para viajar a Dublín. Los dados UTN son 6 por construcción y las cartas de Movimiento adulto son sintéticas. Es una prueba de consistencia y tiempos de transición, **no** una estimación de probabilidad de ingreso, partidas reales, balance ni victoria.

Los resultados completos están en `docs/datos_fase4/corridas_dublin_v2.csv` (200 filas) y `docs/datos_fase4/resumen_dublin_v2.json`.

## Validaciones específicas

- No se concede el Perfil si falta su baraja; no se lo concede dos veces.
- No se sale a UTN cuando falta K pese a cobrar P en casillero 5.
- La reprobación no extrae una Situación adicional.
- No se consumen K/M puntuales ni se aportan automáticamente desde la cuenta del acompañante.
- El ingreso a la cuadrícula no cuenta como un paso ni genera un cobro duplicado del Perfil.
- El acompañante conserva su mano adulta hasta su propio turno.
- Dos jugadores Lucas de Adultez en una misma ronda usan la misma Situación, aunque uno haya llegado desde Dublín a mitad de esa ronda (`next_turn`).
- Se mantiene la conservación de cartas, reservas, saldos económicos y un único turno por jugador.

## Pendientes antes de Monte Carlo integral

1. Reemplazar Situaciones neutrales por **seis mazos versionados** con su economía e interacciones; todavía no fueron cerrados.
2. Conectar inversiones, adjudicaciones, pareja, compra de Casa y Casamiento a decisiones autónomas en el ciclo de turno. El adaptador económico existe, pero algunas operaciones siguen requiriendo una llamada explícita.
3. Resolver retorno de Adultez a Juventud por pérdida de Título/Pasaporte, su coordenada, descarte de manos y reparto en mitad de ronda.
4. Resolver cambio de personaje, ruptura y reemplazo de pareja, socialización y disputas de Perfil.
5. Definir cantidades adultas por casillero, composición final del mazo A/B adulto y reciclados definitivos.
6. Cerrar la sincronización de Dublín con pruebas estratégicas y no solo geográficas.
7. Integrar agentes con políticas de decisiones, trazabilidad Gantt y reporte Monte Carlo, sin sobrescribir la referencia v1.3.

**Integración continua:** se amplía el workflow `.github/workflows/simulaciones-v2.yml` con los tests y escenarios de Fase 4. La verificación local no equivale a un resultado exitoso de GitHub Actions; comprobar ejecución en el repositorio.