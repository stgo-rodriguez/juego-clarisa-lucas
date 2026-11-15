import copy
import math
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from modelo_matematico import cargar_catalogo
from infancia_markov import analizar_infancia_utn

def escenario():
    c=copy.deepcopy(cargar_catalogo())
    o=c["supuestos"]["utn_v31"]
    o.update(rol="Clarisa",posicion_inicial=5,P_inicial=0,K_inicial=0,modo_situaciones="neutras")
    c["requisitos"]["utn"]={"P":0,"K":0}
    for m in c["etapas"]["infancia"]["mecanismos"]:
        if m["tipo"]=="casillero":
            for key in ("P","K"):
                if key in m["premios"]:
                    m["premios"][key]=0
    return c

class MarkovUTNTest(unittest.TestCase):
    def test_valores_abiertos_permanecen_pendientes(self):
        x=analizar_infancia_utn(cargar_catalogo())
        self.assertEqual(x["estado"],"pendiente")

    def test_examen_geometrico_media_dos(self):
        c=escenario()
        x=analizar_infancia_utn(c)
        self.assertEqual(x["estado"],"calculado")
        self.assertAlmostEqual(x["rondas_esperadas"],3,places=6)

    def test_movimiento_impacta(self):
        c=escenario()
        c["supuestos"]["utn_v31"]["posicion_inicial"]=1
        x=analizar_infancia_utn(c)
        self.assertEqual(x["estado"],"calculado")
        self.assertGreater(x["rondas_esperadas"],3)

    def test_deficit_sin_fuente_es_inalcanzable(self):
        c=escenario()
        c["requisitos"]["utn"]={"P":1,"K":1}
        self.assertEqual(analizar_infancia_utn(c)["estado"],"inalcanzable")

    def test_premios_producen_solucion(self):
        c=escenario()
        c["requisitos"]["utn"]={"P":1,"K":1}
        for mid,k in (("i_c2","P"),("i_c4","P"),("i_c5","K")):
            next(m for m in c["etapas"]["infancia"]["mecanismos"] if m["id"]==mid)["premios"][k]=1
        x=analizar_infancia_utn(c)
        self.assertEqual(x["estado"],"calculado")
        self.assertGreater(x["rondas_esperadas"],3)

    def test_situacion_faltante_bloquea(self):
        c=escenario()
        c["supuestos"]["utn_v31"]["modo_situaciones"]="configuradas"
        self.assertEqual(analizar_infancia_utn(c)["estado"],"pendiente")

    def test_situacion_nula_identica_no_exige_probabilidad(self):
        c=escenario()
        c["supuestos"]["utn_v31"]["modo_situaciones"]="configuradas"
        m=next(m for m in c["etapas"]["infancia"]["mecanismos"] if m["id"]=="i_s_c")
        for side in ("opcion_A","opcion_B"):
            m[side]["P"]=m[side]["K"]=0
        self.assertEqual(analizar_infancia_utn(c)["estado"],"calculado")

    def test_entrada_y_examen_separados(self):
        c=escenario()
        c["supuestos"]["utn_v31"]["posicion_inicial"]=5
        self.assertAlmostEqual(analizar_infancia_utn(c)["rondas_esperadas"],3,places=6)

if __name__=="__main__":
    unittest.main()
