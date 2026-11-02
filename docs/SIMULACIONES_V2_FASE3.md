# Simulaciones v2.x — Fase 3: núcleo económico verificable

**Reglamento rector**: Especificación Integral v2.0 Consolidada, 1/11/2026.  
**Rama de trabajo**: `feature/simulaciones-v2-movimiento`.  
**Estado**: módulo económico y pruebas de integración **implementados**. No equivale todavía a partidas Monte Carlo v2.0 completas.

## Componentes nuevos

- `simulador/economia_v2.py`: cuentas de recursos libres, reservas de pareja/Casa, inversiones protegidas, proyectos y comprobantes, premios de casilleros, cobros de Perfil, compra de Casa, pago de Casamiento, UTN y Dublín como validaciones/acceso explícitos.
- `tests/test_economia_v2.py`: 17 pruebas económicas, incluyendo dos casos de integración reales con el `RoundEngine` de Fase 2 (cobro del Perfil adulto al caer con pareja y Casamiento por salida exterior).
- `laboratorio/smoke_economia_v2.py`: cuatro recorridos de control con 6/10 jugadores y economía parametrizada; NO son partidas completas.
- `.github/workflows/simulaciones-v2.yml`: ejecuta pruebas de las tres fases y humo económico.

## Contabilidad e invariantes

`emitido - quemado = libre + reservado_pareja + reservado_casa + invertido_en_proyectos`

Verificación por recurso (A/P/K/M) tras operaciones de emisión, consumo, transferencias, reserva y liquidación de proyectos. Una unidad reservada o invertida nunca puede utilizarse como libre. Intercambios entre jugadores no crean recursos.

## Reglas económicas implementadas

- Infancia: +3 A al visitar posición 2; +2 P al visitar 5. El motor de movimiento todavía **no corta automáticamente** hacia UTN al atravesar 5.
- Juventud: paso +1 K/P por Universidad/Trámite; caída exacta +2 **total**. Cobro de producción de Perfil al cruzar 6→1, por miembro de pareja.
- Adultez: cobro A/P/K/M únicamente si el destino corresponde al casillero y el escenario incluye cantidades; Cobrar perfil al finalizar exactamente en (5,3) e ingreso gratuito desde Dublín mediante llamada explícita.
- Pareja: encuentro exacto C+L y reservas individuales de 5 A, con redistribución legal de recursos libres antes de constituirla.
- Proyectos: Título (1+2+3 K); Pasaporte italiano/polaco (2+3 P y 2 M). Un subhito completo por proyecto y turno; comprobante único y transferible. Solo el titular elegible puede intentar adjudicar desde Universidad/Trámite; pago 1..6, D6 y fallos consumen el intento sin liberar inversiones.
- Dublín: verificación por integrante de título, pasaporte correspondiente, 5 A reservados y 5 K + 5 M libres (sin pagar K/M). Entrada posterior en (5,3) cobra Perfil a ambos, sin consumir puntos de carta.
- Casa: intento únicamente en destino (3,3) si se invoca la acción; reservas adicionales 8 A + 5 P por integrante; oferta base 15 M por persona, reintentos escalados frente a banca y pago solo al ganar. Transferencia de Casa conserva recursos totales al pagar al propietario anterior.
- Casamiento: solo pareja con Casa, hitos, reservas, **afinidad idéntica** y recursos libres finales; se pagan 12 A + 10 P + 5 M por integrante, adicionales a todas las reservas. Una prueba de integración ejerce la salida desde la cuadrícula mediante el motor real.

## Validación local

- `python -m unittest discover -s tests -p '*v2.py' -q`: **51 pruebas superadas** (F1+F2+F3) en Python 3.13, con código geométrico completo, no con simulación auxiliar.
- `python -m laboratorio.smoke_economia_v2 --rondas 4`: **4 escenarios** (Juventud/Adultez × 6/10 jugadores), sin fallos contables y con conservación de mazos.

| Escenario | Turnos | Situaciones resueltas | Emisión A/P/K/M |
|---|---:|---:|---|
| Juventud, 6 | 24 | 24 | 21/47/52/29 |
| Juventud, 10 | 40 | 40 | 31/84/77/43 |
| Adultez, 6 | 24 | 24 | 1/1/1/3 |
| Adultez, 10 | 40 | 40 | 4/3/3/8 |

**Advertencia crucial:** estos valores NO son estimaciones de economía real. Las Situaciones se declararon neutrales, los montos de A/P/K/M adultos se fijaron en 2 como escenario hipotético, las cartas adultas fueron sintéticas y las decisiones de movimiento deterministas (norte/sur). La baja emisión adulta revela la limitación de este escenario, no demuestra desbalance del juego completo.

## Pendientes antes de Monte Carlo real

1. **Orquestación integral de transiciones**: el paso a UTN aún debe cortar movimiento y hacer examen en el mismo turno; reintentos y reparto al cambiar de etapa a mitad de ronda están pendientes. La API `enter_dublin` / `land_from_dublin` está disponible pero no automatizada en el orquestador.
2. **Cartas de Situación aprobadas**: con `neutral_situations=False` (por defecto) se lanza `PendingRuleError`. Los escenarios neutros deben marcarse claramente experimentales.
3. **Montos definitivos de casilleros adultos**: `adult_square_amounts=None` (por defecto) impide pagar ingresos no definidos.
4. **Bots de inversiones y desplazamiento**, formación de pareja, adjudicaciones, compras, negociación, subastas, duelos y cambios de perfil integrados en el turno. El adaptador ofrece acciones que un futuro bot podrá invocar en el orden permitido; no las ejecuta por sí solo.
5. **Reglas de ruptura, disputas y retorno**: todavía no automatizadas, no se presentan como resultados de partida.
6. **Estado de CI remota**: debe verificarse la ejecución en GitHub Actions. Los 51 tests y los cuatro experimentos indicados se corrieron localmente.

## Comandos

```bash
python -m unittest discover -s tests -p 'test_movimiento_v2.py' -v
python -m unittest discover -s tests -p 'test_turnos_v2.py' -v
python -m unittest discover -s tests -p 'test_economia_v2.py' -v
python -m laboratorio.smoke_economia_v2 --rondas 4
```

**Próxima fase sugerida:** cerrar un `GameV2` integral con transición automática UTN y Dublín, mazos sociales reales versionados, políticas de bots y escenarios claramente etiquetados; recién entonces simular 1.000+ partidas para balance.