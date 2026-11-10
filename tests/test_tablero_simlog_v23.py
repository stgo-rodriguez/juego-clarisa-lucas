"""Pruebas del tablero SIMLOG: cierre real y cobertura de posiciones."""
from __future__ import annotations

import unittest

from laboratorio.tablero_simlog_v23 import (
    _adult_coord, _coordinates, snapshot_de_ronda, dibujar_tablero,
    resumen_ubicaciones,
)


def _row(ronda, turno, jugador, etapa, posicion, role, *, partner=""):
    return {
        "Ronda": str(ronda), "Turno_global": str(turno), "Momento": "despues",
        "Jugador": str(jugador), "Rol": role, "Etapa": etapa,
        "Posicion": posicion, "Pareja": partner,
    }


class TableroSIMLOGV23Tests(unittest.TestCase):
    def setUp(self):
        self.game = {
            "manifest": {
                "schema": "SIMLOG-2.3", "ruleset": "especificacion-integral-2026-11-10",
                "roles": {str(i): ("Clarisa" if i <= 3 else "Lucas")
                          for i in range(1, 7)},
            },
            "turnos.csv": [
                {"Ronda": "14", "Jugador": str(i)} for i in range(1, 7)
            ],
            "estados_jugadores.csv": (
                [
                    _row(14, 83, pid, "Infancia", "1",
                         "Clarisa" if pid <= 3 else "Lucas")
                    for pid in range(1, 7)
                ] + [
                    _row(14, 84, 1, "Adultez", "5,3", "Clarisa", partner="4"),
                    _row(14, 84, 2, "Juventud", "3", "Clarisa"),
                    _row(14, 84, 3, "UTN", "UTN", "Clarisa"),
                    _row(14, 84, 4, "Adultez", "5,3", "Lucas", partner="1"),
                    _row(14, 84, 5, "Vuelo a Dublín", "Vuelo a Dublín", "Lucas"),
                    _row(14, 84, 6, "Casamiento", "Casamiento", "Lucas"),
                ]
            ),
        }

    def test_usa_ultimo_turno_global_de_todos_no_propio(self):
        snapshot = snapshot_de_ronda(self.game, 14)
        self.assertEqual(snapshot["turno"], 84)
        self.assertEqual(len(snapshot["jugadores"]), 6)
        self.assertEqual(snapshot["faltantes"], [])
        self.assertEqual(snapshot["jugadores"][0]["etapa"], "Adultez")
        self.assertEqual(snapshot["jugadores"][0]["pareja"], 4)
        self.assertEqual(snapshot["jugadores"][3]["posicion"], "5,3")

    def test_dibuja_todas_las_fichas_y_casilleros_reales(self):
        fig = dibujar_tablero(self.game, 14, height=570)
        labels = [x.text[0] for x in fig.data if x.mode == "markers+text"]
        self.assertEqual(set(labels), {"C1", "C2", "C3", "L4", "L5", "L6"})
        self.assertEqual(fig.layout.height, 570)
        self.assertEqual(sum(x.get("Ubicación dibujada") == "Sí"
                             for x in resumen_ubicaciones(snapshot_de_ronda(self.game, 14))), 6)

    def test_no_infiere_ubicaciones_ni_oculta_faltantes(self):
        self.game["estados_jugadores.csv"] = (
            self.game["estados_jugadores.csv"][:6]
            + [self.game["estados_jugadores.csv"][6]]
        )
        snap = snapshot_de_ronda(self.game, 14)
        self.assertEqual(snap["turno"], 84)
        self.assertEqual([p["jugador"] for p in snap["jugadores"]], [1])
        self.assertEqual(snap["faltantes"], [2, 3, 4, 5, 6])
        fig = dibujar_tablero(self.game, 14)
        self.assertEqual(len([x for x in fig.data if x.mode == "markers+text"]), 1)

    def test_sin_snapshot_no_sustituye_turnos_anteriores(self):
        snap = snapshot_de_ronda(self.game, 15)
        self.assertTrue(snap["sin_datos"])
        self.assertEqual(snap["jugadores"], [])
        self.assertEqual(snap["faltantes"], [1, 2, 3, 4, 5, 6])

    def test_coordenadas_adultas_solo_si_justificables(self):
        self.assertEqual(_adult_coord("3,3"), (3,3))
        self.assertEqual(_adult_coord("(5, 3)"), (5,3))
        for pos in ("4", "0,3", "6,1", "C", "1.5,2", ""):
            self.assertIsNone(_adult_coord(pos))
        self.assertIsNone(_coordinates({
            "etapa":"Adultez", "posicion":"desconocida", "rol":"Clarisa"
        }))

    def test_permite_hasta_diez_fichas_en_un_casillero(self):
        self.game["manifest"]["roles"] = {
            str(i): "Clarisa" if i <= 5 else "Lucas"
            for i in range(1,11)
        }
        self.game["estados_jugadores.csv"] = [
            _row(1, 10, i, "Adultez", "3,3",
                 "Clarisa" if i <= 5 else "Lucas")
            for i in range(1,11)
        ]
        snap = snapshot_de_ronda(self.game,1)
        self.assertEqual(len(snap["jugadores"]),10)
        fig = dibujar_tablero(self.game,1)
        self.assertEqual(len([x for x in fig.data if x.mode=="markers+text"]), 10)


if __name__ == "__main__":
    unittest.main()
