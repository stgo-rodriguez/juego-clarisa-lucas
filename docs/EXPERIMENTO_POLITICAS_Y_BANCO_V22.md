# Experimento controlado SIMLOG v2.2 — conversión bancaria y políticas por jugador

**Reglamento:** Especificación integral v2.2 (09/11/2026). 
**Rama:** `feature/v22-auditoria-politicas-banco`. 
**Estado:** experimental; NO reemplaza las 700 trazas históricas ni modifica el mazo físico.

## Correcciones implementadas

1. **Banco 2:1:** al cierre de cada turno, un jugador puede convertir exclusivamente saldos libres en la cadena A ↔ P ↔ K ↔ M; una operación por jugador y ronda. Cada operación permite múltiples pares completos (2 del origen por 1 del destino), sin encadenamiento. Un único evento `conversion_bancaria` registra origen/destino, cantidades y participante; el débito y el crédito también quedan en el libro contable. La **decisión de hacer el canje**, y su magnitud, son heurísticas experimentales del agente, no reglas nuevas.
2. **SIMLOG:** cada `situation_resolved` del motor experimental incluye el A/B efectivo y coincide con `turnos.csv` y `proposed_situation`. Se añade canje legible y política por jugador a `turnos.csv`; en el manifiesto quedan políticas y tamaño de mano.
3. **Estrategias por jugador:** `planificador`, `aleatorio`, `mixto`. El escenario mixto reparte exactamente mitad y mitad en mesas de 6 (3+3) y 10 (5+5); equilibra ambos roles y alterna el rol con un planificador adicional según semilla. Se evita filtración de la política entre participantes. La política «aleatorio» representa un bot con decisiones estocásticas, no un jugador humano.
4. **Mano de movimiento adulta:** tamaño parametrizable 3 o 4, conservando regla de gastar mano antes de reponer. El mazo de 120 cartas SYN-A sigue siendo sintético y no sustituye una especificación física aprobada.
5. **Reglas todavía pendientes:** si una acción requiere una ruptura en Adultez sin posición de retorno definida, la partida queda marcada `rule_pending`, guardando motivo y semilla, **sin inventar la transición ni publicar una traza incompleta como válida**. Este estado se analiza como censura y NO como derrota ni como Casamiento.

## Matriz de comparación

| Escenario | Políticas | Mano adulta |
|---|---|---:|
| A | Todos planificadores | 3 |
| B | Mitad planificadores, mitad aleatorios | 3 |
| C | Todos aleatorios | 3 |
| D | Mixto | 4 |
| E | Todos planificadores | 4 |

Cada escenario se evalúa por separado para 6 y 10 jugadores con semillas **3201–3240**, límite **100 rondas** y conversión bancaria habilitada en todos. Se producen **400 intentos** (40 × 5 × 2), y el resultado clasifica Casamiento, límite de rondas o bloqueo por regla pendiente.

## Métricas para comparar

- Casamientos / intentos, porcentaje bloqueado por regla pendiente y casos al límite de rondas
- Mediana y P80 de rondas **solo para partidas terminadas en Casamiento** (no para censuradas)
- Cantidad de conversiones / 100 turnos y saldo económico
- Elecciones A/B y diversidad dentro de cohorte de mismo rol y etapa
- Ganadores planificador/aleatorio por participante, sin atribuir causalidad
- Emisión económica por mecanismo, diferenciada de conversiones y transferencias
- Semillas y asignaciones de políticas por participante, reproducibles

## Comandos

```bash
python -m unittest discover -s tests -p 'test_experimento_politicas_v22.py' -v
python -m laboratorio.simular_versionado --version 2.2 --jugadores 6 --politica mixto --mano 3 --semillas 40 --inicio 3201 --rondas 100 --out resultados/mixto_6j
python -m laboratorio.analizar_experimentos_politicas_v22 --out resultados/mixto_6j
```

La rama experimental está aislada del motor v2.2 original. Se necesitan más simulaciones, políticas humanas realistas y resolver P4 (ubicación de retorno a Juventud tras ruptura adulta) antes de certificar balance.
