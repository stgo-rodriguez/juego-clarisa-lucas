/* Vista de Ecualizador Macro: interfaz desacoplada del motor y del ecualizador v3.1. */
(function(){
"use strict";
const R=["A","P","K","M"],STAGES=["infancia","juventud","adultez"],
 NAMES={infancia:"Infancia",juventud:"Juventud",adultez:"Adultez"},
 RES={A:"Amor",P:"Personalidad",K:"Conocimiento",M:"Dinero"},
 COLORS={A:"#f28aa6",P:"#b6a2f1",K:"#7ecce7",M:"#e6c978"},
 STORE="clarisa-lucas-macro-v1", $=id=>document.getElementById(id);
let base=null,active=null,stage="infancia",sourceIndex=0,goalIndex=0;
const clone=o=>JSON.parse(JSON.stringify(o));
const esc=v=>String(v).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
function fmt(n,d=2){
 if(n===null||n===undefined||Number.isNaN(n))return "N/D";
 if(n===Infinity)return "Inalcanzable";
 if(!Number.isFinite(n))return "N/D";
 return new Intl.NumberFormat("es-AR",{maximumFractionDigits:d,minimumFractionDigits:0}).format(n);
}
function pct(n){return n===null?"N/D":fmt(n*100,1)+"%"}
function normRaw(obj){
 const n=pesosNormalizados(obj);
 return n?R.map(r=>r+" "+pct(n[r])).join(" · "):"N/D";
}
function pathGet(path){return path.split(".").reduce((o,k)=>o?.[k],active)}
function pathSet(path,val){
 const p=path.split("."),last=p.pop();
 let o=active;
 for(const k of p)o=o[k];
 o[last]=val;
}
function renderInput(label,path,val,opt={}){
 const min=opt.min===undefined?0:opt.min,max=opt.max===undefined?30:opt.max,
  step=opt.step??0.1,
  n=val===null||val===undefined?"":String(val),
  text=val===null||val===undefined?"SIN DEFINIR":fmt(val,2);
 return '<div class="field"><label><span>'+esc(label)+'</span><span class="value-label">'+esc(text)+'</span></label>'+
  '<div class="input-duo"><input type="range" data-set="'+esc(path)+'" min="'+min+'" max="'+max+'" step="'+step+'" '+
   (n===""?'disabled':'value="'+esc(n)+'"')+' aria-label="Deslizador: '+esc(label)+'">'+
  '<input type="number" data-set="'+esc(path)+'" min="'+min+'" step="any" value="'+esc(n)+'" placeholder="N/D" aria-label="'+esc(label)+'"></div></div>';
}
function renderMix(title,path,weights){
 let out='<div class="mini-title">'+esc(title)+'</div>';
 out+='<div class="tiny">Pesos relativos: el motor los normaliza automáticamente para que sumen 100%.</div>';
 for(const r of R)out+=renderInput(RES[r]+" · "+r,path+"."+r,weights[r],{min:0,max:100,step:1});
 out+='<div class="tiny">Composición efectiva: '+esc(normRaw(weights))+'</div>';
 return out;
}
function selectedSource(){return active.etapas[stage].mecanismos[Math.min(sourceIndex,active.etapas[stage].mecanismos.length-1)]}
function selectedGoal(){return active.etapas[stage].objetivos[Math.min(goalIndex,active.etapas[stage].objetivos.length-1)]}
function sourceEditor(){
 const m=selectedSource(),p="etapas."+stage+".mecanismos."+sourceIndex;
 let html='<div class="box"><b>'+esc(m.nombre)+'</b><div class="tiny">'+esc(m.nota)+'</div></div>';
 html+=renderInput("Activaciones por ronda · f",p+".frecuencia",m.frecuencia,{min:0,max:3,step:.05});
 html+=renderInput("Volumen recibido por activación · g × V",p+".ganancia",m.ganancia,{min:0,max:20,step:.25});
 html+=renderInput("Volumen quitado por activación · ℓ × V",p+".perdida",m.perdida,{min:0,max:20,step:.25});
 html+=renderMix("Proporciones del volumen recibido",p+".pesos_ganancia",m.pesos_ganancia);
 html+=renderMix("Proporciones del volumen quitado",p+".pesos_perdida",m.pesos_perdida);
 return html;
}
function goalEditor(){
 const m=selectedGoal(),p="etapas."+stage+".objetivos."+goalIndex;
 let html='<div class="box"><b>'+esc(m.nombre)+'</b><p class="tiny">'+
  esc(m.categoria==="verificacion"?"El juego exige tener recursos: no implica gastarlos. Aquí se cuentan como presupuesto macro, sin modelar secuencia.":m.categoria==="consumo"?"Este objetivo representa inversión o gasto agregado; no reproduce los subhitos concretos.":"Representación macro de volumen necesario para el objetivo; combina simplificadamente requisitos de distinta naturaleza.")+'</p></div>';
 html+=renderInput("Volumen objetivo · N × V",p+".multiplicador",m.multiplicador,{min:0,max:40,step:.5});
 html+=renderMix("Proporciones de recursos exigidos",p+".pesos",m.pesos);
 if(stage==="adultez"&&((m.categoria==="meta_falso"&&active.ruta_adultez==="boda")||(m.categoria==="meta_boda"&&active.ruta_adultez==="falso")))
   html+='<div class="flag">Este desenlace no forma parte de la ruta adulta seleccionada. Podés editarlo y activarlo luego desde “Desenlace económico”.</div>';
 return html;
}
function renderControls(){
 $("edit-stage").textContent=NAMES[stage];
 $("unit").value=active.unidad_referencia;
 $("target-editor").innerHTML=renderInput("Duración objetivo de la etapa (rondas)","etapas."+stage+".duracion_objetivo",
  active.etapas[stage].duracion_objetivo,{min:.25,max:30,step:.25})+
  '<div class="tiny">La duración objetivo es un criterio de diseño: no la predice el motor.</div>';
 $("route-field").hidden=stage!=="adultez";
 $("route").value=active.ruta_adultez;
 $("source-select").innerHTML=active.etapas[stage].mecanismos.map((x,i)=>'<option value="'+i+'"'+(i===sourceIndex?' selected':'')+'>'+esc(x.nombre)+'</option>').join("");
 $("source-editor").innerHTML=sourceEditor();
 $("goal-select").innerHTML=active.etapas[stage].objetivos.map((x,i)=>'<option value="'+i+'"'+(i===goalIndex?' selected':'')+'>'+esc(x.nombre)+'</option>').join("");
 $("goal-editor").innerHTML=goalEditor();
 $("reference-editor").innerHTML=renderMix("Distribución de referencia para comparar","etapas."+stage+".distribucion_referencia",active.etapas[stage].distribucion_referencia);
 document.querySelectorAll("[data-stage]").forEach(x=>{
  const on=x.dataset.stage===stage;x.classList.toggle("active",on);x.setAttribute("aria-selected",String(on));
 });
}
function infoCard(title,value,footer,cls=""){
 return '<div class="card"><div class="title">'+esc(title)+'</div><div class="value '+cls+'">'+esc(value)+'</div><div class="foot">'+esc(footer)+'</div></div>';
}
function sumObj(obj){let a=0;for(const r of R){if(obj[r]===null)return null;a+=obj[r];}return a}
function mixBar(values){
 if(R.some(r=>values?.[r]===null||values?.[r]===undefined))return '<span class="muted">N/D</span>';
 const sum=R.reduce((a,r)=>a+values[r],0);
 if(sum<=0)return '<span class="muted">Sin volumen positivo</span>';
 return '<div class="mini-bar" style="display:flex;height:13px">'+R.map(r=>
  '<span title="'+esc(RES[r])+': '+fmt(values[r]*100/sum,1)+'%" style="display:block;height:100%;width:'+
  Math.max(0,100*values[r]/sum)+'%;background:'+COLORS[r]+'"></span>').join("")+'</div>';
}
function renderResults(){
 if(!active)return;
 const evalData=evaluarMacro(active);
 if(evalData.estado!=="ok"){$("metrics").innerHTML='<div class="box">'+esc(evalData.errores.join(", "))+'</div>';return}
 const e=evalData.etapas[stage],V=active.unidad_referencia;
 const rTotal=sumObj(e.recibidos),qTotal=sumObj(e.perdidos),dTotal=sumObj(e.demanda);
 const t=e.tAgregado,target=e.objetivo_rondas;
 let tClass=t===null?"":t===Infinity?"bad":target===null?"":t<=target?"success":"warn";
 $("metrics").innerHTML=
  infoCard("Volumen recibido por ronda",rTotal===null?"N/D":fmt(rTotal*V)+" u.", "Ganancias brutas; equivalente normalizado: "+fmt(rTotal)+" × V")+
  infoCard("Volumen quitado por ronda",qTotal===null?"N/D":fmt(qTotal*V)+" u.","Pérdidas brutas de todos los mecanismos")+
  infoCard("Rondas de cobertura económica",t===null?"N/D":t===Infinity?"∞":fmt(t)+" r", "Presupuesto global agregado, no rondas de partida",tClass)+
  infoCard("Factor de volumen neto necesario",e.factorVolumenRequerido===null?"N/D":e.factorVolumenRequerido===Infinity?"∞":fmt(e.factorVolumenRequerido)+"×",
  "Para cubrir el presupuesto dentro de "+(target===null?"una duración N/D":fmt(target)+" rondas"),e.factorVolumenRequerido!==null&&e.factorVolumenRequerido>1?"warn":"");
 $("resource-cards").innerHTML=R.map(r=>{
  const net=e.netos[r],dem=e.demanda[r];
  return '<div class="res-card"><div class="row"><span class="symbol" style="color:'+COLORS[r]+'">'+r+'</span><span class="tiny">'+RES[r]+'</span></div>'+
   '<div class="number">'+(net===null?"N/D":fmt(net,2)+" V/r")+'</div>'+
   '<div class="tiny">Meta agregada: '+(dem===null?"N/D":fmt(dem,2)+" V")+'</div></div>';
 }).join("");
 $("coverage").innerHTML=R.map(r=>{
  const m=e.cobertura[r];
  const d=e.demanda[r],rate=e.netos[r];
  let label=m===null?"N/D":pct(m);
  if(d===0)label="Sin demanda";
  const width=Number.isFinite(m)?Math.max(0,Math.min(100,m*100)):0;
  return '<div class="resource-row"><span class="symbol" style="color:'+COLORS[r]+'">'+r+' · '+RES[r]+'</span>'+
    '<div class="mini-bar"><span style="width:'+width+'%;background:'+COLORS[r]+'"></span></div>'+
    '<strong class="'+(Number.isFinite(m)&&m<1?"warn":"")+'">'+esc(label)+'</strong></div>';
 }).join("");
 const mixR=[["Producción bruta",e.mixProducido],["Presupuesto objetivos",e.mixObjetivos],["Referencia de diseño",e.referencia]];
 $("mix-comparison").innerHTML='<div class="legend">'+R.map(r=>'<span style="--legend-color:'+COLORS[r]+'">'+esc(RES[r])+'</span>').join("")+'</div>'+
  mixR.map(([name,obj])=>'<div class="resource-row" style="grid-template-columns:160px 1fr"><span class="tiny">'+esc(name)+'</span>'+mixBar(obj)+'</div>').join("");
 $("source-rows").innerHTML=e.fuentes.map((s,i)=>{
  const m=active.etapas[stage].mecanismos[i],net=sumObj(s.neta);
  return '<tr><td>'+esc(m.nombre)+'</td><td class="num">'+fmt(m.frecuencia)+'</td><td class="num">'+fmt(m.ganancia)+'</td><td class="num">'+fmt(m.perdida)+'</td><td class="num">'+fmt(net)+'</td></tr>';
 }).join("");
 $("goal-rows").innerHTML=e.metas.map(g=>{
  const original=active.etapas[stage].objetivos.find(m=>m.id===g.id);
  return '<tr><td>'+esc(g.nombre)+'</td><td>'+esc(g.categoria)+'</td><td class="num">'+fmt(original.multiplicador)+'</td><td>'+esc(normRaw(original.pesos))+'</td></tr>';
 }).join("");
 $("phase-overview").innerHTML=STAGES.map(st=>{
  const x=evalData.etapas[st];return '<div class="phase-item"><b>'+NAMES[st]+'</b><div class="tiny">Duración objetivo: '+(x.objetivo_rondas===null?"N/D":fmt(x.objetivo_rondas)+" rondas")+'</div>'+
   '<strong>'+fmt(x.tAgregado)+' r</strong><div class="tiny">Rondas de cobertura del presupuesto</div></div>';
 }).join("");
 let explanation="";
 if(t===null) explanation="Faltan parámetros de esta etapa. Completá los volúmenes por mecanismo, sus frecuencias y los multiplicadores N de los objetivos. Los campos vacíos no se convierten en cero.";
 else if(t===Infinity)explanation="El presupuesto de objetivos no es alcanzable con las tasas netas de generación configuradas. Revisá los recursos que se producen o quitan.";
 else if(target===null)explanation="La etapa requeriría "+fmt(t)+" rondas para cubrir su presupuesto de recursos en este modelo agregado. Definí una duración objetivo para obtener un factor de calibración.";
 else if(t>target)explanation="Con el volumen neto elegido, el presupuesto agregado necesita "+fmt(t)+" rondas, frente a la meta de "+fmt(target)+". Factor necesario de producción neta: "+fmt(t/target)+"×. Recurso de mayor presión: "+(e.cuello||"no determinado")+".";
 else explanation="El presupuesto agregado se cubriría en "+fmt(t)+" rondas, dentro de la meta de "+fmt(target)+". Esto no demuestra que las reglas permitan completar la etapa en ese tiempo: el movimiento y la ejecución de hitos requieren el modelo detallado.";
 $("interpretation").innerHTML='<strong>Lectura del resultado:</strong> '+esc(explanation);
 $("warnings").innerHTML='<h3>Advertencias activas</h3><ul class="note-list">'+
  [...new Set([...e.errores,...evalData.riesgos])].map(x=>'<li>'+esc(x)+'</li>').join("")+'</ul>';
 $("save-state").textContent=active.es_demostracion?"Ejemplo ficticio — guardado local":"Modelo paramétrico — guardado local";
}
function renderAll(){renderControls();renderResults()}
function persist(){
 try{localStorage.setItem(STORE,JSON.stringify(active))}catch(e){$("save-state").textContent="Guardado local no disponible"}
}
function applyEdit(path,value){
 pathSet(path,value);
 active.es_demostracion=Boolean(active.es_demostracion);
 renderResults();persist();
}
function updatePair(input,value){
 const field=input.closest(".field");
 if(!field)return;
 const note=field.querySelector(".value-label");
 if(note)note.textContent=value===null?"SIN DEFINIR":fmt(value);
 field.querySelectorAll("[data-set]").forEach(sib=>{
  if(sib===input)return;
  if(sib.type==="range"){sib.disabled=value===null;if(value!==null)sib.value=value}
  else if(sib.type==="number")sib.value=value===null?"":value;
 });
}
function onParamInput(ev){
 const input=ev.target;if(!input?.matches("[data-set]"))return;
 const val=input.value.trim()===""?null:Number(input.value);
 if(val!==null&&!Number.isFinite(val))return;
 if(val!==null&&Number(input.min||0)>val)return;
 applyEdit(input.dataset.set,val);updatePair(input,val);
 const path=input.dataset.set;
 if(path.includes("pesos_")||path.endsWith(".pesos")||path.includes(".pesos.")||path.includes("distribucion_referencia")){
  const tiny=input.closest(".section")?.querySelector(".tiny");
  if(tiny&&tiny.textContent.includes("Composición efectiva"))tiny.textContent="Composición efectiva: "+normRaw(pathGet(path.split(".").slice(0,-1).join(".")));
 }
}
function download(name,content){
 const blob=new Blob([content],{type:"application/json;charset=utf-8"});
 const url=URL.createObjectURL(blob),a=document.createElement("a");
 a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),2000);
}
function validConfig(o){
 if(!o||!Number.isFinite(o.unidad_referencia)||o.unidad_referencia<=0||!["boda","falso"].includes(o.ruta_adultez))return false;
 return STAGES.every(st=>{
  const e=o.etapas?.[st];
  return e&&Array.isArray(e.mecanismos)&&e.mecanismos.length>=3&&Array.isArray(e.objetivos)&&e.objetivos.length>0&&
   e.mecanismos.every(m=>m.id&&m.pesos_ganancia&&m.pesos_perdida)&&e.objetivos.every(g=>g.id&&g.pesos);
 });
}
function setStage(st){
 if(!STAGES.includes(st))return;
 stage=st;sourceIndex=0;goalIndex=0;renderAll();
}
document.querySelectorAll("[data-stage]").forEach(b=>b.addEventListener("click",()=>setStage(b.dataset.stage)));
document.querySelector(".sticky").addEventListener("input",onParamInput);
$("source-select").addEventListener("change",e=>{sourceIndex=Number(e.target.value);$("source-editor").innerHTML=sourceEditor()});
$("goal-select").addEventListener("change",e=>{goalIndex=Number(e.target.value);$("goal-editor").innerHTML=goalEditor()});
$("route").addEventListener("change",e=>{active.ruta_adultez=e.target.value;persist();renderResults();$("goal-editor").innerHTML=goalEditor()});
$("unit").addEventListener("input",e=>{
 const n=e.target.value.trim()===""?null:Number(e.target.value);
 if(n===null||!Number.isFinite(n)||n<=0){$("save-state").textContent="V debe ser positivo";return}
 active.unidad_referencia=n;persist();renderResults();
});
$("demo").addEventListener("click",()=>{
 if(!confirm("¿Cargar el ejemplo ficticio? Reemplazará el trabajo actual guardado en este navegador. Podés exportarlo antes."))return;
 active=crearEjemploMacro(base);stage="infancia";sourceIndex=0;goalIndex=0;persist();renderAll();
});
$("reset").addEventListener("click",()=>{
 if(!confirm("¿Volver al catálogo con importes sin definir? Se perderá el trabajo local no exportado."))return;
 active=clone(base);stage="infancia";sourceIndex=0;goalIndex=0;persist();renderAll();
});
$("export").addEventListener("click",()=>download("clarisa-lucas-macro-escenario.json",JSON.stringify(active,null,2)+"\n"));
$("import").addEventListener("click",()=>$("file-import").click());
$("file-import").addEventListener("change",async e=>{
 const f=e.target.files[0];if(!f)return;
 try{
  const parsed=JSON.parse(await f.text());
  if(!validConfig(parsed))throw Error("El archivo no tiene el formato del ecualizador macro.");
  if(!confirm("¿Importar este escenario? Se reemplazará el trabajo local actual."))return;
  active=parsed;stage="infancia";sourceIndex=0;goalIndex=0;persist();renderAll();
 }catch(err){alert("No se pudo importar: "+err.message)}
 finally{e.target.value=""}
});
fetch("./catalogo_macro.json").then(r=>{if(!r.ok)throw Error("No se encontró el catálogo macro");return r.json()}).then(catalog=>{
 base=catalog;active=clone(base);
 try{
  const saved=JSON.parse(localStorage.getItem(STORE)||"null");
  if(validConfig(saved))active=saved;
 }catch(err){ /* Sin estado persistente */ }
 renderAll();
}).catch(err=>{$("metrics").innerHTML='<div class="box">No se pudo cargar el catálogo. Abrí la herramienta desde GitHub Pages. '+esc(err.message)+'</div>'});
})();
