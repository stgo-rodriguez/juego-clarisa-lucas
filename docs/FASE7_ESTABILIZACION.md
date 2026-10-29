# Checklist manual de aceptación — Fase 7 (Mac)

Ejecución humana pendiente hasta que el usuario lo verifique en su equipo. Marcar cada punto al finalizar; **la aprobación de CI no equivale a aceptación visual en macOS**.

- [ ] `git status` sin modificaciones inesperadas; rama `feature/laboratorio-balance`.
- [ ] `python -m laboratorio.diagnostico`: todos los controles OK.
- [ ] `./iniciar_laboratorio.sh`: abre `http://127.0.0.1:8501`, sin errores en Terminal.
- [ ] En modo Base=Experimento (6 jugadores, 20 partidas, todo en 100%, Juv/Adultez 0%), diferencia de rondas = 0.
- [ ] Escenario 90% ganancias, 110% pérdidas: se actualizan métricas, tabla y gráfico.
- [ ] Se reconstruye una partida terminada: Gantt y pérdida/recuperación de hitos visible cuando existe.
- [ ] Economía: cuadro por recurso y etapa; ninguna discrepancia de auditoría.
- [ ] Interacciones: Duelos y negociaciones; ayuda automática diferenciada.
- [ ] Turnos: decisiones ejecutadas y oportunidades, con advertencia metodológica.
- [ ] Guardar un experimento, cerrar Streamlit, reiniciar y **recuperar sin simular**.
- [ ] Exportar ZIP, reimportar ZIP de confianza, y comparar escenarios con semillas comunes.
- [ ] Sensibilidad: 3×3 con 20 partidas; mapa, intervalos y advertencia de censura.
- [ ] Guardar/exportar matriz; cerrar y recuperar sin volver a correr las partidas.
- [ ] Intentar importar archivo corrupto/renombrado como ZIP: se rechaza sin ejecutar código.
- [ ] Detener con **Ctrl+C**; el puerto `8501` queda liberado.

## Evidencia para cerrar la aceptación local

Guardar captura de la página de resultados y salida del autodiagnóstico. No enviar archivos privados ni datos personales al soporte. Si una prueba falla, conservar el mensaje completo de error y el paso exacto.
