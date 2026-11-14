"""Regresión de sensibilidad económica v3: semillas apareadas."""
import copy
import json
import unittest
from laboratorio.v3.simulador_experimental import EJEMPLO
from laboratorio.v3.sensibilidad_experimental import comparar


class SensibilidadV3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg=json.loads(EJEMPLO.read_text(encoding="utf-8"))
        cls.variants=[
            {"id":"precio_casa_mas_alto",
             "cambios":{"CASA_OFERTA_BASE_M":6}},
            {"id":"recompensa_mas_alta",
             "cambios":{"CAS_D_F3C5_M":6}}
        ]

    def test_sensibilidad_pareada_y_parametros_no_mutados(self):
        source=copy.deepcopy(self.cfg)
        res=comparar(self.cfg,self.variants,partidas=4,semilla=2100)
        self.assertEqual(self.cfg,source)
        self.assertEqual(res["partidas"],4)
        self.assertEqual(len(res["experimentos"]),2)
        self.assertEqual(res["semillas"],[2100,2103])
        for exp in res["experimentos"]:
            self.assertEqual(len(exp["comparaciones_pareadas"]),4)
            self.assertEqual(
                [r["semilla"] for r in exp["comparaciones_pareadas"]],
                [2100,2101,2102,2103]
            )
            self.assertEqual(sum(exp["cierres"].values()),4)

    def test_determinista_bajo_misma_semilla(self):
        a=comparar(self.cfg,self.variants,partidas=3,semilla=2200)
        b=comparar(self.cfg,self.variants,partidas=3,semilla=2200)
        self.assertEqual(a,b)

    def test_no_acepta_cambios_sin_efecto_o_desconocidos(self):
        for change in (
            {"CASA_OFERTA_BASE_M":self.cfg["parametros"]["CASA_OFERTA_BASE_M"]},
            {"INVENTADO":4},
            {},
        ):
            with self.assertRaises(ValueError):
                comparar(self.cfg,[{"id":"mal","cambios":change}],partidas=1)
        with self.assertRaises(ValueError):
            comparar(self.cfg,[{"id":"igual","cambios":{"CASA_OFERTA_BASE_M":6}},
                               {"id":"igual","cambios":{"CAS_D_F3C5_M":6}}],
                     partidas=1)

    def test_no_confunde_censura_con_victoria(self):
        tiny=copy.deepcopy(self.cfg)
        tiny["rondas_maximas"]=1
        out=comparar(tiny,[{"id":"cambio",
                           "cambios":{"CASA_OFERTA_BASE_M":6}}],
                     partidas=3)
        self.assertEqual(out["base"]["censuradas"],3)
        self.assertIsNone(out["base"]["mediana_cierres"])
        self.assertTrue(all(e["censuradas"]==3
                            and e["mediana_cierres"] is None
                            for e in out["experimentos"]))


if __name__=="__main__":
    unittest.main()
