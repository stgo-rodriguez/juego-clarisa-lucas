"""Pruebas de invariantes económicos para el prototipo determinista."""
import copy
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from modelo_matematico import cargar_catalogo, evaluar  # noqa: E402

RECURSOS = "APKM"


def escenario_conocido():
    config = copy.deepcopy(cargar_catalogo())
    for etapa in config["etapas"].values():
        for m in etapa["mecanismos"]:
            if m["frecuencia"] is None:
                m["frecuencia"] = 0
            if m.get("probabilidad_A") is None and m["tipo"] == "situacion":
                m["probabilidad_A"] = .5
            for campo in ("premios", "opcion_A", "opcion_B"):
                if campo in m:
                    for k, v in m[campo].items():
                        if v is None:
                            m[campo][k] = 0
    r = config["requisitos"]
    r["utn"] = {"P": 0, "K": 4}
    for proyecto in ("titulo", "pasaporte"):
        for hito in r[proyecto]:
            for k in RECURSOS:
                hito[k] = 0
    for name in ("adjudicacion_titulo", "adjudicacion_pasaporte", "pareja", "vuelo", "afinidad"):
        for k in r[name]:
            r[name][k] = 0
    for k in r["casa"]["reserva_individual"]:
        r["casa"]["reserva_individual"][k] = 0
    r["casa"]["precio_M"] = 0
    r["falso_lucas_M"] = 0
    s = config["supuestos"]
    s["fraccion_precio_casa_lucas"] = .5
    s["multiplicador_destinos_en_pareja_juventud"] = 1
    for m in config["etapas"]["infancia"]["mecanismos"]:
        if m["id"] == "i_c5":
            m["premios"]["K"] = 4
    return config


class ModeloMatematicoTest(unittest.TestCase):
    def test_catalogo_sin_premios_no_inventa_cifras(self):
        dato = cargar_catalogo()
        resultado = evaluar(dato)
        self.assertIsNone(resultado["estimaciones"]["boda_autentica"])
        self.assertIsNone(resultado["flujos"]["infancia"]["Clarisa"]["K"])

    def test_cota_utn_dado_uniforme(self):
        r = evaluar(escenario_conocido())
        self.assertAlmostEqual(r["etapas"]["infancia"], 6)
        self.assertAlmostEqual(r["estimaciones"]["boda_autentica"], 6)

    def test_afinidades_identicas_no_duplican(self):
        sc = escenario_conocido()
        sc["requisitos"]["afinidad"]["K"] = 8
        sc["supuestos"]["afinidad_clarisa"] = "K"
        sc["supuestos"]["afinidad_lucas"] = "K"
        r = evaluar(sc)
        self.assertEqual(r["necesidades"]["afinidad"]["K"], 8)

    def test_afinidades_diferentes_exigen_ambas(self):
        sc = escenario_conocido()
        sc["requisitos"]["afinidad"]["K"] = 8
        sc["requisitos"]["afinidad"]["A"] = 3
        sc["supuestos"]["afinidad_clarisa"] = "K"
        sc["supuestos"]["afinidad_lucas"] = "A"
        r = evaluar(sc)
        self.assertEqual(r["necesidades"]["afinidad"]["K"], 8)
        self.assertEqual(r["necesidades"]["afinidad"]["A"], 3)
        self.assertTrue(math.isinf(r["estimaciones"]["boda_autentica"]))

    def test_imposible_propaga_hasta_victorias(self):
        sc = escenario_conocido()
        for m in sc["etapas"]["infancia"]["mecanismos"]:
            if m["id"] == "i_c5":
                m["premios"]["K"] = 0
        r = evaluar(sc)
        self.assertTrue(math.isinf(r["estimaciones"]["utn"]))
        self.assertTrue(math.isinf(r["estimaciones"]["falso_lucas"]))

    def test_menos_generacion_mas_rondas(self):
        sc = escenario_conocido()
        r1 = evaluar(sc)["etapas"]["infancia"]
        for m in sc["etapas"]["infancia"]["mecanismos"]:
            if m["id"] == "i_c5":
                m["premios"]["K"] = 2
        r2 = evaluar(sc)["etapas"]["infancia"]
        self.assertAlmostEqual(r2, 2 * r1)

    def test_no_modificar_entrada(self):
        sc = escenario_conocido()
        original = copy.deepcopy(sc)
        evaluar(sc)
        self.assertEqual(sc, original)


if __name__ == "__main__":
    unittest.main()
