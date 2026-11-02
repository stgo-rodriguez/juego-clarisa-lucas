"""Auditoría tabular de las seis barajas de prueba SIN APROBACIÓN normativa."""
from __future__ import annotations
import argparse,csv,json
from collections import Counter
from pathlib import Path
from simulador.mazos_propuestos_v2 import build_decks, load_catalog
from simulador.turnos_v2 import Stage


def audit_cards(catalog):
    decks=build_decks(catalog,42)
    rows=[]
    for (stage,role),pool in decks.items():
        for card in sorted(pool._deck,key=lambda c:c.id):
            p=card.payload
            if p['origin']=='historical_copy':
                options=p['effects']
                sums={label:sum(max(0,n) for n in changes.values()) for label,changes in options.items()}
                negatives={label:sum(max(0,-n) for n in changes.values()) for label,changes in options.items()}
                row={'card_id':card.id,'stage':stage.value,'role':role,
                     'title':p['title'],'family':'Histórica (no adaptada)',
                     'type':'historical_ab','source_card':p['source_id'],
                     'source_collection':'situaciones_historicas_v0.1',
                     'approval':'NO_APROBADA_v2','a_gain_total':sums['A'],'a_loss_total':negatives['A'],
                     'b_gain_total':sums['B'],'b_loss_total':negatives['B'],
                     'auction_benefit':0,'auction_currency':'','mandatory':''}
            else:
                mechanic=p['mechanics'];kind=mechanic['type']
                auction=mechanic if kind=='auction' else {}
                total=sum(auction.get('benefit',{}).values())
                currency=auction.get('bid',', '.join(auction.get('bid_choice',auction.get('bid_any',[]))))
                row={'card_id':card.id,'stage':stage.value,'role':role,
                     'title':p['title'],'family':p['family'],'type':kind,'source_card':p['source_id'],
                     'source_collection':'adultez_multiverso_v0.2',
                     'approval':'PROPUESTA_NO_APROBADA',
                     'a_gain_total':'','a_loss_total':'','b_gain_total':'','b_loss_total':'',
                     'auction_benefit':total,'auction_currency':currency,'mandatory':auction.get('mandatory','')}
            rows.append(row)
    if len(rows)!=126:raise ValueError('Catálogo físico debe tener 126 cartas de prueba')
    return rows


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',type=Path,default=Path('resultados/fase10'))
    options=parser.parse_args();options.out.mkdir(parents=True,exist_ok=True)
    rows=audit_cards(load_catalog())
    with (options.out/'auditoria_126_cartas.csv').open('w',newline='',encoding='utf8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    result={'total':len(rows),'por_mazo':{f'{s}/{r}':sum(x['stage']==s and x['role']==r for x in rows)
            for s in ('Infancia','Juventud','Adultez') for r in ('Clarisa','Lucas')},
            'familia_adulta':dict(Counter(x['family'] for x in rows if x['stage']=='Adultez')),
            'maquina_de_estados':'PROPUESTAS_NO_APROBADAS'}
    (options.out/'auditoria_mazos_resumen.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()