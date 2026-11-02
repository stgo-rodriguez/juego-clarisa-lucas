# Clarisa & Lucas — Simulaciones v2.x · Fase 6: interacciones

**Reglamento rector:** *Especificación Integral v2.0 Consolidada*, 1/11/2026, secciones 10, 14, 16, 17 y 23.  
**Base técnica:** Fases 1–5 en `feature/simulaciones-v2-movimiento`.  
**Alcance:** API verificable de duelos, subastas y rupturas; NO introduce cartas definitivas ni cambia el simulador histórico v1.3.

## Entregables

- `simulador/interacciones_v2.py`: `InteractionV2` (duelos y estados de Pareja), `AuctionCard`, `SocialAuctionsV2`, `attach_social_situations`.
- `tests/test_interacciones_v2.py`: nuevas pruebas de liquidación contable y situación compartida.
- `laboratorio/experimento_interacciones_v2.py`: auditoría sintética de 200 subastas (50 semillas × 2 tamaños × 2 modalidades).
- `docs/datos_fase6/subastas_sinteticas_v2.csv` y `resumen_interacciones_v2.json`: resultados por ejecución y agrupados.
- `.github/workflows/simulaciones-v2.yml`: ejecución de tests Fase 6 y smoke de subastas.

## Mecánicas implementadas

### Duelos

- **Defensor tira primero**; el retador decide **retirarse pagando 1 P al defensor** o lanzar su D6. Una retirada no lanza segundo dado.
- **Duelo ordinario:** el retador declara recurso y apuesta de fondos libres. Victoria estricta: defensor paga al retador; derrota: retador paga al defensor; empate: sin transferencia.
- **Perfil:** exige el mismo personaje, coincidencia exacta y Perfil activo para los dos. En victoria se intercambian *las cartas físicas* ya retenidas y se actualizan profesión/producción y afinidad de ambos. Derrota o empate: no hay intercambio.
- **Hito:** el desafiante debe poseer un comprobante vigente y elegible del proyecto cuyo propietario desafía. Victoria: transferencia del hito y actualización de propietario. Derrota: consumo bancario de 5 K (Título) o 5 P (Pasaporte); empate: mantiene dueño sin pago.
- **Solvencia:** el retador ha de poder pagar la apuesta eventual y 1 P para retirarse, con recursos libres. *Convención técnica restrictiva pendiente:* en duelo ordinario el defensor también debe poder cubrir la apuesta para que el motor liquide sin deuda; no adjudicar esta restricción como norma confirmada del juego.
- **Una disputa iniciada por turno**: se valida al jugador activo en la fase posterior al movimiento y se bloquea un segundo intento en el mismo turno.
- En caso de perder Título o Pasaporte en Adultez, la **pareja conserva sus reservas de Pareja** si siguen intactas, pierde la Casa y retorna a Juventud. La posición juvenil debe pasar como parámetro explícito (regla pendiente). Se verifican disponibilidad de cartas y descarte antes de alterar la propiedad del hito.

### Ruptura y reservas

- `affect_pair_reserve(...)` debe llamarse **solo cuando un efecto legal afecta expresamente la reserva de Pareja**: no se confunden pérdidas de saldo libre con pérdidas de reservas. La pérdida se contabiliza y el compañero puede donar Amor libre inmediatamente para restituir la reserva. Si no alcanza, se rompe la pareja, se devuelven las reservas subsistentes a saldo libre y se pierde la Casa compartida.
- `break_pair(...)` permite ruptura directa y conserva hitos individuales. En Adultez exige coordenada juvenil de retorno, descarta manos restantes y da cartas juveniles a integrantes que aún deban actuar en la ronda.
- Se comprueba conservación de A/P/K/M mediante `EconomyV2.audit()`.
- *Pendiente de integración adicional:* sustituir la actual excepción del `RoundEngine` si una Situación provoca un cambio de etapa **antes** del movimiento en ese mismo turno; este módulo no altera la política de transición todavía no acordada.

