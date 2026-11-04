const fs=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const html=fs.readFileSync('./previews/mobile-cabinet-options.html','utf8');
assert.ok(Buffer.byteLength(html)<1000000);
assert.ok(!html.includes('__MODEL_DATA__'));
const json=html.match(/<script type="application\/json" id="mc-data">([\s\S]*?)<\/script>/)[1];
const scripts=[...html.matchAll(/<script(?:[^>]*)>([\s\S]*?)<\/script>/g)];
let fills=0,draws=0;
const ctx={setTransform(){draws++},clearRect(){},beginPath(){},moveTo(x,y){assert.ok(Number.isFinite(x)&&Number.isFinite(y))},lineTo(x,y){assert.ok(Number.isFinite(x)&&Number.isFinite(y))},closePath(){},fill(){fills++}};
const elements={};
function el(id){return elements[id]??=( {value:'',checked:false,textContent:'',listeners:{},addEventListener(k,f){this.listeners[k]=f}});}
const canvas=el('mc-canvas');Object.assign(canvas,{clientWidth:736,clientHeight:540,getContext(){return ctx},setPointerCapture(){}});
const root={querySelector(q){return el(q.slice(1))}};
const document={getElementById(id){if(id==='mobile-cabinet-v04')return root;if(id==='mc-data')return{textContent:json};return el(id)}};
const window={devicePixelRatio:1,addEventListener(){}};
class ResizeObserver{constructor(f){this.f=f}observe(){this.f()}}
vm.runInNewContext(scripts.at(-1)[1],{document,window,ResizeObserver,console},{timeout:10000});
const records=[];
for(const variant of ['clean','aluminium','wedge']){
  el('mc-variant').value=variant;el('mc-variant').listeners.change();
  for(const a of [0,45,90]){
    el('mc-open').value=a;el('mc-open').listeners.input();
    for(const e of [false,true]){
      const before=fills;el('mc-explode').checked=e;el('mc-explode').listeners.change();
      assert.ok(fills-before>100);records.push({variant,doors:a,exploded:e,triangles:fills-before});
    }
  }
}
canvas.listeners.pointerdown({clientX:300,clientY:200,pointerId:1});
canvas.listeners.pointermove({clientX:500,clientY:260});canvas.listeners.pointerup();
assert.ok(Number(el('mc-rotate').value)!==27);
canvas.clientWidth=320;canvas.clientHeight=430;el('mc-rotate').value=-120;el('mc-rotate').listeners.input();
console.log(JSON.stringify({bytes:Buffer.byteLength(html),draws,states:records.length,allFinite:true,records},null,2));
