const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs'),{pathToFileURL}=require('node:url');
(async()=>{
 const browser=await chromium.launch({args:['--enable-unsafe-swiftshader','--use-angle=swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:736,height:1100},reducedMotion:'reduce'}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));await page.goto(pathToFileURL(process.argv[2]).href);
  const f=page.frameLocator('iframe').first(),q=id=>f.locator('#c33h-'+id),canvas=q('canvas');
  const read=()=>canvas.evaluate(async el=>{
   await new Promise(done=>requestAnimationFrame(()=>requestAnimationFrame(done)));
   const gl=el.getContext('webgl'),p=new Uint8Array(el.width*el.height*4);gl.readPixels(0,0,el.width,el.height,gl.RGBA,gl.UNSIGNED_BYTE,p);
   let count=0,hash=0;for(let i=3;i<p.length;i+=4)if(p[i]){count++;hash=(hash+p[i-2]*(i+1))%2147483647;}
   return [count,hash];
  });
  await q('caption').getByText(/71T6650/).waitFor();assert.ok((await read())[0]>20000);
  assert.equal(await q('left').getAttribute('max'),'170');assert.equal(await q('left').inputValue(),'170');
  await page.screenshot({path:'/tmp/cambusa-v33-hinge-170.png',fullPage:true});
  const opened=await read();await q('left-toggle').click();assert.equal(await q('left').inputValue(),'0');
  assert.notEqual((await read())[1],opened[1]);await page.screenshot({path:'/tmp/cambusa-v33-hinge-0.png',fullPage:true});
  await q('left-toggle').click();assert.equal(await q('left').inputValue(),'170');
  await q('model').selectOption('doorwood');assert.match(await q('caption').textContent(),/3 выборки/);assert.ok((await read())[0]>10000);
  await page.screenshot({path:'/tmp/cambusa-v33-door-back.png',fullPage:true});
  await q('model').selectOption('full');await q('reveal').uncheck();assert.ok((await read())[0]>10000);
  await q('toggle').click();assert.equal(await q('door').inputValue(),'200');
  await page.screenshot({path:'/tmp/cambusa-v33-full.png',fullPage:true});
  for(const view of ['frame','peg']){await q('model').selectOption(view);assert.ok((await read())[0]>3000);}
  await q('model').selectOption('hinge');await q('zoom').fill('250');assert.equal(await q('zoom-value').textContent(),'250%');
  await page.setViewportSize({width:320,height:1100});await page.emulateMedia({colorScheme:'dark'});
  for(const view of ['hinge','doorwood','full']){
   await q('model').selectOption(view);assert.ok((await read())[0]>3000,view);
   assert.ok(await canvas.evaluate(el=>el.ownerDocument.documentElement.scrollWidth<=el.ownerDocument.defaultView.innerWidth));
  }
  await page.screenshot({path:'/tmp/cambusa-v33-narrow.png',fullPage:true});assert.deepEqual(errors,[]);
  fs.writeFileSync(process.argv[3],JSON.stringify({passed:true,checked_at:new Date().toISOString(),views:5,
   checks:['complete exterior supplier hardware at 170','0–170 hinge motion','wood-only rear relief view','full cabinet and right door','frame and blind pegboard','250 percent zoom','320px dark layout','no JavaScript exceptions']},null,2)+'\n');
  console.log('Full Blum viewer: passed');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
