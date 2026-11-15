/* Crea un escenario de ejemplo EXCLUSIVAMENTE experimental para la guía UTN.
 * No modifica el catálogo de origen ni fija premios oficiales del juego. */
function crearEscenarioGuiaUTN(catalogo){
  if(!catalogo?.supuestos?.utn_v31||!catalogo?.requisitos?.utn||
     !Array.isArray(catalogo?.etapas?.infancia?.mecanismos))
    throw new Error('El catálogo de UTN v3.1 no está disponible.');
  const escenario=JSON.parse(JSON.stringify(catalogo));
  Object.assign(escenario.supuestos.utn_v31,{
    rol:'Clarisa',posicion_inicial:5,P_inicial:0,K_inicial:0,
    modo_situaciones:'neutras',objetivo_rondas:5,maximo_premio_exploracion:12
  });
  escenario.requisitos.utn.P=1;
  escenario.requisitos.utn.K=1;
  for(const [id,recurso] of [['i_c2','P'],['i_c4','P'],['i_c5','K']]){
    const tile=escenario.etapas.infancia.mecanismos.find(m=>m.id===id);
    if(!tile||!tile.premios||!Object.hasOwn(tile.premios,recurso))
      throw new Error('El casillero '+id+' no existe en el catálogo.');
    tile.premios[recurso]=0;
  }
  return escenario;
}
if(typeof window!=='undefined')window.crearEscenarioGuiaUTN=crearEscenarioGuiaUTN;
if(typeof module!=='undefined')module.exports={crearEscenarioGuiaUTN};
