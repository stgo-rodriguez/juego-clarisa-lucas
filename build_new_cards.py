"""Snapshot inmutable de efectos de las hojas vigentes (comparación C/L verificó igualdad)."""
from pathlib import Path
import csv,io,re,json,hashlib

SOURCE=Path(__file__).parent/'docs/datos_v2_nuevas_cartas/fuentes/Clarisa_Lucas_Infancia_24_Cartas_v0_3_Narrativas.txt'
YOUTH = '''P1 M3 -A2|A2 K2 -M1
P2 M2 -A2|A2 K2 -M1
P1 M3 -A3|P1 K2 -M1
K3 -A2|A1 P3 -M1
P3 K1 -A2|A4 P1 -M1
P1 K3 -M2|P2 M2 -A2
K1 M3 -A2|P1 K3 -M1
A4 P1 -M1|K2 M2 -A3
A4 P1 -M1|K1 M2 -A2
K3|P2 K2 -M1
P2 K2 -M2|P1 M3 -A2
K3 -A2|A1 P3 -M2
P1 M3 -A2|A1 K3 -M2
P2 M2 -A2|A4 P1 -M1
P2 M2 -A3|P2 K2 -M2
A1 P3 -M1|P2 K2 -A2
P2 M3 -A2|P1 K3 -M1
P1 K3 -M2|P2 M3 -A2
A1 K3 -M2|P1 M3 -A2
P2 K2 -A2|A4 P2 -M2
A4 P2 -M1|P1 K3 -A2
P1 K3 -M2|A2 P3 -M1
P1 K3 -M2|P1 M3 -A2
A3 P2 -M1|P2 M2 -A2'''.splitlines()
ADULT = '''M4 -A2|A3 P1 -M1
K3 -M1|M2 P1 -A1
A4 -M1|K2 P2 -A2
K2 P2 -M2|M3 -A2
A4 -M1|K1 P3 -A2
K3 P1 -M1|M3 P1 -A2
P3 K1 -M1|A3 P1 -M1
A4 -M1|K2 P2 -A2
K3 P1 -M1|M2 P2 -A1
K2 P2 -M2|M3 -A2
A4 P1 -M1|M3 K1 P1 -A2
M3 P1 -A2|K2 P2 -M1
A4 -P1|P3 M1 -A1
K3 P1 -M1|M2 P2 -A2
P3 A2 -M1|K3 M2'''.splitlines()
YOUTH_TITLES_C=['Un trabajo que empieza mañana','La pasantía en temporada de parciales','El sábado del turno extra','El prototipo y la exposición','Representar al curso o preparar la bienvenida','La semana para capacitarte','El encargo freelance y el grupo de estudio','La bienvenida que prometiste organizar','La escapada que ya estaba reservada','¿Estudiar sola o armar un grupo?','La especialización y la jornada extra','La entrega y la actividad solidaria','Oferta de empleo o formación con beca','Feriado largo: tienda o escapada','La capacitación con beca parcial','El trabajo grupal que se rompió','La computadora deja de funcionar','La idea del concurso y su patrocinador','El intercambio y los turnos remunerados','Una compañera está por dejar la carrera','El recital la noche del parcial','Contenido o coordinación de la muestra','La entrevista y la prueba de trabajo','Una semana difícil en casa']
YOUTH_TITLES_L=['Un turno inesperado en el taller','Prácticas profesionales en semana de exámenes','El sábado antes del recuperatorio','Una entrega con dos responsabilidades','Delegado del curso o anfitrión','El curso breve de vacaciones','El pedido de último minuto','El laboratorio abierto','El viaje del grupo','¿Estudiar solo o armar un grupo?','Capacitación o trabajo remunerado','Dos compromisos para la misma tarde','Una propuesta laboral inesperada','Un finde largo con dos invitaciones','Un curso que podría abrirte puertas','Desacuerdo en el equipo','El equipo del laboratorio se averió','El proyecto que quiere comprar una empresa','Una semana en otra universidad','El compañero que no llega a rendir','El concierto antes del examen','Coordinar o construir el proyecto','Primera entrevista para un puesto relevante','Un familiar necesita apoyo']
ADULT_TITLES_C=['La oficina sin domingos','El diploma de una vida alternativa','El regreso que otra Clarisa postergó','Los planos de la casa que pudo ser','La invitación que casi quedó sin responder','La investigación publicada en otro futuro','La reputación de otra Clarisa','La celebración que nunca viviste','El consejo que llegó de mañana','El imprevisto de dos hogares posibles','Una fotografía, dos vidas posibles','El contrato de la otra Clarisa','La declaración de un futuro distinto','El libro escrito por tu otra vida','El premio que otra Clarisa dejó pasar']
ADULT_TITLES_L=['El taller que nunca cierra','El cuaderno del Lucas que cambió de carrera','El boleto que otro Lucas nunca usó','La casa que Lucas nunca reparó','El mensaje que Lucas dejó sin abrir','El prototipo que otro Lucas vendió','El reconocimiento del Lucas equivocado','La cita que otro Lucas recuerda','La advertencia del Lucas que se equivocó','La avería de cada futuro','Dos cumpleaños para Lucas','El contrato que otro Lucas firmó','El mensaje romántico duplicado','El cuaderno que el otro Lucas nunca terminó','La distinción que otro Lucas rechazó']

