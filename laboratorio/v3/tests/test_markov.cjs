const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const {analizarInfanciaUTN}=require('../infancia_markov.js');
global.analizarInfanciaUTN=analizarInfanciaUTN;
const {calibrarUTN,aplicarCandidatoUTN}=require('../calibrador_utn.js');
const raw=JSON.parse(fs.readFileSync(path.join(__dirname,'..','matriz_economica_v3.json'),'utf8'));
function cfg(){
  const c=JSON.parse(JSON.stringify(raw));
  const opt=c.supuestos.utn_v31;
  opt.rol='Clarisa';opt.posicion_inicial=5;opt.P_inicial=0;opt.K_inicial=0;
  opt.modo_situaciones='neutras';opt.maximo_premio_exploracion=4;
  c.requisitos.utn={P:0,K:0};
  for(const cell of c.etapas.infancia.mecanismos.filter(m=>m.tipo==='casillero'))
    for(const r of ['P','K'])if(Object.hasOwn(cell.premios,r))cell.premios[r]=0;
  return c;
}
(async()=>{
 const untouched=analizarInfanciaUTN(raw);
 assert.equal(untouched.estado,'pendiente');
 assert.equal(raw.requisitos.utn.P,null);
 let c=cfg(),r=analizarInfanciaUTN(c);
 assert.equal(r.estado,'calculado');assert.ok(Math.abs(r.rondas_esperadas-3)<1e-6);
 c.supuestos.utn_v31.posicion_inicial=1;
 r=analizarInfanciaUTN(c);
 assert.ok(r.rondas_esperadas>3);
 c.requisitos.utn={P:1,K:1};
 r=analizarInfanciaUTN(c);
 assert.equal(r.estado,'inalcanzable');
 const tile=id=>c.etapas.infancia.mecanismos.find(m=>m.id===id);
 tile('i_c2').premios.P=1;tile('i_c4').premios.P=1;tile('i_c5').premios.K=1;
 r=analizarInfanciaUTN(c);
 assert.equal(r.estado,'calculado');assert.ok(r.rondas_esperadas>3);
 c.supuestos.utn_v31.modo_situaciones='configuradas';
 assert.equal(analizarInfanciaUTN(c).estado,'pendiente');
 c.etapas.infancia.mecanismos.find(m=>m.id==='i_s_c').probabilidad_A=null;
 for(const side of ['opcion_A','opcion_B']){
  c.etapas.infancia.mecanismos.find(m=>m.id==='i_s_c')[side].P=0;
  c.etapas.infancia.mecanismos.find(m=>m.id==='i_s_c')[side].K=0;
 }
 const same=analizarInfanciaUTN(c);
 assert.equal(same.estado,'calculado');
 c.supuestos.utn_v31.modo_situaciones='neutras';
 const saved=JSON.stringify(c);
 const out=await calibrarUTN(c);
 assert.equal(out.estado,'calculado');
 assert.ok(out.evaluaciones>0);
 assert.equal(JSON.stringify(c),saved,'El calibrador no modifica la configuración');
 assert.ok(out.lista.length>0);
 for(let i=1;i<out.lista.length;i++)assert.ok(out.lista[i].error_absoluto>=out.lista[i-1].error_absoluto-1e-8);
 const next=aplicarCandidatoUTN(c,out.lista[0]);
 assert.notEqual(next,c);
 assert.equal(JSON.stringify(c),saved);
 assert.equal(next.etapas.infancia.mecanismos.find(m=>m.id==='i_c2').premios.P,out.lista[0].premio_P_casilleros_2_y_4);
 assert.equal(next.etapas.infancia.mecanismos.find(m=>m.id==='i_c5').premios.K,out.lista[0].premio_K_casillero_5);
 const ui=fs.readFileSync(path.join(__dirname,'..','ecualizador.html'),'utf8');
 assert.ok(ui.includes('id="prob-panel"'));
 assert.ok(ui.includes('data-tab="utn"'));
 assert.ok(ui.includes('objetivo_rondas'));
 for(const s of [...ui.matchAll(/<script(?:[^>]*)>([\s\S]*?)<\/script>/g)])
  if(s[1].trim())new vm.Script(s[1],{filename:'ecualizador.html:inline'});
 console.log('v3.1: Markov, calibrador inverso, escenarios y sintaxis UI OK. '+out.evaluaciones+' evaluaciones.');
})().catch(e=>{console.error(e);process.exitCode=1;});
