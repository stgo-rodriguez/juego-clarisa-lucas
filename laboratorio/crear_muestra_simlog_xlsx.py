"""Presentación consultable de una partida SIMLOG v2.0 (los CSV conservan el detalle completo)."""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
from artifact_tool import Workbook, SpreadsheetFile

PREVIEW_COLUMNS={
'Turnos':['Ronda','Turno_global','Jugador','Rol','Etapa_antes','Pos_antes','Carta_ID','Situacion',
          'Desenlace_elegido','Resultado_situacion','Carta_Movimiento','Desenlace_movimiento',
          'Direccion','Distancia_movimiento','Ruta_JSON','Casillero_resuelto','Etapa_despues','Pos_despues',
          'A_libre_antes','P_libre_antes','K_libre_antes','M_libre_antes',
          'A_libre_despues','P_libre_despues','K_libre_despues','M_libre_despues',
          'Pareja_antes','Pareja_despues','Res_pareja_A','Res_casa_A','Res_casa_P',
          'Titulo','Pasaporte','Casa','Casamiento','Eventos_cantidad'],
'Eventos':['Secuencia','Ronda','Turno_global','Jugador_activo','Fuente','Accion','Jugador_afectado','Detalle_JSON'],
'Estados':['Ronda','Turno_global','Momento','Jugador','Rol','Etapa','Posicion','Pareja',
           'A_libre','P_libre','K_libre','M_libre','Res_pareja_A','Res_casa_A','Res_casa_P',
           'Titulo','Pasaporte','Perfil_ID','Mano_adulta_JSON','Comprobantes_JSON'],
'Global':['Ronda','Turno_global','Momento','Casa_duenios','Casamiento','Proyectos_JSON',
          'A_emitido','A_consumido','A_invertido','P_emitido','P_consumido','P_invertido',
          'K_emitido','K_consumido','K_invertido','M_emitido','M_consumido','M_invertido'],
'Hitos':None,
'Preferencias Sit.':None,
'Preferencias Mov.':None,
'Recursos Ronda':None,
}
FILES={'Turnos':'turnos.csv','Eventos':'eventos.csv','Estados':'estados_jugadores.csv',
       'Global':'estados_globales.csv','Hitos':'hitos.csv',
       'Preferencias Sit.':'preferencias_situaciones.csv',
       'Preferencias Mov.':'preferencias_movimientos.csv','Recursos Ronda':'recursos_por_ronda.csv'}


def load_rows(path):
    with path.open(encoding='utf-8-sig',newline='') as file:
        reader=csv.DictReader(file)
        return reader.fieldnames,list(reader)


def create_xlsx(folder:Path,destination:Path):
    data=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    wb=Workbook.create()
    summary=wb.worksheets.add('Resumen')
    summary.get_range('A1:D1').merge()
    summary.get_range('A1').values=[['SIMLOG v2.0 · Traza detallada de una partida']]
    summary.get_range('A1:D1').format={'fill':'#163F57','font':{'bold':True,'color':'#FFFFFF'},'row_height':35}
    kv=[('Versión',data['schema']),('ID de partida',data['run_id']),('Semilla',data['seed']),
        ('Participantes',data['player_count']),('Agente',data['policy']),
        ('Competencia',str(data['competition'])),('Estado final',data['status']),
        ('Rondas',data['summary']['rounds']),('Turnos',data['summary']['turns_executed']),
        ('Eventos',data['counts']['eventos.csv']),('Fuente','Mazos históricos/propuestos NO APROBADOS'),
        ('Advertencia','Las afinidades del perfil actuales son heredadas; no el eje A–Neutro–B'),
        ('Granularidad','Cada turno + estados antes/después de TODOS los jugadores'),
        ('Separación A/B','Situación y Movimiento se registran por separado'),
        ('Integridad',data['validation'])]
    summary.get_range_by_indexes(2,0,len(kv),2).values=[[k,v] for k,v in kv]
    summary.get_range('A3:A17').format={'fill':'#E8F2F7','font':{'bold':True},'column_width':30}
    summary.get_range('B3:B17').format.column_width=60
    summary.get_range('A20:D20').merge()
    summary.get_range('A20').values=[['Consultá Turnos, Eventos, Estados y preferencias A/B en las solapas. Los CSV anexos contienen todos los campos originales.']]
    summary.get_range('A20:D20').format={'fill':'#E8F2F7','row_height':32}
    for tab,filename in FILES.items():
        headers,records=load_rows(folder/filename)
        wanted=PREVIEW_COLUMNS[tab] or headers
        sheet=wb.worksheets.add(tab)
        data_rows=[[h for h in wanted]]
        for row in records:
            values=[]
            for col in wanted:
                v=row.get(col,'')
                if v=='' or v is None:v=None
                elif isinstance(v,str) and v in ('True','False'):v=(v=='True')
                elif col in ('Ronda','Turno_global','Jugador','Jugador_activo','Jugador_afectado',
                              'Secuencia','Dado','Eventos_cantidad','Veces_resuelta','Elecciones_A',
                              'Elecciones_B','Otras_resoluciones','Partidas_con_carta') or col.endswith(('_libre','_antes','_despues','_emitido','_consumido','_invertido')):
                    try:v=int(v)
                    except ValueError:pass
                if isinstance(v,str) and v[:1] in ('=','+','-','@'):v="'"+v
                values.append(v)
            data_rows.append(values)
        # bloques para no crear una sola asignación gigante en el motor remoto
        block=350
        for i in range(0,len(data_rows),block):
            chunk=data_rows[i:i+block]
            sheet.get_range_by_indexes(i,0,len(chunk),len(wanted)).values=chunk
        sheet.get_range_by_indexes(0,0,1,len(wanted)).format={
            'fill':'#163F57','font':{'bold':True,'color':'#FFFFFF'},
            'row_height':31,'vertical_alignment':'center'}
        sheet.get_range_by_indexes(0,0,len(data_rows),len(wanted)).format.column_width=18
        for j,h in enumerate(wanted):
            if h in ('Situacion','Detalle_JSON','Proyectos_JSON','Eventos','Ruta_JSON','Mano_adulta_JSON','Comprobantes_JSON'):
                sheet.get_range_by_indexes(0,j,len(data_rows),1).format.column_width=44
        sheet.freeze_panes.freeze_rows(1)
    destination.parent.mkdir(parents=True,exist_ok=True)
    SpreadsheetFile.export_xlsx(wb).save(str(destination))
    check=wb.inspect({'kind':'table','range':'Resumen!A1:B8','include':'values',
                      'table_max_rows':8,'table_max_cols':2})
    print(check.ndjson[:1200])
    return destination


def main():
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('--partida',type=Path,required=True)
    a.add_argument('--out',type=Path,required=True)
    args=a.parse_args()
    print(create_xlsx(args.partida,args.out))


if __name__=='__main__':main()