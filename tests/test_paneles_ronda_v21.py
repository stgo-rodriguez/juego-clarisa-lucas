"""Paneles por ronda: estados históricos e interacciones sin anticipar resultados."""
import json
from pathlib import Path
import tempfile
import unittest

from laboratorio.paneles_ronda_v21 import (
    estado_hitos, eventos_hitos_ronda, eventos_sociales_ronda,
)


def snapshot(rnd, turn, player, *, title=False, passport="None", mate="None",
             receipts=None):
    return {
        "Ronda": str(rnd), "Turno_global": str(turn), "Jugador":str(player),
        "Momento": "despues", "Titulo":str(title), "Pasaporte":passport,
        "Pareja":str(mate),
        "Comprobantes_JSON": json.dumps(receipts or []),
    }


def world(rnd, turn, *, house=None, married=None, projects=None):
    return {
        "Ronda":str(rnd),"Turno_global":str(turn),"Momento":"despues",
        "Casa_duenios":json.dumps(house), "Casamiento":json.dumps(married),
        "Proyectos_JSON":json.dumps(projects or {}),
    }


def event(seq, rnd, turn, active, stream, action, **detail):
    return {
        "Secuencia":str(seq),"Ronda":str(rnd),"Turno_global":str(turn),
        "Jugador_activo":str(active),"Fuente":stream,"Accion":action,
        "Detalle_JSON":json.dumps(detail),
    }


def fixture():
    return {
        "manifest":{"roles":{"1":"Clarisa","2":"Lucas","3":"Clarisa"}},
        "turnos.csv":[],
        "estados_jugadores.csv":[
            snapshot(1,1,1), snapshot(1,3,1),
            snapshot(1,3,2),
            snapshot(2,4,1,mate=2,receipts=[
                {"id":"Titulo-1-S1","project":"Titulo-1","subhito":1,
                 "resource":"K","amount":1}]),
            snapshot(2,4,2,mate=1),
            snapshot(2,5,1,mate=2,receipts=[
                {"id":"Titulo-1-S1","project":"Titulo-1","subhito":1,
                 "resource":"K","amount":1}]),
            snapshot(2,5,2,mate=1),
            snapshot(3,8,1,title=True,passport="Italia",mate=2),
            snapshot(3,8,2,title=True,passport="Polonia",mate=1),
        ],
        "estados_globales.csv":[
            world(1,3), world(2,4),
            world(2,5),
            world(3,8,house=[1,2],married=[1,2]),
        ],
        "eventos.csv":[
            event(1,2,4,1,"economia","invest",player=1,project="Titulo-1",
                  receipt="Titulo-1-S1"),
            event(2,2,4,1,"observador","noviazgo_propuesta",player=1,target=2),
            event(3,2,4,1,"observador","noviazgo_resultado",
                  player=1,target=2,accepted=True),
            event(4,2,4,1,"economia","pair",players=[1,2]),
            event(5,2,5,2,"economia","transfer",source=1,dest=2,resource="K",amount=2),
            event(6,2,5,2,"economia","transfer",source=3,dest=2,resource="M",amount=1),
            event(7,2,5,2,"duelo","duel",challenger=2,defender=3,
                  kind="ordinario",result="victoria",paid_resource="M",
                  paid=1),
            event(8,2,5,2,"economia","house_attempt",dice_buyers=5,
                  dice_owners_or_bank=8,price_per_player=15,won=False),
            event(9,3,8,1,"economia","house_bought",owners=[1,2],prior=None),
            event(10,3,8,1,"economia","married",players=[1,2]),
        ],
    }


