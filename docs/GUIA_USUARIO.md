# Fase 7 — Estabilización local y preparación para publicación opcional

## Alcance

Se estabiliza la aplicación local para macOS y Python 3.11/3.13, se incorpora diagnóstico offline, lanzamiento local seguro, guía operativa, medición descriptiva de rendimiento y CI dual. **No se modifica ninguna regla, bot, distribución aleatoria, costo, carta ni motor.** Tampoco se toca `main` ni la web pública del juego.

La etapa termina con un producto local verificable. **Publicar en internet requiere autorización posterior**; no se despliega automáticamente ni se presupone que la app deba ser accesible a terceros.

## Cambios realizados

- `laboratorio/diagnostico.py`: revisión de versión de Python, dependencias, hashes del motor/mazo, CSV históricos (2.000 partidas), dirección de escucha local, XSRF, tamaño de carga y escritura del historial. Comando `python -m laboratorio.diagnostico` (también `--json` y `--sin-dependencias`). No ejecuta partidas ni hace llamadas de red.
- `.streamlit/config.toml`: escucha en `127.0.0.1:8501`, protección XSRF y CORS, máximo 24 MB por carga y estadísticas de uso desactivadas. Configuración diseñada expresamente para uso **local**; no sirve sin modificación para despliegue remoto.
- `iniciar_laboratorio.sh`: no hace `pip install` ni `git pull` automáticos; comprueba el entorno con diagnóstico y abre Streamlit en el bucle local.
- `laboratorio/benchmark_fase7.py`: ejecuta un A/B y una matriz 3×3 pequeños con semillas y parámetros conocidos, devuelve duraciones observadas de ese equipo. No impone rendimiento mínimo o máximo: los tiempos dependen de la máquina.
- `laboratorio/app.py`: encabezado correcto de fases 0–7 y ayuda contextual sobre recorrido, persistencia, límites e interpretación.
- `tests/test_estabilizacion_fase7.py`: pruebas de preflight (incluida detección de corrupción), archivo protegido, configuración, lanzador, benchmark y presentación Streamlit.
- `.github/workflows/laboratorio-tests.yml`: matriz Python 3.11 y 3.13, instalación de dependencias, compilación, autodiagnóstico, todas las pruebas e integridad de CSV. La regresión completa 2.000/2.000 corre en 3.11; puede repetirse manualmente en 3.13 si es necesario.
- `docs/GUIA_USUARIO.md` y `docs/PRUEBA_MANUAL_FASE7.md`: instalación, actualización segura, errores frecuentes, flujo funcional y límites.

## Criterios de aceptación

1. El diagnóstico detecta entorno no apto e imprime controles específicos con código de salida no cero.
2. La aplicación se abre sin exponer su servicio fuera de localhost en la configuración incluida.
3. La suite completa pasa en Python 3.11 y Python 3.13 dentro de GitHub Actions; los tests de Streamlit se ejecutan realmente.
4. Las referencias de 1.000 partidas de seis jugadores y 1.000 de diez son binariamente idénticas al motor validado.
5. Pruebas de ejecución, recuperación y comparación de escenarios, Gantt, economía, interacciones, turnos y sensibilidad conservadas.
6. El benchmark da métricas observables, sin umbrales falsos de velocidad.
7. `main` y `index.html` permanecen intactos; no se modifica el motor reglamentario.

## Riesgos y limitaciones conocidos

- El nivel de completitud se refiere al **laboratorio local**, no a una evaluación final de calidad lúdica. Los bots no son jugadores humanos.
- La validación automática no reemplaza verificar manualmente la interfaz en la Mac del usuario. El checklist de prueba queda entregado para ejecución humana.
- Los resultados y los ZIP son datos de investigación; la validación de SHA-256 no constituye firma digital de autoría.
- Publicación remota, autenticación, compartición multiusuario, copias de seguridad remotas, cuotas concurrentes y gestión de secretos no forman parte de esta fase. Para abrir la aplicación a terceros haría falta una etapa de despliegue específico.
- Se recomienda conservar los ZIP de `.laboratorio/` fuera del repositorio antes de cambios importantes.

## Comandos de aceptación

```bash
python -m laboratorio.diagnostico --json
python -m compileall -q laboratorio simulador tests
python -m unittest discover -s tests -p 'test_*.py' -v
python -m laboratorio.verificar_baseline --full
python -m laboratorio.benchmark_fase7 --json
./iniciar_laboratorio.sh
```
