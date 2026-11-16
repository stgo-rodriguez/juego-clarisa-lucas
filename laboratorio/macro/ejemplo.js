/* Únicamente ejercicio ilustrativo — cantidades NO reglamentarias. */
(function(root){
"use strict";
function crearEjemploMacro(catalogo){
 const c=JSON.parse(JSON.stringify(catalogo));
 const dados={
  infancia:{casilleros:[1,3,0],cartas:[1,2,1],otros:[0,0,0],objetivos:{utn:10},duracion:5},
  juventud:{casilleros:[0.7,3,0],cartas:[1,2,0.8],perfiles:[0.25,4,0],otros:[0,0,0],
    objetivos:{titulo:6,pasaporte:5,vuelo:4},duracion:9},
  adultez:{casilleros:[0.8,4,0],cartas:[1,2,1.4],perfiles:[0.1,3,0],otros:[0,0,0],
    objetivos:{casa:9,boda:7,falso:8},duracion:11}
 };
 for(const [st,stage] of Object.entries(c.etapas)){
   const conf=dados[st];
   stage.duracion_objetivo=conf.duracion;
   for(const m of stage.mecanismos){
     const v=conf[m.id];if(!v)continue;
     [m.frecuencia,m.ganancia,m.perdida]=v;
   }
   for(const g of stage.objetivos)g.multiplicador=conf.objetivos[g.id]??null;
 }
 c.origen="ESCENARIO DEMOSTRATIVO: cantidades inventadas únicamente para practicar; no usar como reglamento.";
 c.es_demostracion=true;
 return c;
}
if(typeof module!=="undefined"&&module.exports)module.exports={crearEjemploMacro};
if(root)root.crearEjemploMacro=crearEjemploMacro;
})(typeof window!=="undefined"?window:null);
