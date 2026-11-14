"""Pruebas de optimización conjunta de cantidades de v3.0.

Los números son hipótesis didácticas, no calibración del juego real.
"""
import copy
import json
import unittest

from laboratorio.v3.catalogo import CatalogoInvalido, cargar_matriz
from laboratorio.v3.optimizar import (
    CLAVES_METRICAS, ESCENARIO_EJEMPLO, _domina, _frontera,
    _validar_escenario, evaluar_configuracion, optimizar,
)


class OptimizadorEconomicoV3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.matriz = cargar_matriz()
        cls.escenario = json.loads(
            ESCENARIO_EJEMPLO.read_text(encoding="utf-8")
        )
        cls.fijos = cls.escenario["ajustes_fijos"]
        cls.dominios = cls.escenario["variables"]

    def cantidad_de_premios_y_costos(self, elegido):
        return {
            **self.fijos,
            **dict(zip([v["parametro"] for v in self.dominios], elegido)),
        }

    def test_evaluacion_mesa_ronda_sin_doble_multiplicacion_jugadores(self):
        amounts = self.cantidad_de_premios_y_costos(
            [1, 1, 2, 2, 4, 5, 5, 9]
        )
        report = evaluar_configuracion(self.matriz, self.escenario, amounts)
        offer = report["oferta"]["por_etapa"]["Adultez"]
        self.assertEqual(offer, {"A": 5.0, "P": 5.0, "K": 0.0, "M": 10.0})
        self.assertEqual(report["rutas"][0]["demanda_total"],
                         {"A": 13, "P": 4, "K": 0, "M": 13})
        self.assertEqual(report["rutas"][0]["emision_total"], 20)
        self.assertEqual(report["rutas"][2]["demanda_total"],
                         {"A": 8, "P": 4, "K": 0, "M": 17})
        self.assertEqual(report["rutas"][0]["presion_total"], 1.5)
        self.assertTrue(report["rutas"][0]["faltantes"])

    def test_premios_mayores_reducen_deficit_otros_parametros_fijos(self):
        low = self.cantidad_de_premios_y_costos(
            [1, 1, 2, 2, 4, 5, 5, 9]
        )
        high = {**low, "CAS_D_F1C5_A": 3, "CAS_D_F3C5_M": 4}
        x = evaluar_configuracion(self.matriz, self.escenario, low)
        y = evaluar_configuracion(self.matriz, self.escenario, high)
        self.assertGreater(
            x["objetivos"]["deficit"], y["objetivos"]["deficit"]
        )

    def test_costos_mayores_aumentan_demanda_sin_inventar_emision(self):
        low = self.cantidad_de_premios_y_costos(
            [1, 1, 2, 2, 4, 5, 5, 9]
        )
        high = {**low, "CASA_OFERTA_BASE_M": 6,
                "AFINIDAD_META_A": 7, "FALSO_LUCAS_META_M": 12}
        x = evaluar_configuracion(self.matriz, self.escenario, low)
        y = evaluar_configuracion(self.matriz, self.escenario, high)
        self.assertEqual(x["oferta"], y["oferta"])
        self.assertGreater(
            sum(y["rutas"][0]["demanda_total"].values()),
            sum(x["rutas"][0]["demanda_total"].values()),
        )
        self.assertGreater(
            y["rutas"][2]["demanda_total"]["M"],
            x["rutas"][2]["demanda_total"]["M"],
        )

    def test_exhaustividad_y_pareto_premios_costos(self):
        result = optimizar(self.matriz, self.escenario,
                           max_evaluaciones=1500, semilla=20261114)
        self.assertEqual(result["metodo"], "EXHAUSTIVA")
        self.assertEqual(result["espacio_combinaciones"], 1296)
        self.assertEqual(result["combinaciones_evaluadas"], 1296)
        self.assertGreaterEqual(result["frontera_pareto_total"], 1)
        best = result["mejor_por_pesos"]
        self.assertEqual(set(best["ajustes"]), set(self.fijos) | {
            x["parametro"] for x in self.dominios
        })
        self.assertGreaterEqual(best["puntaje_ponderado"], 0)
        self.assertIn("CASA_OFERTA_BASE_M", best["ajustes"])
        self.assertIn("CAS_D_F1C5_A", best["ajustes"])
        self.assertEqual(len(best["rutas"]), 3)
        for candidate in result["frontera_pareto"]:
            self.assertFalse(_domina(best["objetivos"],
                                     candidate["objetivos"]))

    def test_reproducibilidad_con_pesos_y_semilla_explicitos(self):
        first = optimizar(self.matriz, self.escenario,
                          max_evaluaciones=80, semilla=71, limite_pareto=4)
        second = optimizar(self.matriz, self.escenario,
                           max_evaluaciones=80, semilla=71, limite_pareto=4)
        self.assertEqual(first, second)
        self.assertEqual(first["metodo"], "COORDENADAS_MULTINICIO_DETERMINISTA")
        self.assertLessEqual(first["combinaciones_evaluadas"], 80)
        self.assertGreater(first["combinaciones_evaluadas"], 0)

    def test_un_costo_o_premio_no_asignado_se_rechaza(self):
        case = copy.deepcopy(self.escenario)
        case["ajustes_fijos"].pop("CASA_RESERVA_A")
        with self.assertRaisesRegex(CatalogoInvalido, "Demanda sin importe"):
            _validar_escenario(self.matriz, case)
        case = copy.deepcopy(self.escenario)
        case["fuentes"].append({"parametro": "CAS_D_F2C1_M",
                                "etapa": "Adultez",
                                "activaciones_por_ronda_mesa": .1})
        with self.assertRaises(CatalogoInvalido):
            _validar_escenario(self.matriz, case)

    def test_mezcla_sin_objetivo_y_pesos_cero_invalidados(self):
        case = copy.deepcopy(self.escenario)
        case["mezcla_objetivo"]["Adultez"]["A"] = 0.42
        with self.assertRaisesRegex(CatalogoInvalido, "no suma 1"):
            _validar_escenario(self.matriz, case)
        case = copy.deepcopy(self.escenario)
        case["pesos"] = {k: 0 for k in CLAVES_METRICAS}
        with self.assertRaisesRegex(CatalogoInvalido, "todos cero"):
            _validar_escenario(self.matriz, case)
        case = copy.deepcopy(self.escenario)
        del case["presion_objetivo"]
        with self.assertRaisesRegex(CatalogoInvalido, "sin presion_objetivo"):
            _validar_escenario(self.matriz, case)

    def test_dominio_de_costos_no_se_hereda_de_v2(self):
        self.assertEqual(
            {p["parametro"] for p in self.dominios},
            {"CAS_D_F1C5_A", "SIT_D_C_A_A_GANANCIA",
             "CAS_D_F3C5_M", "PERFIL_C_M",
             "CASA_OFERTA_BASE_M", "AFINIDAD_META_A",
             "AFINIDAD_META_M", "FALSO_LUCAS_META_M"},
        )
        case = copy.deepcopy(self.escenario)
        case["variables"][0]["valores"] = [1, -1]
        with self.assertRaises(CatalogoInvalido):
            _validar_escenario(self.matriz, case)
        case = copy.deepcopy(self.escenario)
        case["variables"][0]["valores"] = [1, True]
        with self.assertRaises(CatalogoInvalido):
            _validar_escenario(self.matriz, case)

    def test_variable_sin_efecto_se_rechaza(self):
        case = copy.deepcopy(self.escenario)
        case["variables"].append({"parametro": "UTN_UMBRAL_P",
                                  "valores": [1, 2]})
        with self.assertRaisesRegex(CatalogoInvalido, "Variables sin efecto"):
            _validar_escenario(self.matriz, case)

    def test_pareto_simple_dominancia_y_truncado(self):
        def row(k, v):
            return {"objetivos": dict(zip(CLAVES_METRICAS, v)),
                    "puntaje_ponderado": sum(v),
                    "ajustes": {"A": k}}
        a = row(1, [1, 1, 1, 1, 1])
        b = row(2, [2, 2, 2, 2, 2])
        c = row(3, [0, 2, 1, 1, 1])
        self.assertTrue(_domina(a["objetivos"], b["objetivos"]))
        self.assertFalse(_domina(a["objetivos"], c["objetivos"]))
        front, total = _frontera([b, a, c], 1)
        self.assertEqual(total, 2)
        self.assertEqual(len(front), 1)
        self.assertEqual(front[0]["ajustes"], {"A": 1})

    def test_rechaza_configuracion_fuera_de_dominio(self):
        amounts = self.cantidad_de_premios_y_costos(
            [1, 1, 2, 2, 4, 5, 5, 9]
        )
        amounts["CAS_D_F1C5_A"] = 999
        with self.assertRaisesRegex(CatalogoInvalido, "fuera del dominio"):
            evaluar_configuracion(self.matriz, self.escenario, amounts)


if __name__ == "__main__":
    unittest.main()
