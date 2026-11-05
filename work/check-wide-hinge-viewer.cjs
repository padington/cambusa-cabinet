const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {pathToFileURL}=require('node:url');
(async()=>{
 const browser=await chromium.launch({args:['--enable-unsafe-swiftshader','--use-angle=swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:736,height:1100},reducedMotion:'reduce'}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));await page.goto(pathToFileURL(process.argv[2]).href);
  const f=page.frameLocator('iframe').first(),q=id=>f.locator('#cw170-'+id),canvas=q('canvas');
  const read=()=>canvas.evaluate(async el=>{
   await new Promise(done=>requestAnimationFrame(()=>requestAnimationFrame(done)));
   const gl=el.getContext('webgl'),p=new Uint8Array(el.width*el.height*4);gl.readPixels(0,0,el.width,el.height,gl.RGBA,gl.UNSIGNED_BYTE,p);
   let count=0,hash=0;for(let i=3;i<p.length;i+=4)if(p[i]){count++;hash=(hash+p[i-2]*(i+1))%2147483647;}
   return [count,hash];
  });
  await q('caption').getByText(/часть деталей показана схемой/).waitFor();
  assert.ok((await read())[0]>20000);assert.equal(await q('left').getAttribute('max'),'170');
  assert.equal(await q('left').inputValue(),'170');await q('reveal').uncheck();
  await page.screenshot({path:'/tmp/cambusa-wide-170-full.png',fullPage:true});
  const opened=await read();await q('left-toggle').click();assert.equal(await q('left').inputValue(),'0');
  assert.notEqual((await read())[1],opened[1]);await q('left-toggle').click();assert.equal(await q('left').inputValue(),'170');
  await q('toggle').click();assert.equal(await q('door').inputValue(),'200');
  await q('model').selectOption('hinge');assert.match(await q('caption').textContent(),/71T6650/);
  await q('left').fill('0');const hingeClosed=await read();await page.screenshot({path:'/tmp/cambusa-wide-hinge-closed.png',fullPage:true});
  await q('left').fill('170');assert.notEqual((await read())[1],hingeClosed[1]);await page.screenshot({path:'/tmp/cambusa-wide-hinge-open.png',fullPage:true});
  for(const view of ['mount','section','right','frame','corner','foot','peg','pegmount','axis-l','axis-r']){
   await q('model').selectOption(view);assert.ok((await read())[0]>3000,view);
  }
  await q('model').selectOption('peg');assert.match(await q('caption').textContent(),/глубина 16 мм/);
  await q('model').selectOption('pegmount');const inserted=await read();await q('explode').fill('100');assert.notEqual((await read())[1],inserted[1]);
  await q('zoom').fill('250');assert.equal(await q('zoom-value').textContent(),'250%');
  await page.setViewportSize({width:320,height:1100});await page.emulateMedia({colorScheme:'dark'});
  for(const view of ['full','hinge','pegmount']){
   await q('model').selectOption(view);assert.ok((await read())[0]>3000,view);
   assert.ok(await canvas.evaluate(el=>el.ownerDocument.documentElement.scrollWidth<=el.ownerDocument.defaultView.innerWidth));
  }
  await page.screenshot({path:'/tmp/cambusa-wide-narrow.png',fullPage:true});assert.deepEqual(errors,[]);
  fs.writeFileSync(process.argv[3],JSON.stringify({passed:true,checked_at:new Date().toISOString(),views:12,
   checks:['initial full model at 170 degrees','0–170 control and toggle','six-bar motion visible in hinge detail','all 12 views render','right facade control','24 mm pegboard captions and section','peg insertion/pullout','250 percent zoom','320px dark layout','no JavaScript exceptions']},null,2)+'\n');
  console.log('Wide hinge viewer: all checks passed');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
