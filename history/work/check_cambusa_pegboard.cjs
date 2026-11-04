const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=fs.readFileSync('./previews/cambusa-pegboard.html','utf8');
assert.ok(Buffer.byteLength(html)<1000000);assert.ok(!html.includes('__MODEL_DATA__'));
const json=html.match(/<script type="application\/json" id="mc-data">([\s\S]*?)<\/script>/)[1],scripts=[...html.matchAll(/<script(?:[^>]*)>([\s\S]*?)<\/script>/g)];
let fills=0,draws=0;
const ctx={setTransform(){draws++},clearRect(){},beginPath(){},moveTo(x,y){assert.ok(Number.isFinite(x)&&Number.isFinite(y))},lineTo(x,y){assert.ok(Number.isFinite(x)&&Number.isFinite(y))},closePath(){},fill(){fills++}};
const elements={};function el(id){return elements[id]??={value:'',checked:false,textContent:'',listeners:{},addEventListener(k,f){this.listeners[k]=f}}}
const canvas=el('mc-canvas');Object.assign(canvas,{clientWidth:736,clientHeight:550,getContext(){return ctx},setPointerCapture(){}});
const root={querySelector(q){return el(q.slice(1))}},document={getElementById(id){if(id==='cambusa-pegboard-v05')return root;if(id==='mc-data')return{textContent:json};return el(id)}};
const window={devicePixelRatio:1,addEventListener(){}};class ResizeObserver{constructor(f){this.f=f}observe(){this.f()}}
vm.runInNewContext(scripts.at(-1)[1],{document,window,ResizeObserver,console},{timeout:10000});
let states=0;
for(const variant of ['outside','inside']){
  el('mc-variant').value=variant;el('mc-variant').listeners.change();
  for(const drawer of [0,1]){
    el('mc-drawer').value=drawer;el('mc-drawer').listeners.change();
    for(const travel of [0,140,280]){
      el('mc-pull').value=travel;el('mc-pull').listeners.input();
      if(variant==='inside'&&travel>0)assert.ok(+el('mc-open').value>=95);
      for(const accessories of [false,true]){const before=fills;el('mc-accessories').checked=accessories;el('mc-accessories').listeners.change();assert.ok(fills-before>1000);states++;}
    }
  }
}
el('mc-variant').value='inside';el('mc-variant').listeners.change();el('mc-open').value=0;el('mc-open').listeners.input();assert.equal(+el('mc-pull').value,0);
canvas.listeners.pointerdown({clientX:300,clientY:200,pointerId:1});canvas.listeners.pointermove({clientX:500,clientY:260});canvas.listeners.pointerup();
canvas.clientWidth=320;canvas.clientHeight=440;el('mc-rotate').value=-120;el('mc-rotate').listeners.input();
console.log(JSON.stringify({bytes:Buffer.byteLength(html),draws,interaction_states:states,all_coordinates_finite:true,door_drawer_guard_passed:true},null,2));
