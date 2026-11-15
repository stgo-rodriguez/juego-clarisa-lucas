/* Clarisa & Lucas v3.1 — MDP absorbente de Infancia/UTN. Sin Monte Carlo. */
function analizarInfanciaUTN(config, override={}) {
  const opt={...(config.supuestos?.utn_v31||{}),...override};
  const rol=opt.rol||"Clarisa", sitio=opt.posicion_inicial;
  let p0=opt.P_inicial, k0=opt.K_inicial;
  const modo=opt.modo_situaciones||"configuradas";
  const rp=config.requisitos?.utn?.P, rk=config.requisitos?.utn?.K;
  const faltan=[];
  if(!["Clarisa","Lucas"].includes(rol)) faltan.push("Rol Clarisa o Lucas");
  if(!Number.isInteger(sitio)||sitio<1||sitio>6) faltan.push("Casillero inicial de Infancia (1–6)");
  const integer=(n)=>Number.isInteger(n)&&n>=0;
  for(const [k,v] of [["P requerida",rp],["K requerido",rk],["P inicial",p0],["K inicial",k0]]){
    if((k==="P inicial"&&rp===0)||(k==="K inicial"&&rk===0))continue;
    if(v===null||v===undefined) faltan.push(k);
    else if(!integer(v)) faltan.push(k+" (entero no negativo)");
  }
  if(!["configuradas","neutras"].includes(modo)) faltan.push("Modo de Situaciones válido");
  if(faltan.length) return {estado:"pendiente",faltan,objetivo_rondas:opt.objetivo_rondas??5};
  if(rp===0)p0=0;
  if(rk===0)k0=0;
  const N=(rp+1)*(rk+1);
  if(N>625) return {estado:"limite",detalle:"El espacio P×K supera 625 estados por posición. Reducí temporalmente los requisitos o usá un solver de mayor capacidad.",estados:N};
  const cas=[];
  for(let t=1;t<=6;t++){
    const m=config.etapas?.infancia?.mecanismos?.find(x=>x.id==="i_c"+t);
    if(!m){faltan.push("Casillero "+t);continue;}
    const vP=rp===0?0:(m.premios?.P??(Object.prototype.hasOwnProperty.call(m.premios||{},"P")?null:0));
    const vK=rk===0?0:(m.premios?.K??(Object.prototype.hasOwnProperty.call(m.premios||{},"K")?null:0));
    if((rp>0&&vP===null)||(rk>0&&vK===null))faltan.push("Premio P/K del casillero "+t);
    else if(!Number.isInteger(vP)||!Number.isInteger(vK)) faltan.push("Premios P/K enteros del casillero "+t);
    cas.push({P:vP,K:vK});
  }
  let outcomes=[];
  if(modo==="neutras") outcomes=[{prob:1,P:0,K:0}];
  else {
    const situ=config.etapas.infancia.mecanismos.find(x=>x.id===(rol==="Clarisa"?"i_s_c":"i_s_l"));
    if(!situ) faltan.push("Situación de "+rol);
    else {
      const a={P:rp===0?0:situ.opcion_A?.P,K:rk===0?0:situ.opcion_A?.K},
        b={P:rp===0?0:situ.opcion_B?.P,K:rk===0?0:situ.opcion_B?.K},q=situ.probabilidad_A;
      const same=a.P!==null&&a.K!==null&&b.P!==null&&b.K!==null&&a.P===b.P&&a.K===b.K;
      if(same) outcomes=[{prob:1,P:a.P,K:a.K}];
      else if(q===null||q===undefined||!(q>=0&&q<=1))faltan.push("Probabilidad A de Situación "+rol);
      else {
        for(const [prob,v,name] of [[q,a,"A"],[1-q,b,"B"]])if(prob>0){
          if(v.P===null||v.K===null||v.P===undefined||v.K===undefined)faltan.push("Efectos P/K de la opción "+name+" · "+rol);
          else outcomes.push({prob,P:v.P,K:v.K});
        }
      }
    }
  }
  for(const s of outcomes)if(!Number.isInteger(s.P)||!Number.isInteger(s.K))faltan.push("Efectos P/K enteros de Situación");
  if(faltan.length) return {estado:"pendiente",faltan:[...new Set(faltan)],objetivo_rondas:opt.objetivo_rondas??5};
  // Truncar saldos en la cuota solo es exacto con incrementos no negativos.
  // Ante pérdidas habría que mantener estados con superávit y acotar el error.
  const hasLoss=cas.some(x=>(rp>0&&x.P<0)||(rk>0&&x.K<0))||
    outcomes.some(x=>(rp>0&&x.P<0)||(rk>0&&x.K<0));
  if(hasLoss) return {estado:"limite",detalle:"El solver v3.1 no trunca pérdidas P/K: hay efectos negativos. Para esos casos se requiere un modelo con excedentes y control del error de truncamiento.",rol,objetivo_rondas:opt.objetivo_rondas??5};
  if((rp>p0 && Math.max(...cas.map(x=>x.P),...outcomes.map(x=>x.P))<=0) ||
     (rk>k0 && Math.max(...cas.map(x=>x.K),...outcomes.map(x=>x.K))<=0))
    return {estado:"inalcanzable",rondas_esperadas:Infinity,detalle:"Al menos un recurso requerido tiene déficit inicial y ninguna fuente positiva en el modelo; no se puede aprobar UTN.",rol,objetivo_rondas:opt.objetivo_rondas??5};
  const W=rk+1, S=N, O=outcomes.length;
  const clamp=(v,lim)=>Math.max(0,Math.min(lim,v));
  const encode=(p,k)=>p*W+k;
  const idx=(state,dP,dK)=>{
    const p=Math.floor(state/W),k=state%W;
    return encode(clamp(p+dP,rp),clamp(k+dK,rk));
  };
  const succ=new Int32Array(S*O),pass=new Uint8Array(S*O),land=new Int32Array(6*S*O);
  for(let i=0;i<S;i++)for(let s=0;s<O;s++){
    const o=outcomes[s],j=i*O+s;
    succ[j]=idx(i,o.P,o.K);
    pass[j]=(Math.floor(succ[j]/W)>=rp&&(succ[j]%W)>=rk)?1:0;
    for(let d=0;d<6;d++)land[d*S*O+j]=idx(i,cas[d].P+o.P,cas[d].K+o.K);
  }
  const C=new Float64Array(6*S),U=new Float64Array(S),R=new Float64Array(S);
  const maxIter=opt.max_iteraciones||1500, tolerance=opt.tolerancia||1e-9;
  let error=Infinity,iter=0;
  for(iter=0;iter<maxIter;iter++){
    error=0;
    for(let state=S-1;state>=0;state--){
      let exam=1,back=1,enter=0;
      for(let s=0;s<O;s++){
        const z=state*O+s,ns=succ[z],w=outcomes[s].prob;
        exam+=w*(pass[z]?0.5*U[ns]:R[ns]);
        back+=w*C[4*S+ns];
        enter+=w*(pass[z]?U[ns]:R[ns]);
      }
      error=Math.max(error,Math.abs(exam-U[state]),Math.abs(back-R[state]));
      U[state]=exam;R[state]=back;
      for(let pos=0;pos<6;pos++){
        const dist=(4-pos+6)%6; // casillero UTN = índice 4
        let sum=0;
        for(let die=1;die<=6;die++){
          const dest=(pos+die)%6;
          let stay=0;
          for(let s=0;s<O;s++)stay+=outcomes[s].prob*C[dest*S+land[dest*S*O+state*O+s]];
          sum+=(die>=dist+1)?Math.min(stay,enter):stay;
        }
        const v=1+sum/6,q=pos*S+state;
        error=Math.max(error,Math.abs(v-C[q]));C[q]=v;
      }
    }
    if(error<tolerance)break;
  }
  if(error>=tolerance) return {estado:"no_convergente",detalle:"La iteración de Bellman no alcanzó la tolerancia. Puede haber una demora muy alta o una clase de estados sin acceso garantizado a UTN.",rol,residuo:error,iteraciones:iter+1,objetivo_rondas:opt.objetivo_rondas??5};
  const i0=encode(clamp(p0,rp),clamp(k0,rk)),answer=C[(sitio-1)*S+i0];
  return {estado:"calculado",rondas_esperadas:answer,objetivo_rondas:opt.objetivo_rondas??5,desviacion:answer-(opt.objetivo_rondas??5),rol,posicion_inicial:sitio,requisitos:{P:rp,K:rk},iniciales:{P:p0,K:k0},
     estados:8*S,iteraciones:iter+1,residuo:error,modelo:"MDP absorbente finito; valor esperado óptimo; programación de Bellman sin Monte Carlo",
     hipotesis:[
       "Movimiento D6 equiprobable; solo el casillero final entrega recursos.",
       "La entrada por casillero 5 consume un paso adicional; si sobra movimiento, se descarta.",
       "El jugador elige entrar o seguir el circuito para minimizar rondas esperadas, después de conocer D6 y antes de resolver Situación.",
       "La Situación se resuelve al final de cada turno de Infancia, también en el nodo UTN y en el turno de regreso.",
       "El ingreso no permite examinarse hasta el siguiente turno; cada examen tiene probabilidad 1/2 de aprobación.",
       "Si faltan requisitos tras una Situación en UTN, el próximo turno se destina a regresar al casillero 5, sin dado ni premio de casillero.",
       "Solo se modelan efectos P/K no negativos; las pérdidas requieren estados adicionales para conservar excedentes y no se estiman aquí.",
       modo==="neutras"?"Escenario experimental explícito: se omiten los efectos P/K de Situaciones. No representa el mazo real.":"Las opciones A/B se tratan como sucesos independientes por turno con probabilidades indicadas; no modela dependencia de mazo finito."
     ]};
}
if(typeof window!=='undefined')window.analizarInfanciaUTN=analizarInfanciaUTN;
if(typeof module!=='undefined')module.exports={analizarInfanciaUTN};