class PanelesRondaTests(unittest.TestCase):
    def test_estados_historicos_sin_filtrar_futuro(self):
        game=fixture()
        earlier=estado_hitos(game,1,1)
        self.assertEqual([x["estado"] for x in earlier["hitos"]],
                         ["Pendiente","Pendiente","Pendiente","Pendiente"])
        mid=estado_hitos(game,2,1)
        self.assertEqual(mid["hitos"][0]["estado"],"En progreso")
        self.assertEqual(mid["hitos"][0]["detalle"],"1 comprobante(s) propio(s)")
        self.assertEqual(len(mid["comprobantes"]),1)
        self.assertEqual(mid["hitos"][2]["estado"],"Pendiente")
        end=estado_hitos(game,3,1)
        self.assertEqual([x["estado"] for x in end["hitos"]],
                         ["Logrado","Logrado","Lograda","Logrado"])
        self.assertEqual(end["hitos"][1]["detalle"],"Italia")

    def test_pasaporte_propio_y_sin_estado(self):
        g=fixture()
        g["estados_jugadores.csv"].append(snapshot(2,5,3,receipts=[
            {"id":"Polonia-3-S1","project":"Polonia-3","subhito":1,"amount":2}]))
        self.assertEqual(estado_hitos(g,2,3)["hitos"][1]["estado"],"Pendiente")
        self.assertFalse(estado_hitos(g,4,1)["disponible"])
        self.assertEqual(estado_hitos(g,4,1)["hitos"][0]["estado"],"Sin datos")

    def test_inversion_y_casa_en_pareja_solo_en_ronda(self):
        game=fixture()
        e1=eventos_hitos_ronda(game,1,1)
        self.assertEqual(e1,[])
        steps=eventos_hitos_ronda(game,2,1)
        self.assertEqual([e["titulo"] for e in steps],
                         ["Título · Subhito 1","Intento de Casa"])
        self.assertIn("1 de Conocimiento",steps[0]["descripcion"])
        self.assertEqual(steps[1]["estado"],"Intento fallido")
        self.assertEqual(steps[1]["participacion"],"en pareja")
        mate=eventos_hitos_ronda(game,2,2)
        self.assertEqual([e["titulo"] for e in mate],["Intento de Casa"])
        success=eventos_hitos_ronda(game,3,2)
        self.assertEqual([e["titulo"] for e in success],["Casa","Casamiento"])
        self.assertEqual([e["estado"] for e in success],["Conseguida","Ganaron"])

    def test_propuesta_agrupada_y_resultado_por_participante(self):
        game=fixture()
        a=eventos_sociales_ronda(game,2,1)
        b=eventos_sociales_ronda(game,2,2)
        self.assertEqual([x["titulo"] for x in a],
                         ["Propuesta de noviazgo","Transferencia"])
        self.assertEqual([x["titulo"] for x in b],
                         ["Propuesta de noviazgo","Transferencia","Duelo"])
        self.assertEqual(a[0]["estado"],"Aceptada")
        self.assertEqual(a[0]["participacion"],"realizada")
        self.assertEqual(b[0]["participacion"],"recibida")
        self.assertEqual(b[-1]["estado"],"Ganó")
        self.assertEqual(b[-1]["participacion"],"realizado")
        self.assertNotIn("Pareja formada",[x["titulo"] for x in a])

    def test_duelo_recibido_perdido_no_duplica_transferencia(self):
        game=fixture()
        seen=eventos_sociales_ronda(game,2,3)
        self.assertEqual(len(seen),1)
        self.assertEqual(seen[0]["titulo"],"Duelo")
        self.assertEqual(seen[0]["estado"],"Perdió")
        self.assertEqual(seen[0]["participacion"],"recibido")

    def test_propuesta_no_concretada_y_sin_resultado(self):
        game=fixture()
        game["eventos.csv"]=[
            event(1,2,4,1,"observador","noviazgo_propuesta",player=1,target=2),
            event(2,2,4,1,"observador","noviazgo_resultado",
                  player=1,target=2,accepted=False),
        ]
        self.assertEqual(eventos_sociales_ronda(game,2,1)[0]["estado"],"No concretada")
        game["eventos.csv"].pop()
        self.assertEqual(eventos_sociales_ronda(game,2,2)[0]["estado"],"Sin resolución")

    def test_falta_snapshot_global_no_inventa_casa(self):
        game=fixture()
        game["estados_globales.csv"]=[]
        state=estado_hitos(game,2,1)
        self.assertEqual(state["hitos"][2]["estado"],"Sin datos")
        self.assertEqual(state["hitos"][0]["estado"],"En progreso")

    def test_integracion_real_simlog(self):
        from laboratorio.simular_mazos_vigentes_v2 import run_game
        from laboratorio.simlog_viewer_v21 import load_game
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/"traza"
            run_game(6,1,round_limit=6,trace_dir=folder)
            g=load_game(folder,str(folder.resolve()))
            self.assertTrue(g.get("estados_globales.csv"))
            for rnd in range(1,7):
                for player in (1,4):
                    with self.subTest(rnd=rnd,player=player):
                        data=estado_hitos(g,rnd,player)
                        self.assertTrue(data["disponible"])
                        self.assertEqual(len(data["hitos"]),4)
                        advances=eventos_hitos_ronda(g,rnd,player)
                        social=eventos_sociales_ronda(g,rnd,player)
                        self.assertTrue(all(0 < x["secuencia"] for x in advances+social))


if __name__ == "__main__":
    unittest.main()
