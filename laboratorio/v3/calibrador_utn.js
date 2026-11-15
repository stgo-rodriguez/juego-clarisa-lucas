/* Calibrador inverso UTN v3.1: búsqueda determinista, sin Monte Carlo. */
async function calibrarUTN(config, report=()=>{}) {
 const control=config.supuestos?.utn_v31||{};
 const meta=control.objetivo_rondas??5,maximo=control.maximo_premio_exploracion;
 if(!Number.isFinite(meta)||meta<=0) return {estado:"error",detalle:"La meta debe ser un número positivo de rondas."};
 if(!Number.isInteger(maximo)||maximo<0||maximo>30) return {estado:"error",detalle:"El máximo de exploración debe ser un entero de 0 a 30."};
 const escenario=JSON.parse(JSON.stringify(config));
 const ms=escenario.etapas.infancia.mecanismos;
 const p2=ms.find(x=>x.id==="i_c2"),p4=ms.find(x=>x.id==="i_c4"),k5=ms.find(x=>x.id==="i_c5");
 if(!p2||!p4||!k5)return {estado:"error",detalle:"Faltan los casilleros de producción 2, 4 o 5."};
 const cache=new Map(),candidatos=new Map(),inconclusos=[];
 function evaluate(p,k){
   const key=p+":"+k;
   if(cache.has(key))return cache.get(key);
   p2.premios.P=p;p4.premios.P=p;k5.premios.K=k;
   const out=analizarInfanciaUTN(escenario);
   cache.set(key,out);
   if(out.estado==="calculado")candidatos.set(key,{premio_P_casilleros_2_y_4:p,premio_K_casillero_5:k,rondas_esperadas:out.rondas_esperadas,error_absoluto:Math.abs(out.rondas_esperadas-meta)});
   else if(out.estado==="no_convergente"||out.estado==="limite")inconclusos.push(key);
   return out;
 }
 const initial=evaluate(0,0);
 if(initial.estado==="pendiente"||initial.estado==="limite"||initial.estado==="error")return {estado:initial.estado,faltan:initial.faltan,detalle:initial.detalle,objetivo_rondas:meta};
 for(let p=0;p<=maximo;p++){
   const lo=evaluate(p,0),hi=evaluate(p,maximo);
   if(lo.estado==="calculado"&&hi.estado==="calculado"&&lo.rondas_esperadas>=meta&&hi.rondas_esperadas<=meta){
     let l=0,r=maximo;
     while(r-l>1){
       const mid=Math.floor((l+r)/2),z=evaluate(p,mid);
       if(z.estado==="calculado"&&z.rondas_esperadas<=meta)r=mid;
       else l=mid;
     }
     evaluate(p,l);evaluate(p,r);
   }
   report({procesados:p+1,total:maximo+1,combinaciones:cache.size});
   if(p%2===1)await new Promise(resolve=>setTimeout(resolve,0));
 }
 const ordered=[...candidatos.values()].sort((a,b)=>a.error_absoluto-b.error_absoluto||
        (a.premio_P_casilleros_2_y_4+a.premio_K_casillero_5)-(b.premio_P_casilleros_2_y_4+b.premio_K_casillero_5));
 return {
   estado:ordered.length?"calculado":inconclusos.length?"inconcluso":"inalcanzable",
   objetivo_rondas:meta,lista:ordered.slice(0,8),mejor_error:ordered[0]?.error_absoluto??null,
   exacta:ordered.some(x=>x.error_absoluto<=0.01),
   minimo_explorado:ordered.length?Math.min(...ordered.map(x=>x.rondas_esperadas)):null,
   evaluaciones:cache.size,inconclusos:inconclusos.length,
   hipotesis:"Se modifican solo P en casilleros 2 y 4 (mismo premio) y K en casillero 5, con enteros de 0 al máximo elegido. Los demás parámetros permanecen idénticos. No se aplica ningún resultado automáticamente."
 };
}
function aplicarCandidatoUTN(config, propuesta) {
 const out=JSON.parse(JSON.stringify(config));
 const byId=id=>out.etapas.infancia.mecanismos.find(x=>x.id===id);
 const pp=propuesta.premio_P_casilleros_2_y_4,kk=propuesta.premio_K_casillero_5;
 if(!Number.isInteger(pp)||pp<0||!Number.isInteger(kk)||kk<0)throw Error("Candidato inválido");
 byId("i_c2").premios.P=pp;byId("i_c4").premios.P=pp;byId("i_c5").premios.K=kk;
 return out;
}
if(typeof window!=='undefined'){window.calibrarUTN=calibrarUTN;window.aplicarCandidatoUTN=aplicarCandidatoUTN;}
if(typeof module!=='undefined')module.exports={calibrarUTN,aplicarCandidatoUTN};
