"""Ejecutar escenario económico desde JSON: python -m laboratorio.ejecucion --escenario escenarios/...json --out resultados"""
from __future__ import annotations
import argparse,hashlib,json,pathlib,datetime,platform,sys
from simulador.economia import ScenarioConfig
from simulador.motor import run_batch,write_csv,aggregate,parse_cards

ROOT=pathlib.Path(__file__).resolve().parents[1]
CARDS=ROOT/'simulador'/'cards_v13_effects.txt'
MOTOR=ROOT/'simulador'/'motor_v13_base.py'
ADAPTER=ROOT/'simulador'/'motor.py'

def sha(path): return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()

def run(config:ScenarioConfig,out:str|pathlib.Path):
    out=pathlib.Path(out);out.mkdir(parents=True,exist_ok=True)
    cards=parse_cards(CARDS)
    rows,samples=run_batch(config.partidas,config.jugadores,config.seed,cards,
                           max_rounds=config.max_rondas,bot_mode=config.bot,
                           economia=config.economia,incremento_seed=config.incremento_seed)
    path=out/f'resultados_{config.jugadores}j.csv'
    write_csv(path,rows)
    (out/f'registro_muestra_{config.jugadores}j.json').write_text(json.dumps(samples,ensure_ascii=False,indent=2),encoding='utf-8')
    metrics=aggregate(rows)
    (out/f'resumen_{config.jugadores}j.json').write_text(json.dumps(metrics,ensure_ascii=False,indent=2),encoding='utf-8')
    manifest={'escenario':config.as_dict(),'motor_sha256':sha(MOTOR),'adaptador_sha256':sha(ADAPTER),
              'mazo_sha256':sha(CARDS),'salida_sha256':sha(path),'python':sys.version,
              'plataforma':platform.platform(),'fecha_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    (out/'manifiesto.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    return {'metricas':metrics,'csv':str(path),'sha256':manifest['salida_sha256']}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--escenario',required=True);p.add_argument('--out',required=True)
    a=p.parse_args();print(json.dumps(run(ScenarioConfig.load(a.escenario),a.out),ensure_ascii=False,indent=2))
