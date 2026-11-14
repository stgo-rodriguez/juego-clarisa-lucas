"""Pruebas del simulador ECONÓMICO experimental v3.0; sin importes aprobados."""
import copy
import json
import unittest

from laboratorio.v3.estado_v3 import LibroMayor, Personaje, EstadoInvalido
from laboratorio.v3.simulador_experimental import (
    EJEMPLO, SimulacionV3, ejecutar_lote, validar_config
)


class SimuladorExperimentalV3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = json.loads(EJEMPLO.read_text(encoding="utf-8"))

    def make(self,n=6,seed=2001,policy="planificador"):
        return SimulacionV3(self.cfg,n,seed,policy)

    def test_parametros_son_externos_y_cinco_de_hitos(self):
        validar_config(self.cfg)
        c=copy.deepcopy(self.cfg)
        del c["parametros"]["CASA_OFERTA_BASE_M"]
        with self.assertRaisesRegex(ValueError,"obligatorios"):
            validar_config(c)
        c=copy.deepcopy(self.cfg)
        c["etiqueta"]="VALORES_APROBADOS"
        with self.assertRaisesRegex(ValueError,"experimental"):
            validar_config(c)

    def test_una_identidad_falsa_secreta_y_reparto_de_recursos(self):
        for players in (6,10):
            s=self.make(players)
            self.assertEqual(sum(p.falso for p in s.personas.values()),1)
            false=next(p for p in s.personas.values() if p.falso)
            self.assertEqual(false.rol,"Lucas")
            self.assertFalse(false.secreto_revelado)
            self.assertFalse(false.afinidad_revelada)
            self.assertEqual(len(s.personas),players)
            self.assertTrue(all(p.perfil=="" for p in s.personas.values()))
            self.assertFalse(any("falso" in e for e in s.eventos))

    def test_libro_mayor_no_duplica_reservas_ni_inversiones(self):
        p=Personaje(id="C1",rol="Clarisa")
        q=Personaje(id="L1",rol="Lucas")
        ledger=LibroMayor({"C1":p,"L1":q})
        ledger.emitir(1,"Casillero","C1","A",10,"CAS_I_1_A")
        ledger.reservar(1,"C1","A",4,"reserva_pareja","PAREJA_RESERVA_A")
        self.assertEqual(p.libre("A"),6)
        ledger.transferir(1,"acuerdo","C1","L1","A",2,"ACUERDO")
        ledger.perder(1,"C1","A",7,"SIT_I_C_B_A_PERDIDA")
        self.assertEqual(p.libre("A"),0)
        self.assertEqual(p.recursos["A"]["reserva_pareja"],1)
        self.assertEqual(ledger.total_emitido["A"],10)
        self.assertEqual(ledger.total_consumido["A"],7)
        ledger.comprobar()
        with self.assertRaises(EstadoInvalido):
            ledger.reservar(1,"C1","A",1,"reserva_casa","CASA_RESERVA_A")

    def test_entrada_utn_y_examen_posterior_sin_pagar_umbral(self):
        s=self.make()
        p=s.personas["C1"]
        s.ronda=1
        s.economia.emitir(1,"test",p.id,"P",3,"TEST")
        s.economia.emitir(1,"test",p.id,"K",3,"TEST")
        p.posicion="UTN"
        p.utm_regreso=False
        c={"id":"I-C-test", "_situation_stage":"Infancia",
           "_situation_role":"Clarisa","A":{},"B":{}}
        s._lanzar=lambda:4
        s._infancia(p,c)
        self.assertTrue(p.examen_aprobado)
        self.assertEqual(p.etapa,"Juventud")
        self.assertEqual(p.libre("P"),3)
        self.assertEqual(p.libre("K"),3)
        self.assertNotEqual(p.perfil,"")
        self.assertTrue(s.economia.comprobar())

    def test_bot_puede_entrar_a_utn_sin_umbral_y_sufrir_regreso(self):
        s=self.make()
        s.rules["politica_entrada_utn"]="entrar_aunque_falten"
        p=s.personas["C1"];p.posicion=1;s.ronda=1
        s._lanzar=lambda:5
        moved,rolled=s._mover_infancia(p)
        self.assertTrue(moved)
        self.assertEqual(p.posicion,"UTN")
        card={"id":"I-C-test","_situation_stage":"Infancia",
              "_situation_role":"Clarisa","A":{},"B":{}}
        s._efecto(p,card,"A")
        self.assertFalse(s._satisface_utn(p))
        p.utm_regreso=True
        moved,rolled=s._mover_infancia(p)
        self.assertEqual(p.posicion,3)  # UTN → 5 consume 1 step, then four.
        s.economia.comprobar()

    def test_boda_no_puede_hacerse_desde_un_casillero_no_conectado(self):
        s,p,q=self._boda_setup(False)
        p.posicion=(3,3);q.posicion=(3,3)
        self.assertTrue(s._puede_casarse(p))
        self.assertFalse(s._casarse(p))
        self.assertIsNone(s.cierre)

    def test_utm_sin_requisitos_regresa_con_un_paso_consumido(self):
        s=self.make()
        p=s.personas["C1"];p.posicion="UTN";p.utm_regreso=True
        s._lanzar=lambda:1
        moved,rolled=s._mover_infancia(p)
        self.assertTrue(moved)
        self.assertEqual((rolled,p.posicion),(1,5))
        self.assertEqual(p.libre("K"),s.values["CAS_I_5_K"])

    def test_situacion_asignada_a_rol_original_aun_con_cambio_etapa(self):
        s=self.make()
        p=s.personas["C1"]
        p.etapa="Adultez";p.posicion=(5,3)
        p.examen_aprobado=True
        p.titulo=True;p.pasaporte=True
        c={"id":"J-C-01","_situation_stage":"Juventud",
           "_situation_role":"Clarisa","A":{"K":2},"B":{}}
        s._efecto(p,c,"A")
        e=[e for e in s.eventos if e.get("tipo")=="fuente"][-1]
        self.assertEqual(e["parametro"],"SIT_J_C_A_K_GANANCIA")
        self.assertEqual(e["etapa"],"Adultez")  # Estuvo en Adultez al cobrar.
        s.economia.comprobar()

    def test_pareja_movimiento_juvenil_compartido_una_sola_carta(self):
        s=self.make()
        p=s.personas["C1"];q=s.personas["L1"]
        for z in (p,q):
            z.etapa="Juventud";z.posicion=1;z.examen_aprobado=True
            z.perfil="perfil_"+z.rol
            s.economia.emitir(1,"test",z.id,"A",10,"TEST")
        s.ronda=1
        s._buscar_pareja(p)
        self.assertEqual(p.pareja,q.id)
        p.mano=[(2,4)];q.mano=[(3,5)]
        c={"id":"J-C-test","_situation_stage":"Juventud",
           "_situation_role":"Clarisa","A":{},"B":{}}
        s._elegir_opcion=lambda *args: "A"
        s._juvenil(p,c,(2,4))
        self.assertEqual(p.posicion,3)
        self.assertEqual(q.posicion,3)
        self.assertEqual(q.mano,[(3,5)])
        s.economia.comprobar()

    def test_adulto_rebote_y_prohibicion_de_inicio_saliendo(self):
        s=self.make()
        self.assertIsNone(s._simular_trayectoria((1,1),1,-1,0))
        self.assertIsNone(s._simular_trayectoria((1,1),1,0,-1))
        self.assertEqual(s._simular_trayectoria((1,1),6,1,1),(3,3))
        self.assertEqual(s._simular_trayectoria((5,3),2,-1,0),(3,3))

    def test_revelacion_y_cobro_perfil_unico_ingreso_adultez(self):
        s=self.make()
        p=s.personas["C1"]
        q=next(z for z in s.personas.values() if z.falso)
        s.ronda=3
        for z in (p,q):
            z.etapa="Juventud";z.posicion=5
            z.examen_aprobado=True;z.perfil="perfil_"+z.rol
            z.pareja=q.id if z==p else p.id
        s._volar(p)
        for z in (p,q):
            self.assertEqual(z.posicion,(5,3))
            self.assertEqual(z.etapa,"Adultez")
            self.assertTrue(z.afinidad_revelada)
            self.assertEqual(z.libre("M"),s.cfg["perfiles"][z.rol]["M"] if hasattr(s,"cfg") else self.cfg["perfiles"][z.rol]["M"])
        self.assertTrue(q.secreto_revelado)
        self.assertEqual(
            sum(e.get("tipo")=="revelacion_falso_lucas" for e in s.eventos),1
        )
        s.economia.comprobar()

    def test_compra_casa_dados_requiere_reserva_y_precio(self):
        s=self.make();s.ronda=5
        p=s.personas["C1"];q=s.personas["L1"]
        for z in (p,q):
            z.etapa="Adultez";z.posicion=(3,3)
            z.pareja=q.id if z==p else p.id
            for r,amount in (("A",15),("P",10),("M",15)):
                s.economia.emitir(5,"test",z.id,r,amount,"TEST")
            s.economia.reservar(5,z.id,"A",s.values["PAREJA_RESERVA_A"],
                                "reserva_pareja","PAREJA_RESERVA_A")
        dice=iter([6,6,1,1])
        s._lanzar=lambda:next(dice)
        s._comprar_casa(p)
        self.assertTrue(s._casa_suya(p))
        for z in (p,q):
            self.assertEqual(z.recursos["A"]["reserva_casa"],
                             s.values["CASA_RESERVA_A"])
            self.assertEqual(z.recursos["P"]["reserva_casa"],
                             s.values["CASA_RESERVA_P"])
        self.assertEqual(s.economia.total_consumido["M"],
                         2*s.values["CASA_OFERTA_BASE_M"])
        s.economia.comprobar()

    def _boda_setup(self, false):
        s=self.make();s.ronda=10
        p=s.personas["C1"]
        q=next(z for z in s.personas.values()
               if z.falso) if false else next(z for z in s.personas.values()
               if z.rol=="Lucas" and not z.falso)
        for z in (p,q):
            z.etapa="Adultez";z.posicion=(1,3)
            z.pareja=q.id if z==p else p.id
            z.titulo=True;z.pasaporte=True;z.examen_aprobado=True
            z.afinidad_revelada=True;z.zona=0
            for r in "APKM":
                s.economia.emitir(10,"test",z.id,r,25,"TEST")
            s.economia.reservar(10,z.id,"A",s.values["PAREJA_RESERVA_A"],
                                "reserva_pareja","PAREJA_RESERVA_A")
            for r in ("A","P"):
                s.economia.reservar(10,z.id,r,s.values[f"CASA_RESERVA_{r}"],
                                    "reserva_casa",f"CASA_RESERVA_{r}")
        s.propiedad_casa=frozenset((p.id,q.id))
        return s,p,q

    def test_boda_con_falso_gana_solo_clarisa(self):
        s,p,q=self._boda_setup(True)
        old=sum(z.libre(p.afinidad_recurso) for z in (p,q))
        self.assertTrue(s._puede_casarse(p))
        self.assertTrue(s._casarse(p))
        self.assertEqual(s.cierre["tipo"],"boda_falso_lucas")
        self.assertEqual(s.cierre["ganadores"],[p.id])
        self.assertTrue(s.economia.comprobar())

    def test_boda_autentica_ganan_ambos(self):
        s,p,q=self._boda_setup(False)
        self.assertTrue(s._casarse(p))
        self.assertEqual(s.cierre["tipo"],"boda_autentica")
        self.assertEqual(sorted(s.cierre["ganadores"]),sorted((p.id,q.id)))
        self.assertTrue(s.economia.comprobar())

    def test_falso_lucas_solo_gana_con_casa_y_dinero_propio(self):
        s,p,q=self._boda_setup(True)
        q.secreto_revelado=True
        s.economia.emitir(10,"test",q.id,"M",25,"TEST")
        # Activa su turno con efecto vacío y movimiento adulto real.
        c={"id":"D-L-test","_situation_stage":"Adultez",
           "_situation_role":"Lucas","A":{},"B":{}}
        s._adulto(q,c)
        self.assertEqual(s.cierre["tipo"],"falso_lucas_individual")
        self.assertEqual(s.cierre["ganadores"],[q.id])
        s.economia.comprobar()

    def test_consentimiento_experimental_falso_puede_bloquear_boda(self):
        s,p,q=self._boda_setup(True)
        s.rules["consentimiento_falso"]="rechaza"
        self.assertTrue(s._puede_casarse(p))
        self.assertFalse(s._casarse(p))
        self.assertIsNone(s.cierre)

    def test_reproducibilidad_trazas_seis_jugadores(self):
        a=self.make().jugar()
        b=self.make().jugar()
        self.assertEqual(a,b)
        self.assertIn(a["cierre"]["tipo"],
            ("censurada_sin_victoria","boda_autentica",
             "boda_falso_lucas","falso_lucas_individual"))
        self.assertTrue(any(e.get("tipo")=="situacion" for e in a["eventos"]))
        self.assertTrue(any(e.get("tipo")=="fuente" for e in a["eventos"]))
        self.assertEqual(len(a["saldos_finales"]),6)

    def test_lotes_y_frecuencias_6_y_10_jugadores(self):
        for n in (6,10):
            out=ejecutar_lote(self.cfg,partidas=3,n=n,semilla=2300)
            self.assertEqual(out["cantidad_partidas"],3)
            self.assertEqual(sum(out["cierres"].values()),3)
            self.assertEqual(len(out["partidas"]),3)
            self.assertTrue(out["activaciones_observadas"])
            self.assertTrue(out["generacion_por_etapa"])
            self.assertTrue(out["distribucion_por_etapa"])
            self.assertEqual(out["partidas_censuradas"]+
                             out["partidas_con_victoria"], 3)
            self.assertTrue(all(
                e["frecuencia_por_jugador_ronda"]>=0
                and e["activaciones_por_ronda_mesa"]>=0
                for e in out["activaciones_observadas"]
            ))
            self.assertTrue(all(
                sum(value for value in shares.values() if value is not None)
                <= 1.0000001
                for shares in out["distribucion_por_etapa"].values()
            ))
            self.assertEqual(out,ejecutar_lote(
                self.cfg,partidas=3,n=n,semilla=2300
            ))

    def test_simulacion_bot_aleatorio_sin_saldos_negativos(self):
        result=self.make(n=6,seed=2002,policy="aleatorio").jugar()
        self.assertTrue(all(
            type(amount) is int and amount>=0
            for p in result["saldos_finales"].values()
            for r in p.values() for amount in r.values()
        ))


if __name__=="__main__":
    unittest.main()
