const fs=require('fs'),vm=require('vm');
const path='./previews/cabinet-after-references.html';
const html=fs.readFileSync(path,'utf8'),src=html.match(/<script>([\s\S]*?)<\/script>/)[1];
new vm.Script(src);
const palette={'--cr-wood':'ddbd8e','--cr-back':'c4a06c','--cr-terracotta':'b85b3d','--cr-blue':'82b8d6','--cr-lilac':'b0a0c9','--cr-green':'416d57','--cr-yellow':'d3ae35','--cr-graphite':'494b4a','--cr-book':'ece4d3'};
const context={state:{open:false},color:name=>palette[name].match(/../g).map(v=>parseInt(v,16)/255)};
vm.createContext(context);vm.runInContext(src.slice(src.indexOf('function geometry'),src.indexOf('function makeRenderer')),context);
const meshes={};let checked=0;
for(const height of [1200,1500,1800])for(const open of [false,true])for(const kind of ['cassette','gallery','workshop']){
  context.state.open=open;const m=context.build(kind,height);
  for(const attr of ['position','normal','color','material'])if(!m[attr].every(Number.isFinite))throw Error('Non-finite '+attr);
  if(m.position.length!==m.normal.length||m.position.length!==m.color.length||m.material.length*3!==m.position.length)throw Error('Attribute mismatch');
  const zs=m.position.filter((_,i)=>i%3===2);if(Math.min(...zs)<-.01||Math.max(...zs)>height+.01)throw Error('Wrong height');
  checked++;if(height===1200)meshes[kind+(open?'-open':'')]=m;
}
fs.writeFileSync('work/reference-design-meshes.json',JSON.stringify(meshes));
console.log(JSON.stringify({syntax:'ok',geometryConfigurations:checked,vertices:Object.fromEntries(Object.entries(meshes).map(([k,v])=>[k,v.position.length/3])),fragmentBytes:Buffer.byteLength(html)}));
