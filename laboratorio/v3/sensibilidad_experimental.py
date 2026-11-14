"""Experimentos apareados de sensibilidad del simulador experimental v3.0.

Compara configuraciones con EXACTAMENTE las mismas semillas, cantidad de
jugadores y política de agentes. Frecuencias reestimadas para cada cambio.

NO extrapola a reglas definitivas ni utiliza el modelo de optimización
como si sus hipótesis fueran estadísticas observadas.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from laboratorio.v3.catalogo import cargar_matriz, validar_ajustes
from laboratorio.v3.simulador_experimental import (
    EJEMPLO, ejecutar_lote, validar_config,
)


def comparar(config: dict, variantes: list[dict], *,
             jugadores=6, partidas=20, semilla=2001,
             politica="planificador") -> dict:
    validar_config(config)
    if not isinstance(variantes,list) or not variantes:
        raise ValueError("Se requieren escenarios de sensibilidad")
    baseline=ejecutar_lote(config,partidas,jugadores,semilla,politica)
    base_frequencies={
        (x["etapa"],x["parametro"],x["recurso"]):x
        for x in baseline["activaciones_observadas"]
    }
    used=set()
    experiments=[]
    for case in variantes:
        name=case.get("id")
        if not isinstance(name,str) or not name or name in used:
            raise ValueError("Variante repetida o sin identificador")
        used.add(name)
        changes=validar_ajustes(cargar_matriz(), case.get("cambios",{}))
        if not changes:
            raise ValueError("La variante debe cambiar al menos un parámetro")
        for key,new in changes.items():
            if key not in config["parametros"]:
                raise ValueError("No agregar parámetros sin regla: "+key)
            if config["parametros"][key]==new:
                raise ValueError("Cambio sin efecto: "+key)
        modified=copy.deepcopy(config)
        modified["parametros"].update(changes)
        report=ejecutar_lote(modified,partidas,jugadores,semilla,politica)
        freqs={
            (x["etapa"],x["parametro"],x["recurso"]):x
            for x in report["activaciones_observadas"]
        }
        relative=[]
        for key in sorted(set(freqs)|set(base_frequencies)):
            a=base_frequencies.get(key)
            b=freqs.get(key)
            av=a["frecuencia_por_jugador_ronda"] if a else 0.0
            bv=b["frecuencia_por_jugador_ronda"] if b else 0.0
            if abs(av-bv)>1e-12:
                relative.append({
                    "etapa":key[0],"parametro":key[1],"recurso":key[2],
                    "base_frecuencia_por_jugador_ronda":av,
                    "variante_frecuencia_por_jugador_ronda":bv,
                    "variacion_absoluta":bv-av,
                })
        paired_changes=[
            {
                "semilla":base["semilla"],
                "rondas_base":base["rondas"],
                "rondas_variante":alt["rondas"],
                "delta_rondas":alt["rondas"]-base["rondas"],
                "cierre_base":base["cierre"]["tipo"],
                "cierre_variante":alt["cierre"]["tipo"],
            }
            for base,alt in zip(baseline["partidas"],report["partidas"])
        ]
        experiments.append({
            "id":name, "cambios":changes,
            "cierres":report["cierres"],
            "censuradas":report["partidas_censuradas"],
            "mediana_cierres":report["rondas_mediana_completadas"],
            "p80_cierres":report["rondas_p80_completadas"],
            "delta_rondas_medio_pareado_observado":(
                sum(x["delta_rondas"] for x in paired_changes)/partidas
            ),
            "frecuencias_que_cambiaron":relative,
            "activaciones_distintas":len(report["activaciones_observadas"]),
            "comparaciones_pareadas":paired_changes,
        })
    return {
        "estado":"SENSIBILIDAD_EXP_NO_CALIBRADA",
        "jugadores":jugadores,"partidas":partidas,
        "semillas":[semilla,semilla+partidas-1],
        "politica":politica,
        "base":{
            "cierres":baseline["cierres"],
            "censuradas":baseline["partidas_censuradas"],
            "mediana_cierres":baseline["rondas_mediana_completadas"],
            "p80_cierres":baseline["rondas_p80_completadas"],
            "activaciones_distintas":len(baseline["activaciones_observadas"]),
        },
        "experimentos":experiments,
        "advertencia":"Comparación con semillas idénticas de un simulador incompleto, "
                      "cartas/valores sintéticos y bots experimentales; "
                      "variar el recurso puede cambiar decisiones y frecuencias. "
                      "Los cierres censurados no se tratan como victorias.",
    }


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config",type=Path,default=EJEMPLO)
    ap.add_argument("--variantes",type=Path,default=Path(__file__).with_name(
        "sensibilidad_v3_NO_CALIBRADA.json"))
    ap.add_argument("--jugadores",type=int,choices=(6,10),default=6)
    ap.add_argument("--partidas",type=int,default=20)
    ap.add_argument("--semilla",type=int,default=2001)
    ap.add_argument("--politica",choices=("planificador","aleatorio"),
                    default="planificador")
    ap.add_argument("--salida",type=Path)
    args=ap.parse_args(argv)
    data=json.loads(args.config.read_text(encoding="utf-8"))
    scenarios=json.loads(args.variantes.read_text(encoding="utf-8"))
    result=comparar(data,scenarios["variantes"],jugadores=args.jugadores,
                    partidas=args.partidas,semilla=args.semilla,
                    politica=args.politica)
    text=json.dumps(result,ensure_ascii=False,indent=2)+"\n"
    if args.salida:
        args.salida.parent.mkdir(parents=True,exist_ok=True)
        args.salida.write_text(text,encoding="utf-8")
        print(args.salida)
    else:print(text)


if __name__=="__main__":
    main()
