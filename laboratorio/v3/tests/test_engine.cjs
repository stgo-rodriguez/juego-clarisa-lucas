const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { analizar } = require('../engine.js');
const root = path.join(__dirname, '..');
const cfg = JSON.parse(fs.readFileSync(path.join(root, 'matriz_economica_v3.json'), 'utf8'));
assert.equal(analizar(cfg).estimaciones.utn, null);
assert.equal(analizar(cfg).flujos.infancia.Clarisa.A, null);
const clone = JSON.parse(JSON.stringify(cfg));
for(const stage of Object.values(clone.etapas))for(const m of stage.mecanismos){
  if(m.frecuencia === null)m.frecuencia = 0;
  if(m.tipo === 'situacion' && m.probabilidad_A === null)m.probabilidad_A = .5;
  for(const field of ['premios','opcion_A','opcion_B'])if(m[field])
    for(const k of Object.keys(m[field]))if(m[field][k] === null)m[field][k] = 0;
}
for(const k of 'APKM')clone.requisitos.afinidad[k] = 0;
clone.requisitos.utn = {P:0,K:4};
for(const g of ['titulo','pasaporte'])for(const v of clone.requisitos[g])for(const k of 'APKM')v[k] = 0;
for(const g of ['adjudicacion_titulo','adjudicacion_pasaporte','pareja','vuelo'])for(const k of Object.keys(clone.requisitos[g]))clone.requisitos[g][k] = 0;
for(const k of Object.keys(clone.requisitos.casa.reserva_individual))clone.requisitos.casa.reserva_individual[k] = 0;
clone.requisitos.casa.precio_M=0;
clone.requisitos.falso_lucas_M=0;
clone.supuestos.fraccion_precio_casa_lucas=.5;
clone.supuestos.multiplicador_destinos_en_pareja_juventud=1;
clone.etapas.infancia.mecanismos.find(x=>x.id==='i_c5').premios.K=4;
assert.equal(analizar(clone).estimaciones.boda_autentica, 6);
clone.requisitos.afinidad.K=8;
clone.supuestos.afinidad_clarisa='K';
clone.supuestos.afinidad_lucas='K';
assert.equal(analizar(clone).necesidades.afinidad.K, 8);
clone.supuestos.afinidad_lucas='A';
clone.requisitos.afinidad.A=3;
assert.equal(analizar(clone).necesidades.afinidad.A, 3);
assert.equal(analizar(clone).estimaciones.boda_autentica, Infinity);
clone.etapas.infancia.mecanismos.find(x=>x.id==='i_c5').premios.K=0;
assert.equal(analizar(clone).estimaciones.falso_lucas, Infinity);
console.log('Motor JS: pruebas económicas correctas.');
