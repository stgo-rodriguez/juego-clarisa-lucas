/* Modelo determinista. Los valores económicos provienen del catálogo. */
function analizar(cfg){
 const keys=["A","P","K","M"],roles=["Clarisa","Lucas"],stages=["infancia","juventud","adultez"];
 const isnum=x=>typeof x==="number"&&Number.isFinite(x);
 const add=(a,b)=>a===null||b===null?null:a+b, mul=(a,b)=>a===null||b===null?null:a*b;
 const val=(x,k)=>x&&Object.prototype.hasOwnProperty.call(x,k)?x[k]:0;
 const zero=()=>Object.fromEntries(keys.map(k=>[k,0]));
 function first(constraints){
   let t=0,unknown=false;
   for(const c of constraints){
     if(c.need===null||c.have===null||c.rate===null){unknown=true;continue;}
     if(![c.need,c.have,c.rate].every(isnum)){unknown=true;continue;}
     let deficit=Math.max(0,c.need-c.have);
     if(deficit>1e-9&&c.rate<=0)return Infinity;
     if(deficit>1e-9)t=Math.max(t,deficit/c.rate);
   }
   return unknown?null:t;
 }
 const flows={},breakdown={},missing=[];
 for(const stage of stages){
   flows[stage]={};breakdown[stage]={};
   for(const role of roles){
     let acc=zero(),events={};
     for(const m of cfg.etapas[stage].mecanismos){
       if(m.rol!=="ambos"&&m.rol!==role)continue;
       if(m.variante&&m.variante!==cfg.supuestos.variante_juvenil)continue;
       let frequency=m.frecuencia;
       if(m.tipo==="casillero"&&stage!=="infancia")
         frequency=mul(frequency,cfg.supuestos["multiplicador_destinos_en_pareja_"+stage]);
       const out=zero();
       for(const k of keys){
         let amount=val(m.premios,k);
         if(m.tipo==="situacion"){
           let a=val(m.opcion_A,k),b=val(m.opcion_B,k),p=m.probabilidad_A;
           amount=a!==null&&b!==null&&a===b?a:(p===null||a===null||b===null?null:p*a+(1-p)*b);
         }
         out[k]=frequency===0||amount===0?0:mul(frequency,amount);
         acc[k]=add(acc[k],out[k]);
         if(out[k]===null)missing.push(stage+" / "+role+" / "+m.nombre+" / "+k);
       }
       events[m.id]=out;
     }
     flows[stage][role]=acc;breakdown[stage][role]=events;
   }
 }
 const r=cfg.requisitos;
 const sumVectors=xs=>Object.fromEntries(keys.map(k=>[k,xs.reduce((acc,x)=>add(acc,val(x,k)),0)]));
 const title=sumVectors([...r.titulo,r.adjudicacion_titulo]);
 const passport=sumVectors([...r.pasaporte,r.adjudicacion_pasaporte]);
 const blank=()=>Object.fromEntries(roles.map(role=>[role,zero()]));
 const condition=(need,have,rate)=>({need,have,rate});
 const each=(need,bal,rate)=>roles.flatMap(role=>keys.map(k=>condition(val(need,k),bal[role][k],rate[role][k])));
 const grow=(bal,rate,time)=>{
   const o=blank();
   for(const role of roles)for(const k of keys){
     const x=bal[role][k],y=rate[role][k];
     o[role][k]=time===null||!Number.isFinite(time)||x===null||y===null?null:x+y*time;
   }
   return o;
 };
 const debit=(bal,reqs)=>{
   const o=blank();
   for(const role of roles)for(const k of keys)
     o[role][k]=bal[role][k]===null||val(reqs,k)===null?null:bal[role][k]-val(reqs,k);
   return o;
 };
 const pair=(bal,k)=>add(bal.Clarisa[k],bal.Lucas[k]);
 const tInf=first(each(r.utn,blank(),flows.infancia));
 const infBal=grow(blank(),flows.infancia,tInf);
 const tTitle=first(each(title,infBal,flows.juventud));
 const tPassport=first(each(passport,infBal,flows.juventud));
 const youngCosts=sumVectors([title,passport,r.pareja]);
 const youngReq=sumVectors([youngCosts,r.vuelo]);
 const tYoung=first(each(youngReq,infBal,flows.juventud));
 const youthBal=debit(grow(infBal,flows.juventud,tYoung),youngCosts);
 let houseCs=[];
 for(const role of roles)for(const k of ["A","P"])
   houseCs.push(condition(val(r.casa.reserva_individual,k),youthBal[role][k],flows.adultez[role][k]));
 houseCs.push(condition(r.casa.precio_M,pair(youthBal,"M"),pair(flows.adultez,"M")));
 const tHouse=first(houseCs);
 const houseBal=debit(grow(youthBal,flows.adultez,tHouse),r.casa.reserva_individual);
 const frac=cfg.supuestos.fraccion_precio_casa_lucas;
 if(frac===null||r.casa.precio_M===null){houseBal.Clarisa.M=null;houseBal.Lucas.M=null;}
 else{
   houseBal.Clarisa.M=houseBal.Clarisa.M===null?null:houseBal.Clarisa.M-(1-frac)*r.casa.precio_M;
   houseBal.Lucas.M=houseBal.Lucas.M===null?null:houseBal.Lucas.M-frac*r.casa.precio_M;
 }
 const ca=cfg.supuestos.afinidad_clarisa,la=cfg.supuestos.afinidad_lucas;
 const affinity=Object.fromEntries(keys.map(k=>[k,(ca===k||la===k)?val(r.afinidad,k):0]));
 const tWedding=first(keys.map(k=>condition(affinity[k],pair(houseBal,k),pair(flows.adultez,k))));
 const tFalse=first([condition(r.falso_lucas_M,houseBal.Lucas.M,flows.adultez.Lucas.M)]);
 const cumulative=(...ns)=>ns.some(x=>x===null)?null:ns.reduce((a,b)=>a+b,0);
 const estimates={
    utn:tInf,titulo:cumulative(tInf,tTitle),pasaporte:cumulative(tInf,tPassport),
    dublin:cumulative(tInf,tYoung),casa:cumulative(tInf,tYoung,tHouse),
    boda_autentica:cumulative(tInf,tYoung,tHouse,tWedding),
    boda_con_falso:cumulative(tInf,tYoung,tHouse,tWedding),
    falso_lucas:cumulative(tInf,tYoung,tHouse,tFalse)
 };
 const bottlenecks=[];
 for(const role of roles)for(const k of keys){
   const delay=first([condition(youngReq[k],infBal[role][k],flows.juventud[role][k])]);
   if(delay!==null)bottlenecks.push({etapa:"Juventud",rol:role,recurso:k,rondas:delay});
 }
 for(const k of keys){
   if(affinity[k]===0)continue;
   const delay=first([condition(affinity[k],pair(houseBal,k),pair(flows.adultez,k))]);
   if(delay!==null)bottlenecks.push({etapa:"Adultez · afinidad",rol:"Pareja",recurso:k,rondas:delay});
 }
 bottlenecks.sort((a,b)=>b.rondas-a.rondas);
 const notes=[];
 if(cfg.supuestos.regla_afinidad!=="pago")notes.push("La variante distinta de pago terminal de afinidad no está modelada.");
 if(frac!==null&&(frac<0||frac>1))notes.push("Fracción del precio pagada por Lucas fuera del intervalo [0,1].");
 for(const stage of stages)for(const role of roles)for(const k of keys)
   if(flows[stage][role][k]!==null&&flows[stage][role][k]<0)notes.push("Flujo neto negativo en "+stage+" / "+role+" / "+k+"; las pérdidas deben acotarse por saldo elegible.");
 if(Object.values(estimates).some(x=>x===null))notes.push("Hay resultados no identificables: faltan importes o frecuencias. No se sustituyen por cero.");
 notes.push("Las estimaciones son cotas económicas optimistas y no incluyen demoras de ubicación, adjudicaciones, consentimiento, afinidad por zona, disputas o decisiones estratégicas.");
 notes.push("Boda con Falso Lucas: la cota de boda supone cooperación hipotética. No significa que él tenga incentivo para consentir.");
 return {flujos:flows,desglose:breakdown,necesidades:{titulo:title,pasaporte:passport,juventud:youngReq,afinidad:affinity},
  estimaciones:estimates,etapas:{infancia:tInf,juventud:tYoung,adultez_casa:tHouse,adultez_boda:tWedding,adultez_falso:tFalse},
  cuellos:bottlenecks.slice(0,10),avisos:notes,desconocidos:[...new Set(missing)],
  saldos:{salida_infancia:infBal,salida_juventud:youthBal,despues_casa:houseBal},
  precision:"Cota económica, no duración probabilística ni p80."};
}
if(typeof window!=='undefined')window.analizar=analizar;
if(typeof module!=='undefined')module.exports={analizar};