### Subastas de apropiación

- **Una ronda**: cada competidor elegible tiene una única oportunidad de ofertar o pasar. Una oferta inferior a la vigente se considera pase definitivo. Nunca se ejecuta una segunda ronda.
- Activo y compañero del activo excluidos; los elegibles pueden provenir de cualquier etapa si la carta lo permite.
- Modalidades: recurso único; elección anticipada por el activo entre dos recursos; recursos heterogéneos comparados por un `compare_heterogeneous` que expresa la evaluación subjetiva del activo. **No existe una conversión automática entre tipos de recursos.**
- El activo selecciona solo entre las mejores ofertas (incluidos empates). `allow_reject` y el resultado exacto cuando no se adjudica están **especificados en cada carta**, no se imponen globalmente. Si faltan, `PendingRuleError`.
- `bid_order` se recibe por **ejecución**, no como identificador fijo dentro de una Situación compartida, de modo que la misma carta funciona cuando la resuelven diferentes jugadores del mismo personaje durante la ronda.
- Solamente el ganador paga la oferta al **activo**, y recibe la parte apropiable; el activo recibe el remanente. Si no hay ganador, la carta determina expresamente si obtiene el beneficio completo o ninguno.
- El adaptador `attach_social_situations(...)` permite integrar una carta de payload `AuctionCard` antes del movimiento sin modificar los demás efectos de Situación. No inventa ni asigna cartas a los seis mazos existentes.

## Verificación y reproducción

Desde la raíz del repositorio:

```bash
python -m unittest discover -s tests -p 'test_*_v2.py' -v
python -m laboratorio.experimento_interacciones_v2 --semillas 50 --out resultados/fase6
python -m laboratorio.experimento_agentes_v2 --semillas 3 --rondas 30 --mano 3 --out resultados/regresion_fase5
```

**Resultado local:** 102/102 tests superados. El motor de la fase anterior sigue pasando el ensayo reducido de regresión con agentes y cartas sintéticas. Se verificó sintaxis de todos los módulos Python.

### Resultados controlados: 200 subastas

| Jugadores | Modo | Casos | Adjudicadas | Rechazos | Sin ofertas | Ofertas válidas medias | Pases medios |
|---|---|---:|---:|---:|---:|---:|---:|
| 6 | fijo | 50 | 42 | 8 | 0 | 2,00 | 3,00 |
| 6 | heterogéneo | 50 | 40 | 8 | 2 | 1,88 | 3,12 |
| 10 | fijo | 50 | 42 | 8 | 0 | 2,68 | 6,32 |
| 10 | heterogéneo | 50 | 41 | 9 | 0 | 2,62 | 6,38 |

*Interpretación limitada:* cada situación usada para el ensayo tiene una apropiación 4 A de un total 6 A, una probabilidad de pase artificial y preferencias de oferta configuradas. Los participantes tienen recursos aleatorios de prueba y el modo heterogéneo usa una preferencia del activo explícita (primero A, luego cantidad), **no una equivalencia numérica de recursos**. No son resultados de partidas completas, ni permiten concluir qué modo se balancea mejor.

## Próximo avance

1. Incorporar por separado políticas de bots de duelo, subasta, negociación y defensa, con pruebas de información visible y límites de una disputa por turno.
2. Calibrar y versionar las seis barajas de Situación reales antes de estimar frecuencia de conflictos por partida.
3. Resolver el tratamiento de cambios de etapa durante la Situación adulta, la posición juvenil de retorno y el caso de defensor sin fondos para una apuesta ordinaria.
4. Ejecutar contrafactuales **de partidas completas** cambiando un solo elemento por corrida, y presentar métricas (interacciones, duración, recuperaciones y ganadores) separadas de las pruebas de componentes.

**CI de GitHub:** workflow ampliado; la validación local no acredita que GitHub Actions ya haya terminado exitosamente.