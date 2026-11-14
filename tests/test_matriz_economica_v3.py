"""Pruebas del primer entregable del Laboratorio de Balance v3.0."""
import csv
import io
import unittest
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory

from laboratorio.v3.catalogo import (
    CatalogoInvalido, cargar_matriz, emisiones_esperadas, exportar_csv,
    resumen, validar_ajustes, validar_matriz,
)


class MatrizEconomicaV3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = cargar_matriz()
        cls.params = {p["id"]: p for p in cls.data["parametros"]}

    def test_181_parametros_no_heredan_cantidades(self):
        self.assertEqual(len(self.params), 181)
        self.assertTrue(all(row["valor"] is None for row in self.params.values()))
        self.assertTrue(all(row["fuente_seccion"] for row in self.params.values()))

    def test_mecanismos_clave_y_modelo_de_reservas(self):
        required = {
            "UTN_UMBRAL_P", "UTN_UMBRAL_K",
            "TITULO_SUBHITO_1_K", "TITULO_SUBHITO_2_K",
            "TITULO_SUBHITO_3_K", "PASAPORTE_SUBHITO_1_P",
            "PASAPORTE_SUBHITO_2_P", "PASAPORTE_SUBHITO_3_M",
            "DUBLIN_UMBRAL_K", "DUBLIN_UMBRAL_M",
            "PAREJA_RESERVA_A", "CASA_RESERVA_A",
            "CASA_RESERVA_P", "CASA_OFERTA_BASE_M",
            "CASA_OFERTA_INCREMENTO_M", "FALSO_LUCAS_META_M",
            "BANCO_ENTREGA", "BANCO_RECIBE",
        }
        self.assertFalse(required - self.params.keys())
        for key in ["PAREJA_RESERVA_A", "CASA_RESERVA_A",
                    "CASA_RESERVA_P"]:
            self.assertEqual(self.params[key]["flujo"], "RESERVA")
        for key in ["UTN_UMBRAL_P", "DUBLIN_UMBRAL_M"]:
            self.assertEqual(self.params[key]["flujo"], "REQUISITO")
        self.assertEqual(self.params["FALSO_LUCAS_META_M"]["recurso"], "M")

    def test_cobertura_de_cartas_perfiles_y_tableros(self):
        situation = [p for p in self.params.values() if p["id"].startswith("SIT_")]
        self.assertEqual(len(situation), 3 * 2 * 2 * 4 * 2)
        self.assertEqual(
            sum(p["id"].startswith("CAS_I_") for p in self.params.values()), 6
        )
        self.assertEqual(
            sum(p["id"].startswith("CAS_D_") for p in self.params.values()), 6
        )
        self.assertEqual(
            sum(p["id"].startswith("CAS_J_") for p in self.params.values()), 4
        )
        self.assertEqual(
            sum(p["id"].startswith("PERFIL_") for p in self.params.values()), 8
        )
        self.assertEqual(
            sum(p["id"].startswith("AFINIDAD_META_") for p in self.params.values()), 4
        )

    def test_csv_en_repositorio_coincide_con_json(self):
        original = Path(__file__).resolve().parents[1] / "laboratorio" / "v3" / "matriz_economica_v3.csv"
        with original.open("r", newline="", encoding="utf-8-sig") as handle:
            actual = list(csv.DictReader(handle))
        self.assertEqual(len(actual), len(self.params))
        self.assertEqual({r["id"] for r in actual}, set(self.params))
        for r in actual:
            expected = self.params[r["id"]]
            for col in self.data["campos"]:
                self.assertEqual(r[col], "" if expected[col] is None else str(expected[col]))

    def test_exportacion_csv_es_determinista(self):
        with TemporaryDirectory() as d:
            p1 = exportar_csv(self.data, Path(d) / "primero.csv")
            p2 = exportar_csv(self.data, Path(d) / "segundo.csv")
            self.assertEqual(p1.read_bytes(), p2.read_bytes())

    def test_cero_no_equivale_a_valor_sin_definir(self):
        key = "CAS_I_1_A"
        with self.assertRaisesRegex(CatalogoInvalido, "Importe pendiente"):
            emisiones_esperadas(self.data, {}, {key: 1.0})
        self.assertEqual(
            emisiones_esperadas(self.data, {key: 0}, {key: 1.0}),
            {("Infancia", "A"): 0.0},
        )

    def test_produccion_esperada_con_dos_mecanismos(self):
        vals = {"CAS_I_1_A": 3, "SIT_I_C_A_A_GANANCIA": 2}
        activations = {"CAS_I_1_A": 0.25,
                       "SIT_I_C_A_A_GANANCIA": 0.5}
        result = emisiones_esperadas(self.data, vals, activations)
        self.assertEqual(result, {("Infancia", "A"): 1.75})

    def test_escenarios_no_aceptan_tipos_o_reglas_abiertas_como_cifras(self):
        for value in (-1, 1.5, True, "3"):
            with self.assertRaises(CatalogoInvalido):
                validar_ajustes(self.data, {"CAS_I_1_A": value})
        with self.assertRaisesRegex(CatalogoInvalido, "Control reglamentario"):
            validar_ajustes(self.data, {"ADJ_PROB_DADO": 1})
        with self.assertRaises(CatalogoInvalido):
            validar_ajustes(self.data, {"BANCO_RECIBE": 0})
        self.assertEqual(
            validar_ajustes(self.data, {"OBJETIVO_MEZCLA_I_A": 0.5}),
            {"OBJETIVO_MEZCLA_I_A": 0.5},
        )
        with self.assertRaises(CatalogoInvalido):
            validar_ajustes(self.data, {"OBJETIVO_MEZCLA_I_A": 1.2})

    def test_rechaza_parametros_duplicados_faltantes_y_no_nulos(self):
        import copy
        bad = copy.deepcopy(self.data)
        bad["parametros"].append(copy.deepcopy(bad["parametros"][0]))
        with self.assertRaisesRegex(CatalogoInvalido, "Identificador"):
            validar_matriz(bad)
        bad = copy.deepcopy(self.data)
        bad["parametros"][0]["valor"] = 10
        with self.assertRaisesRegex(CatalogoInvalido, "cifra prefijada"):
            validar_matriz(bad)
        bad = copy.deepcopy(self.data)
        bad["parametros"] = [r for r in bad["parametros"]
                            if r["id"] != "FALSO_LUCAS_META_M"]
        with self.assertRaisesRegex(CatalogoInvalido, "Falso Lucas"):
            validar_matriz(bad)


if __name__ == "__main__":
    unittest.main()
