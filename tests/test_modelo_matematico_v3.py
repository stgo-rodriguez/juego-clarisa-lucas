"""Validación del motor matemático v3.0 sin usar el simulador v2.x."""
import copy
import unittest

from laboratorio.v3.catalogo import CatalogoInvalido, cargar_matriz
from laboratorio.v3.modelo_matematico import (
    calcular_demanda_secuencial, calibrar_emisiones,
    combinar_metas_afinidad, proyectar_flujos, tasas_desde_demanda,
)


class ModeloMatematicoV3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.matriz = cargar_matriz()

    def test_emision_consumo_reserva_inversion_y_transferencia_separados(self):
        ajustes = {
            "CAS_I_1_A": 4, "SIT_I_C_A_A_PERDIDA": 2,
            "PAREJA_RESERVA_A": 3, "DUELO_ORDINARIO_APUESTA_A": 7,
            "TITULO_SUBHITO_1_K": 5,
        }
        events = [
            {"parametro": "CAS_I_1_A", "etapa": "Infancia", "frecuencia": 0.5},
            {"parametro": "SIT_I_C_A_A_PERDIDA", "etapa": "Infancia",
             "frecuencia": 0.25, "perdida_efectiva": True},
            {"parametro": "PAREJA_RESERVA_A", "etapa": "Juventud",
             "frecuencia": 0.25},
            {"parametro": "DUELO_ORDINARIO_APUESTA_A", "etapa": "Juventud",
             "frecuencia": 0.4},
            {"parametro": "TITULO_SUBHITO_1_K", "etapa": "Juventud",
             "frecuencia": 0.4},
        ]
        p = proyectar_flujos(self.matriz, ajustes, events)
        inf = p["etapas"]["Infancia"]["recursos"]["A"]
        self.assertEqual(inf["flujos"]["EMISION"], 2)
        self.assertEqual(inf["flujos"]["CONSUMO"], 0.5)
        self.assertEqual(inf["creacion_mesa_neta"], 1.5)
        self.assertEqual(inf["delta_libre_sin_transferencias"], 1.5)
        youth = p["etapas"]["Juventud"]["recursos"]["A"]
        self.assertEqual(youth["flujos"]["RESERVA"], 0.75)
        self.assertAlmostEqual(youth["volumen_redistribuido"], 2.8)
        self.assertEqual(youth["creacion_mesa_neta"], 0.0)
        self.assertEqual(youth["delta_libre_sin_transferencias"], -0.75)
        self.assertEqual(
            p["etapas"]["Juventud"]["recursos"]["K"]["flujos"]["INVERSION"], 2
        )
        self.assertEqual(p["etapas"]["Juventud"]["recursos"]["K"]["creacion_mesa_neta"], 0)
        self.assertEqual(p["etapas"]["Juventud"]["recursos"]["K"]["delta_libre_sin_transferencias"], -2)
        self.assertFalse(p["advertencias"])

    def test_perdidas_nominales_no_pretenden_ser_efectivas(self):
        p = proyectar_flujos(
            self.matriz, {"SIT_I_C_A_P_PERDIDA": 4}, [
                {"parametro": "SIT_I_C_A_P_PERDIDA", "etapa": "Infancia",
                 "frecuencia": 1}
            ],
        )
        self.assertEqual(len(p["advertencias"]), 1)
        self.assertIn("consumo efectivo", p["advertencias"][0])

    def test_perfiles_deben_especificar_etapa(self):
        with self.assertRaisesRegex(CatalogoInvalido, "Etapa desconocida"):
            proyectar_flujos(
                self.matriz, {"PERFIL_C_M": 3}, [
                    {"parametro": "PERFIL_C_M", "etapa": "Juventud/Adultez",
                     "frecuencia": 1}
                ],
            )
        p = proyectar_flujos(
            self.matriz, {"PERFIL_C_M": 3}, [
                {"parametro": "PERFIL_C_M", "etapa": "Adultez",
                 "frecuencia": 0.5}
            ],
        )
        self.assertEqual(p["etapas"]["Adultez"]["recursos"]["M"]["flujos"]["EMISION"], 1.5)

    def test_efectos_diferentes_por_carta_no_forzados_iguales(self):
        source = "SIT_I_C_A_K_GANANCIA"
        p = proyectar_flujos(self.matriz, {}, [
            {"parametro": source, "etapa": "Infancia", "instancia": "I-C-01",
             "importe_instancia": 1, "frecuencia": 0.25},
            {"parametro": source, "etapa": "Infancia", "instancia": "I-C-02",
             "importe_instancia": 4, "frecuencia": 0.25},
        ])
        self.assertEqual(p["etapas"]["Infancia"]["recursos"]["K"]["flujos"]["EMISION"], 1.25)

    def test_casa_separa_compra_de_redistribucion(self):
        source = "CASA_OFERTA_BASE_M"
        base = {"parametro": source, "etapa": "Adultez", "frecuencia": 0.2}
        p = proyectar_flujos(
            self.matriz, {source: 10},
            [dict(base, destino="banca")],
        )
        self.assertEqual(p["etapas"]["Adultez"]["recursos"]["M"]["flujos"]["CONSUMO"], 2)
        t = proyectar_flujos(
            self.matriz, {source: 10},
            [dict(base, destino="propietarios")],
        )
        self.assertEqual(t["etapas"]["Adultez"]["recursos"]["M"]["volumen_redistribuido"], 2)
        self.assertEqual(t["etapas"]["Adultez"]["recursos"]["M"]["creacion_mesa_neta"], 0)
        with self.assertRaisesRegex(CatalogoInvalido, "banca"):
            proyectar_flujos(self.matriz, {source: 10}, [base])

    def test_rechaza_importes_faltantes_y_parametros_inventados(self):
        with self.assertRaisesRegex(CatalogoInvalido, "Falta importe"):
            proyectar_flujos(self.matriz, {}, [
                {"parametro": "CAS_I_1_A", "etapa": "Infancia", "frecuencia": 0.5},
            ])
        with self.assertRaises(CatalogoInvalido):
            proyectar_flujos(self.matriz, {"CAS_I_1_A": 3}, [
                {"parametro": "CAS_I_1_A", "etapa": "Adultez", "frecuencia": 1},
            ])
        with self.assertRaises(CatalogoInvalido):
            proyectar_flujos(self.matriz, {}, [
                {"parametro": "ESTO_NO_EXISTE", "etapa": "Infancia", "frecuencia": 1},
            ])
        with self.assertRaises(CatalogoInvalido):
            proyectar_flujos(self.matriz, {}, [
                {"parametro": "CAS_I_1_A", "etapa": "Infancia", "frecuencia": -0.1},
            ])

    def test_calibrador_inverso_proporcion_por_mecanismo(self):
        goals = {"Juventud": {"A": 0, "P": 0, "K": 2, "M": 0}}
        sources = [
            {"parametro": "SIT_J_C_A_K_GANANCIA", "etapa": "Juventud",
             "instancia": "J-C-01", "frecuencia": 0.5, "cuota": 0.75},
            {"parametro": "PERFIL_C_K", "etapa": "Juventud",
             "instancia": "perfil-01", "frecuencia": 0.5, "cuota": 0.25},
        ]
        p = calibrar_emisiones(self.matriz, goals, sources)
        self.assertEqual(len(p["recomendaciones"]), 2)
        self.assertEqual([x["importe_medio_activacion"] for x in p["recomendaciones"]], [3, 1])
        self.assertFalse(any(x["ajuste_requiere_distribucion_de_premios"]
                             for x in p["recomendaciones"]))

    def test_calibrador_reconoce_fracciones_sin_falsos_enteros(self):
        goals = {"Infancia": {"A": 1, "P": 0, "K": 0, "M": 0}}
        sources = [
            {"parametro": "CAS_I_1_A", "etapa": "Infancia", "frecuencia": 0.4,
             "cuota": 1},
        ]
        p = calibrar_emisiones(self.matriz, goals, sources)
        x = p["recomendaciones"][0]
        self.assertEqual(x["importe_medio_activacion"], 2.5)
        self.assertEqual((x["entero_inferior"], x["entero_superior"]), (2, 3))
        self.assertTrue(x["ajuste_requiere_distribucion_de_premios"])

    def test_calibrador_no_oculta_frecuencias_cero_ni_cuotas_incompletas(self):
        goal = {"Infancia": {"A": 1, "P": 0, "K": 0, "M": 0}}
        with self.assertRaisesRegex(CatalogoInvalido, "suman"):
            calibrar_emisiones(self.matriz, goal, [{
                "parametro": "CAS_I_1_A", "etapa": "Infancia",
                "frecuencia": 1, "cuota": .5
            }])
        with self.assertRaisesRegex(CatalogoInvalido, "sin frecuencia"):
            calibrar_emisiones(self.matriz, goal, [{
                "parametro": "CAS_I_1_A", "etapa": "Infancia",
                "frecuencia": 0, "cuota": 1
            }])
        with self.assertRaisesRegex(CatalogoInvalido, "identificar carta/Perfil"):
            calibrar_emisiones(self.matriz, goal, [{
                "parametro": "SIT_I_C_A_A_GANANCIA", "etapa": "Infancia",
                "frecuencia": 1, "cuota": 1
            }])

    def test_afinidades_mismo_recurso_no_suman(self):
        cards = [{"recurso": "A", "cantidad": 7},
                 {"recurso": "A", "cantidad": 7}]
        self.assertEqual(combinar_metas_afinidad(cards), {"A": 7})
        self.assertEqual(combinar_metas_afinidad([
            cards[0], {"recurso": "M", "cantidad": 5}
        ]), {"A": 7, "M": 5})

    def test_afinidades_mismo_recurso_distinta_cantidad_siguen_abiertas(self):
        cards = [{"recurso": "A", "cantidad": 7},
                 {"recurso": "A", "cantidad": 9}]
        with self.assertRaisesRegex(CatalogoInvalido, "ABIERTA"):
            combinar_metas_afinidad(cards)
        self.assertEqual(
            combinar_metas_afinidad(cards, politica_coincidencia="maximo_experimental"),
            {"A": 9},
        )

    def test_demanda_secuencial_requisito_sin_consumo_reserva_y_pago(self):
        amounts = {"UTN_UMBRAL_P": 2, "UTN_UMBRAL_K": 1,
                   "PAREJA_RESERVA_A": 3, "CASA_RESERVA_A": 4,
                   "CASA_OFERTA_BASE_M": 6, "AFINIDAD_META_M": 7}
        events = [
            {"etapa": "Infancia", "hito": "UTN", "parametro": "UTN_UMBRAL_P", "actores": ["C"]},
            {"etapa": "Infancia", "hito": "UTN", "parametro": "UTN_UMBRAL_K", "actores": ["C"]},
            {"etapa": "Juventud", "hito": "Pareja", "parametro": "PAREJA_RESERVA_A",
             "actores": ["C", "L"], "por_integrante": True},
            {"etapa": "Adultez", "hito": "Casa", "parametro": "CASA_RESERVA_A",
             "actores": ["C", "L"], "por_integrante": True},
            {"etapa": "Adultez", "hito": "Casa", "parametro": "CASA_OFERTA_BASE_M",
             "actores": ["C", "L"], "por_integrante": True, "destino": "banca"},
            {"etapa": "Adultez", "hito": "Boda", "parametro": "AFINIDAD_META_M",
             "actores": ["C", "L"], "modo_objetivo": "pago"},
        ]
        res = calcular_demanda_secuencial(
            self.matriz, amounts, ["C", "L"], events
        )
        self.assertEqual(res["produccion_minima_total"], {"A": 14, "P": 2, "K": 1, "M": 19})
        self.assertEqual(res["estado_final"]["C"]["A"]["reserva_pareja"], 3)
        self.assertEqual(res["estado_final"]["L"]["A"]["reserva_pareja"], 3)
        self.assertEqual(res["estado_final"]["C"]["A"]["reserva_casa"], 4)
        self.assertEqual(res["estado_final"]["L"]["A"]["reserva_casa"], 4)
        self.assertEqual(res["estado_final"]["C"]["P"]["libre"], 2)
        self.assertEqual(res["estado_final"]["C"]["M"]["libre"], 0)

    def test_demanda_no_suma_dos_veces_un_umbral(self):
        amounts = {"UTN_UMBRAL_P": 4}
        stages = [
            {"etapa": "Infancia", "parametro": "UTN_UMBRAL_P", "actores": ["C"]},
            {"etapa": "Infancia", "parametro": "UTN_UMBRAL_P", "actores": ["C"]},
        ]
        r = calcular_demanda_secuencial(self.matriz, amounts, ["C"], stages)
        self.assertEqual(r["produccion_minima_total"]["P"], 4)

    def test_demanda_falso_lucas_individual(self):
        amounts = {"FALSO_LUCAS_META_M": 10, "CASA_OFERTA_BASE_M": 6}
        events = [
            {"etapa": "Adultez", "parametro": "CASA_OFERTA_BASE_M",
             "actores": ["C", "F"], "por_integrante": True, "destino": "banca"},
            {"etapa": "Adultez", "parametro": "FALSO_LUCAS_META_M",
             "actores": ["F"], "modo_objetivo": "comprobacion"},
        ]
        res = calcular_demanda_secuencial(
            self.matriz, amounts, ["C", "F"], events
        )
        self.assertEqual(res["produccion_minima_total"]["M"], 22)
        self.assertEqual(res["estado_final"]["F"]["M"]["libre"], 10)
        self.assertEqual(res["estado_final"]["C"]["M"]["libre"], 0)

    def test_demanda_rechaza_objetivo_ambiguo_y_costos_sin_regla(self):
        with self.assertRaisesRegex(CatalogoInvalido, "modo explícito"):
            calcular_demanda_secuencial(
                self.matriz, {"AFINIDAD_META_K": 5},
                ["C", "L"], [{"etapa": "Adultez", "parametro": "AFINIDAD_META_K",
                              "actores": ["C", "L"]}],
            )
        with self.assertRaisesRegex(CatalogoInvalido, "especificar destino"):
            calcular_demanda_secuencial(
                self.matriz, {"CASA_OFERTA_BASE_M": 5},
                ["C", "L"], [{"etapa": "Adultez",
                              "parametro": "CASA_OFERTA_BASE_M",
                              "actores": ["C", "L"]}],
            )
        with self.assertRaisesRegex(CatalogoInvalido, "Falta importe"):
            calcular_demanda_secuencial(
                self.matriz, {},
                ["C", "L"], [{"etapa": "Adultez",
                              "parametro": "AFINIDAD_META_K",
                              "actores": ["C", "L"],
                              "modo_objetivo": "pago"}],
            )


    def test_convertir_demanda_en_tasa_por_jugador_y_ronda(self):
        demands = {"produccion_minima_por_etapa": {
            "Infancia": {"A": 0, "P": 0, "K": 0, "M": 0},
            "Juventud": {"A": 0, "P": 0, "K": 0, "M": 0},
            "Adultez": {"A": 14, "P": 4, "K": 0, "M": 19},
        }}
        result = tasas_desde_demanda(
            demands, {"Adultez": 5}, {"Adultez": 2},
            perdidas_estimadas={"Adultez": {"A": 2}},
            holgura={"Adultez": {"M": 1}},
        )
        self.assertEqual(result["objetivos_emision"]["Adultez"],
                         {"A": 1.6, "P": 0.4, "K": 0.0, "M": 2.0})
        self.assertEqual(result["objetivos_emision"]["Infancia"]["A"], 0)
        with self.assertRaisesRegex(CatalogoInvalido, "Faltan rondas"):
            tasas_desde_demanda(demands, {}, {})
        with self.assertRaisesRegex(CatalogoInvalido, "positivos"):
            tasas_desde_demanda(
                demands, {"Adultez": 0}, {"Adultez": 2},
            )

    def test_escenario_didactico_tres_rutas_reproducible(self):
        import json
        from pathlib import Path
        from laboratorio.v3.ejecutar_modelo import analizar_escenario, EJEMPLO
        escenario = json.loads(EJEMPLO.read_text(encoding="utf-8"))
        output = analizar_escenario(escenario)
        emit = output["flujos_esperados"]["etapas"]["Adultez"]["recursos"]
        self.assertEqual({r: emit[r]["flujos"].get("EMISION", 0) for r in "APKM"},
                         {"A": 2, "P": 1, "K": 0, "M": 3})
        results = output["rutas"]
        self.assertEqual(set(results),
                         {"boda_lucas_autentico",
                          "boda_falso_lucas",
                          "victoria_individual_falso_lucas"})
        b1 = results["boda_lucas_autentico"]["demanda"]
        b2 = results["boda_falso_lucas"]["demanda"]
        f = results["victoria_individual_falso_lucas"]["demanda"]
        self.assertEqual(b1["produccion_minima_total"],
                         {"A": 15, "P": 4, "K": 0, "M": 19})
        self.assertEqual(b2["produccion_minima_total"],
                         {"A": 15, "P": 4, "K": 0, "M": 19})
        self.assertEqual(f["produccion_minima_total"],
                         {"A": 8, "P": 4, "K": 0, "M": 22})
        self.assertEqual(results["boda_falso_lucas"]["ganadores_hipoteticos"],
                         ["C"])
        self.assertEqual(results["victoria_individual_falso_lucas"]["ganadores_hipoteticos"],
                         ["F"])
        cuotas = output["calibracion_inversa_condicionada_a_hipotesis"]
        self.assertEqual(
            sorted((x["importe_medio_activacion"] for x in cuotas["recomendaciones"])),
            [2, 2, 2, 3, 3]
        )


if __name__ == "__main__":
    unittest.main()
