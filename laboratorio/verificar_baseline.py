"""Comprobar integridad y (opcionalmente) reproducir íntegramente la línea base v1.3.

Uso desde la raíz del repositorio:
  python -m laboratorio.verificar_baseline
  python -m laboratorio.verificar_baseline --full
"""
from __future__ import annotations
import argparse,csv,gzip,hashlib,io,pathlib,tempfile,json
from simulador.economia import ScenarioConfig
from laboratorio.ejecucion import ROOT,run

REFERENCE_HASHES={
 6:'820168f1c8006ec2f143e44098cca0b6cac67a55a28ecc63423d2747451c5059',
 10:'4442427c133e590be062cfdde61163afcaac719bbc27e3dc7aad95f673ee00f8',
}

def verify(full=False):
    results={}
    for players,expected in REFERENCE_HASHES.items():
        gz=ROOT/'referencias'/f'resultados_{players}j.csv.gz'
        original=gzip.decompress(gz.read_bytes())
        actual_hash=hashlib.sha256(original).hexdigest()
        if actual_hash!=expected:raise AssertionError(f'CSV histórico corrupto: {players} jugadores')
        with io.TextIOWrapper(io.BytesIO(original),encoding='utf-8-sig',newline='') as f:
            entries=list(csv.DictReader(f))
        conf=ScenarioConfig.load(ROOT/'escenarios'/f'base_v13_{players}j.json')
        assert len(entries)==conf.partidas==1000
        assert all(int(row['semilla'])==conf.seed+i*conf.incremento_seed for i,row in enumerate(entries))
        assert all(int(row['jugadores'])==players and int(row['errores'])==0 for row in entries)
        item={'jugadores':players,'partidas':len(entries),'referencia_sha256':actual_hash,
              'reproduccion_ejecutada':bool(full)}
        if full:
            with tempfile.TemporaryDirectory() as tmp:
                result=run(conf,tmp)
                reproduced=pathlib.Path(result['csv']).read_bytes()
                if reproduced!=original:
                    raise AssertionError(f'La reproducción NO coincide con referencia {players}j')
                item['reproduccion_sha256']=hashlib.sha256(reproduced).hexdigest()
                item['binariamente_identicos']=True
        results[str(players)]=item
    return results

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--full',action='store_true')
    args=parser.parse_args();print(json.dumps(verify(full=args.full),ensure_ascii=False,indent=2))