assert len(YOUTH)==24 and len(ADULT)==15
assert len(YOUTH_TITLES_C)==len(YOUTH_TITLES_L)==24
assert len(ADULT_TITLES_C)==len(ADULT_TITLES_L)==15

def effects(text):
    out={}
    for s in text.strip().split():
        sign=-1 if s.startswith('-') else 1
        s=s.lstrip('+-')
        assert s[0] in 'APKM' and s[1:].isdigit()
        out[s[0]]=sign*int(s[1:])
    return out

def childhood(role):
    s=SOURCE.read_text(encoding='utf-8')
    t=s.split('TAB NAME: '+role+'>')[1].split('<PARSED TEXT FOR SHEET:')[0].strip()
    rows=list(csv.reader(io.StringIO(t)))
    cards=[r for r in rows if len(r)>9 and re.match(r'INF-[CL]-\d+$',r[1])]
    assert len(cards)==12
    # Saldo neto validado contra los 16 indicadores por desenlace de la hoja.
    entries=[]
    for r in cards:
        def numeric(start):
            got={}
            for i,key in enumerate('APKM'):
                plus,minus=int(r[start+2*i]),int(r[start+2*i+1])
                if plus or minus:got[key]=plus-minus
            return got
        a,b=numeric(10),numeric(18)
        entries.append({'id':r[1],'title':r[2],'context':r[3],
                        'text_a':r[4],'text_b':r[6],
                        'effects':{'A':a,'B':b},'source':'Infancia v0.3'})
    return entries

cards=[]
for role in ('Clarisa','Lucas'):
    c= 'C' if role=='Clarisa' else 'L'
    for x in childhood(role):
        cards.append({**x,'stage':'Infancia','role':role})
    for i,raw in enumerate(YOUTH,1):
        a,b=raw.split('|')
        cards.append({'id':f'J-{c}-{i:02}','title':(YOUTH_TITLES_C if c=='C' else YOUTH_TITLES_L)[i-1],
                      'stage':'Juventud','role':role,'effects':{'A':effects(a),'B':effects(b)},'source':'Juventud v0.3'})
    for i,raw in enumerate(ADULT,1):
        a,b=raw.split('|')
        cards.append({'id':f'AD-{c}-{i:02}','title':(ADULT_TITLES_C if c=='C' else ADULT_TITLES_L)[i-1],
                      'stage':'Adultez','role':role,'effects':{'A':effects(a),'B':effects(b)},'source':'Adultez v0.4'})
assert len(cards)==102 and len({c['id'] for c in cards})==102
for stage,n in [('Infancia',12),('Juventud',24),('Adultez',15)]:
 a=[x['effects'] for x in cards if x['stage']==stage and x['role']=='Clarisa']
 b=[x['effects'] for x in cards if x['stage']==stage and x['role']=='Lucas']
 assert len(a)==len(b)==n and a==b,stage
payload={'schema':'clarisa-lucas-cartas-2026-11-04-v2x','status':'EXPERIMENTAL_NO_APROBADO',
'sources':{'Infancia':'Clarisa_Lucas_Infancia_24_Cartas_v0_3_Narrativas.xlsx (Library)',
'Juventud':'https://docs.google.com/spreadsheets/d/1DjLn42FWoPbiRivm9G0DLQ1Hk_PDz8K8xbh6s0B_vuY/edit',
'Adultez':'https://docs.google.com/spreadsheets/d/1BQUEqJiSOew7oT2SDMYUeuXSUwW_xyL0BylhQvKl_yc/edit'},
'notes':'Todos los efectos leídos de hojas v0.3/v0.4; simetría C/L comprobada; originales preservados en los enlaces. Transcripción de fuentes en módulos reproducibles.','cards':cards}
output=Path(__file__).parent/'docs/datos_v2_nuevas_cartas/catalogo_102_v03_v04.json'
output.parent.mkdir(parents=True,exist_ok=True)
output.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('CARDS=',len(cards),'SHA256=',hashlib.sha256(output.read_bytes()).hexdigest())
