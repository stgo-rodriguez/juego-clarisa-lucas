/* Ecualizador macro v1 — flujos normalizados por ronda, presupuestos agregados. */
(function(root){
"use strict";
const R=["A","P","K","M"],STAGES=["infancia","juventud","adultez"];
function finite(x){return typeof x==="number"&&Number.isFinite(x)}
function pesosNormalizados(pesos){
 if(!pesos||R.some(r=>!finite(pesos[r])||pesos[r]<0))return null;
 const total=R.reduce((a,r)=>a+pesos[r],0);
 if(total<=0)return null;
 return Object.fromEntries(R.map(r=>[r,pesos[r]/total]));
}
function add(a,b){return a===null||b===null?null:a+b}
function producto(f,v,w){
 if(f===0||v===0||w===0)return 0;
 if(!finite(f)||!finite(v)||!finite(w))return null;
 return f*v*w;
}
function fuente(m){
 const pg=pesosNormalizados(m.pesos_ganancia),pp=pesosNormalizados(m.pesos_perdida);
 const gan={},per={},net={};
 const errores=[];
 if(m.frecuencia!==null&&(!finite(m.frecuencia)||m.frecuencia<0))errores.push("Frecuencia inválida: "+m.nombre);
 for(const [key,label] of [["ganancia","Volumen recibido"],["perdida","Volumen entregado"]]){
  if(m[key]!==null&&(!finite(m[key])||m[key]<0))errores.push(label+" inválido: "+m.nombre);
 }
 if(!pg&&m.ganancia!==0&&m.frecuencia!==0)errores.push("Proporciones recibidas incompletas: "+m.nombre);
 if(!pp&&m.perdida!==0&&m.frecuencia!==0)errores.push("Proporciones entregadas incompletas: "+m.nombre);
 for(const r of R){
  gan[r]=producto(m.frecuencia,m.ganancia,pg?.[r]??null);
  per[r]=producto(m.frecuencia,m.perdida,pp?.[r]??null);
  net[r]=gan[r]===null||per[r]===null?null:gan[r]-per[r];
 }
 return {ganancia:gan,perdida:per,neta:net,errores};
}
function seleccionarMetas(cfg,stage){
 const all=cfg.etapas[stage].objetivos||[];
 return all.filter(m=>m.categoria!=="meta_falso"&&m.categoria!=="meta_boda"||
   (m.categoria==="meta_boda"&&cfg.ruta_adultez==="boda")||
   (m.categoria==="meta_falso"&&cfg.ruta_adultez==="falso"));
}
function meta(g){
 const p=pesosNormalizados(g.pesos),d={};
 const errores=[];
 if(g.multiplicador!==null&&(!finite(g.multiplicador)||g.multiplicador<0))
   errores.push("Multiplicador N inválido: "+g.nombre);
 if(!p)errores.push("Proporciones de objetivo incompletas: "+g.nombre);
 for(const r of R)d[r]=g.multiplicador===0?0:producto(1,g.multiplicador,p?.[r]??null);
 return {por_recurso:d,errores};
}
function dividir(a,b){
 if(a===0)return 0; // un recurso fuera de la demanda no bloquea aunque su producción sea N/D
 if(a===null||b===null)return null;
 if(b<=0)return Infinity;
 return a/b;
}
function evaluarEtapa(cfg,stage){
 const e=cfg.etapas[stage],srcs=e.mecanismos.map(m=>({id:m.id,nombre:m.nombre,...fuente(m)}));
 const goals=seleccionarMetas(cfg,stage).map(g=>({id:g.id,nombre:g.nombre,categoria:g.categoria,...meta(g)}));
 const recibidos={},perdidos={},netos={},demanda={},saldo={},cobertura={};
 const T=e.duracion_objetivo;
 let errores=[...srcs.flatMap(s=>s.errores),...goals.flatMap(g=>g.errores)];
 if(T!==null&&(!finite(T)||T<=0))errores.push("Duración objetivo inválida: "+stage);
 for(const r of R){
  recibidos[r]=srcs.reduce((a,s)=>add(a,s.ganancia[r]),0);
  perdidos[r]=srcs.reduce((a,s)=>add(a,s.perdida[r]),0);
  netos[r]=srcs.reduce((a,s)=>add(a,s.neta[r]),0);
  demanda[r]=goals.reduce((a,g)=>add(a,g.por_recurso[r]),0);
  saldo[r]=T===null||netos[r]===null||demanda[r]===null?null:T*netos[r]-demanda[r];
  cobertura[r]=T===null||netos[r]===null||demanda[r]===null?null:
    demanda[r]===0?null:dividir(T*netos[r],demanda[r]);
 }
 let tiempo=0,desconocido=false,imposible=false,cuello=null;
 for(const r of R){
   const t=dividir(demanda[r],netos[r]);
   if(t===null){desconocido=true;continue}
   if(t===Infinity||(!Number.isFinite(t)&&t!==0)){imposible=true;cuello=r;continue}
   if(demanda[r]>0&&netos[r]<=0){imposible=true;cuello=r;continue}
   if(t>tiempo){tiempo=t;cuello=r}
 }
 const tAgregado=imposible?Infinity:desconocido?null:tiempo;
 let factor=null;
 if(T!==null&&tAgregado!==null){
  factor=tAgregado===0?0:tAgregado/T;
 }
 const recursosActivos=R.filter(r=>demanda[r]!==null&&demanda[r]>0);
 if(recursosActivos.length===0&&R.every(r=>demanda[r]===0)&&tAgregado!==null)errores.push("No hay volumen objetivo positivo en "+stage);
 if(tAgregado===null)errores.push("No hay información económica suficiente: completá frecuencias, volúmenes y objetivos.");
 const grossTotal=R.reduce((s,r)=>add(s,recibidos[r]),0);
 const mixProducido=Object.fromEntries(R.map(r=>[r,grossTotal===null||recibidos[r]===null?null:grossTotal>0?recibidos[r]/grossTotal:null]));
 const demandTotal=R.reduce((s,r)=>add(s,demanda[r]),0);
 const mixObjetivos=Object.fromEntries(R.map(r=>[r,demandTotal===null||demanda[r]===null?null:demandTotal>0?demanda[r]/demandTotal:null]));
 const referencia=pesosNormalizados(e.distribucion_referencia);
 return {etapa:stage,fuentes:srcs,metas:goals,recibidos,perdidos,netos,demanda,saldo,cobertura,mixProducido,mixObjetivos,
  referencia,tAgregado,objetivo_rondas:T,factorVolumenRequerido:factor,cuello,errores:[...new Set(errores)]};
}
function evaluarMacro(cfg){
 const v=cfg.unidad_referencia;
 if(!finite(v)||v<=0)return {estado:"invalido",errores:["La unidad de referencia V debe ser positiva."],etapas:{}};
 const etapas=Object.fromEntries(STAGES.map(stage=>[stage,evaluarEtapa(cfg,stage)]));
 const riesgos=[
  "Modelo agregado por personaje representativo, sin turnos simultáneos ni ventaja de pareja.",
  "El tiempo indicado es cobertura de un presupuesto económico agregado, no duración esperada de la partida.",
  "La frecuencia de casilleros y Perfiles es un supuesto de escenario, no se deriva de posiciones o dados.",
  "Las metas de comprobación y reserva se agregan como presupuesto de análisis; no se modelan pagos, saldos ni orden de hitos.",
  "Las proporciones de referencia son objetivos históricos de mezcla del diseño, no premios aprobados.",
  "La unidad V es una normalización: multiplicar todos los premios y objetivos por V no cambia la cantidad de rondas."
 ];
 return {estado:"ok",unidad_referencia:v,etapas,riesgos};
}
const api={evaluarMacro,evaluarEtapa,fuente,meta,pesosNormalizados,seleccionarMetas};
if(typeof module!=="undefined"&&module.exports)module.exports=api;
if(root)Object.assign(root,api);
})(typeof window!=="undefined"?window:null);
