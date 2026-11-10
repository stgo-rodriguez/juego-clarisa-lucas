# Migración de simulador y SIMLOG v2.1 → v2.2

**Estado:** implementación funcional completada y sujeta a pruebas.

**Especificación v2.2:** [documento consolidado 9 de noviembre de 2026](https://docs.google.com/document/d/1XvdzvRGT5ZGtgljpn5vVJYS4A0KDpqkw/edit). El documento fue proporcionado explícitamente por el usuario.

El delta v2.2 respecto de v2.1 afecta exclusivamente los premios de casilleros de Juventud y Adultez, con la interpretación nueva de la cuadrícula adulta. Los demás aspectos se mantienen, incluidos los asuntos ya pendientes de v2.1.

- Juventud: Universidad y Trámite ya no entregan K/P al pasar ni al caer, pero conservan adjudicación y salida a Dublín.
- Juventud: 6→1 sigue produciendo el Perfil.
- Adultez: desaparecen todas las casillas A/P/K/M; quedan CASA (3,3), COBRAR PERFIL (5,3), vacíos y las tres conexiones exteriores a Casamiento.
- Adultez: el Perfil se cobra al aterrizar en (5,3) y en el ingreso físico gratuito desde Dublín.
- Infancia, UTN, Cartas, afinidad, economía de reservas y duelos: permanecen como v2.1.

**Implementación y uso**: consultar [SIMLOG_V22_ESPECIFICACION_2026_11_09.md](SIMLOG_V22_ESPECIFICACION_2026_11_09.md). Los motores, agentes y manifestadores están separados por versión y se seleccionan con `--version`.

**Criterios de aceptación**: pruebas de regresión 2.1 y 2.2, confirmación de que no se producen los orígenes `juventud_tramite`, `juventud_universidad` ni `adultez_casillero`, generación SIMLOG 2.2, trazabilidad de Perfil y hitos, y partidas controladas de seis y diez jugadores.

Las proporciones económicas por etapa siguen siendo objetivos de balance; no se han recalibrado los mazos para forzarlas.
