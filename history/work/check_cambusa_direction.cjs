const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const path='./previews/cambusa-fly-direction.html';
const html=fs.readFileSync(path,'utf8');assert.ok(Buffer.byteLength(html)<1000000);assert.ok(!html.includes('__MODEL_DATA__'));
const json=html.match(/<script type="application\/json" id="cf-data">([\s\S]*?)<\/script>/)[1];
const scripts=[...html.matchAll(/<script(?:[^>]*)>([\s\S]*?)<\/script>/g)];
const ids=new Set([...html.matchAll(/\bid="([^"]+)"/g)].map(x=>x[1]));
const queried=[...scripts.at(-1)[1].matchAll(/(?:querySelector\('#|getElementById\(')([^']+)'/g)].map(x=>x[1]);
for(const id of queried)assert.ok(ids.has(id),id+' absent');
let fills=0,draws=0;const elements={};
const ctx={setTransform(){draws++},clearRect(){},beginPath(){},moveTo(x,y){assert.ok(Number.isFinite(x)&&Number.isFinite(y))},lineTo(x,y){assert.ok(Number.isFinite(x)&&Number.isFinite(y))},closePath(){},fill(){fills++}};
function el(id){return elements[id]??={value:'',checked:false,textContent:'',style:{},listeners:{},addEventListener(k,f){this.listeners[k]=f}}}
const canvas=el('cf-canvas');Object.assign(canvas,{clientWidth:736,clientHeight:570,getContext(){return ctx},setPointerCapture(){}});
const root={querySelector(q){return el(q.slice(1))}};
const document={documentElement:{},getElementById(id){if(id==='cambusa-fly-v07')return root;if(id==='cf-data')return{textContent:json};return el(id)}};
const window={devicePixelRatio:1,addEventListener(){},matchMedia(){return{addEventListener(){}}}};
class ResizeObserver{constructor(f){this.f=f}observe(){this.f()}}
class MutationObserver{constructor(f){this.f=f}observe(){}}
const getComputedStyle=()=>({color:'var(--test)'});
vm.runInNewContext(scripts.at(-1)[1],{document,window,ResizeObserver,MutationObserver,getComputedStyle,console},{timeout:10000});
for(const drawer of [0,1]){el('cf-drawer').value=drawer;el('cf-drawer').listeners.change();for(const travel of [0,140,280]){el('cf-pull').value=travel;el('cf-pull').listeners.input();if(travel>0)assert.ok(+el('cf-open').value>=145)}}
el('cf-open').value=0;el('cf-open').listeners.input();assert.equal(+el('cf-pull').value,0);
for(const active of [true,false]){el('cf-exploded').checked=active;const before=fills;el('cf-exploded').listeners.change();assert.ok(fills-before>1000)}
canvas.listeners.pointerdown({clientX:300,clientY:200,pointerId:1});canvas.listeners.pointermove({clientX:500,clientY:260});canvas.listeners.pointerup();
canvas.clientWidth=320;canvas.clientHeight=440;el('cf-yaw').value=-120;el('cf-yaw').listeners.input();
console.log(JSON.stringify({bytes:Buffer.byteLength(html),draws,all_coordinates_finite:true,queried_ids_present:true,drawer_guard_passed:true},null,2));
