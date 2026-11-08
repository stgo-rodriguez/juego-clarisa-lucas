"""Validar y publicar una copia compacta de la corrida SIMLOG v2.1 archivada.

No ejecuta reglas ni el motor del juego. Entrada: artifact expandido por
actions/download-artifact. Salida: docs/datos_v21_ultima (200 partidas).
"""
from __future__ import annotations
import argparse
import csv
import gzip
import hashlib
import json
import statistics
from pathlib import Path
from collections import Counter

ACTIONS = {"invest","adjudicate","pair","utn_exam","utn_profile_awarded",
           "utn_to_youth","enter_dublin","dublin_to_adult","house_bought",
           "house_attempt","married","duel","situation_revealed","enter_utn","land_dublin"}

def rows(path):
    with path.open(encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))

def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))

def integer(value):
    return int(value) if value not in (None,"") else None

def boolean(value):
    return str(value).lower()=="true" if value not in (None,"") else None

def build(source:Path,out:Path):
    resumen=read_json(source/"resumen.json")
    audit=read_json(source/"auditoria_economica.json")
    games_raw=rows(source/"partidas.csv")
    assert resumen["total_games"]==len(games_raw)==200
    assert resumen["total_marriages"]==200
    games=[]
    details={}
    total=0
    for raw in games_raw:
        size,seed=int(raw["size"]),int(raw["seed"])
        path=source/"trazas"/f"n{size}_s{seed}"
        manifest=read_json(path/"manifest.json")
        assert manifest["validation"]=="PASS"
        assert (manifest["player_count"],manifest["seed"])==(size,seed)
        for filename,digest in manifest["file_sha256"].items():
            assert hashlib.sha256((path/filename).read_bytes()).hexdigest()==digest, filename
        g=dict(size=size,seed=seed,rounds=integer(raw["rounds"]),
               turns=integer(raw["turns"]),won=boolean(raw["won"]),
               pair=json.loads(raw["winning_pair"]),zone=raw["winning_zone"],
               a=integer(raw["choices_A"]),b=integer(raw["choices_B"]),
               duels=integer(raw["duels"]),deck_sha256=raw["shuffled_decks_sha256"])
        assert g["won"]
        games.append(g)
        total+=g["a"]+g["b"]
        turns=[]
        for t in rows(path/"turnos.csv"):
            turns.append(dict(r=integer(t["Ronda"]),t=integer(t["Turno_global"]),
                  j=integer(t["Jugador"]),rol=t["Rol"],
                  etapa=t["Etapa_situacion"] or t["Etapa_antes"],
                  carta=t["Carta_ID"],op=t["Desenlace_elegido"],
                  afin_antes=integer(t["Afinidad_posicion_antes"]),
                  afin_desp=integer(t["Afinidad_posicion_despues"]),
                  zona=t["Afinidad_zona_despues"],
                  compatible=boolean(t["Pareja_compatible_despues"]),
                  a=integer(t["A_despues"]),p=integer(t["P_despues"]),
                  k=integer(t["K_despues"]),m=integer(t["M_despues"])))
        assert len(turns)==g["turns"]
        assert (sum(x["op"]=="A" for x in turns),
                sum(x["op"]=="B" for x in turns))==(g["a"],g["b"])
        resources=[dict(r=integer(t["Ronda"]),a=integer(t["A_libre_total"]),
                        p=integer(t["P_libre_total"]),k=integer(t["K_libre_total"]),
                        m=integer(t["M_libre_total"]))
                   for t in rows(path/"recursos_por_ronda.csv")]
        events=[dict(r=integer(e["Ronda"]),t=integer(e["Turno_global"]),
                     j=integer(e["Jugador_activo"]),action=e["Accion"],
                     detail=json.loads(e["Detalle_JSON"]))
                for e in rows(path/"eventos.csv") if e["Accion"] in ACTIONS]
        details[f"{size}-{seed}"]=dict(turns=turns,resources=resources,events=events)
    assert Counter(x["size"] for x in games)=={6:100,10:100}
    assert {(x["size"],x["seed"]) for x in games}=={
        (size,seed) for size in (6,10) for seed in range(101,201)}
    assert total==resumen["total_decisions"]==28708
    for row in resumen["summary"]:
        durations=[x["rounds"] for x in games if x["size"]==row["size"]]
        assert round(statistics.mean(durations),2)==row["avg_rounds_censored"]
        assert statistics.median(durations)==row["median_rounds_censored"]
    out.mkdir(parents=True,exist_ok=True)
    meta={"source":{"workflow_run_id":42454007039,"artifact_id":13606319833,
       "commit_sha":"29c7ec51fdf4144885e3ad3bf9ad995901445810",
       "validation":"200 manifests PASS; all manifest SHA-256 verified",
       "snapshot_kind":"read_only"},
       "summary":resumen,"audit":audit,"games":games,
       "preferences_stage_role":rows(source/"preferencias_por_etapa_rol.csv"),
       "preferences_cards":rows(source/"preferencias_por_carta.csv")}
    (out/"resumen.json").write_text(json.dumps(meta,ensure_ascii=False,
        separators=(",",":"))+"\n",encoding="utf-8")
    for size in (6,10):
        for first in (101,151):
            group={f"{size}-{seed}":details[f"{size}-{seed}"]
                   for seed in range(first,first+50)}
            filename=out/f"detalle_{size}j_{first}_{first+49}.json.gz"
            with gzip.open(filename,"wt",encoding="utf-8",compresslevel=9) as stream:
                json.dump({"schema":"SIMLOG v2.1 compact","by_game":group},stream,
                          ensure_ascii=False,separators=(",",":"))
    print(f"PASS: {len(games)} partidas, {total} decisiones, 200 manifiestos y hashes verificados")

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--source",type=Path,required=True)
    parser.add_argument("--out",type=Path,default=Path("docs/datos_v21_ultima"))
    args=parser.parse_args()
    build(args.source,args.out)
