const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {pathToFileURL}=require('node:url');
const preview=process.argv[2];
if(!preview)throw new Error('Usage: node work/check-v30-viewer.cjs /absolute/standalone-preview.html [result.json]');
(async()=>{
 const browser=await chromium.launch({args:['--enable-unsafe-swiftshader','--use-angle=swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:736,height:1100},reducedMotion:'reduce'}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));await page.goto(pathToFileURL(preview).href);
  const f=page.frameLocator('iframe').first(),q=id=>f.locator('#c30-'+id),canvas=q('canvas');
  const read=()=>canvas.evaluate(async el=>{
   await new Promise(done=>requestAnimationFrame(()=>requestAnimationFrame(done)));
   const gl=el.getContext('webgl'),p=new Uint8Array(el.width*el.height*4);gl.readPixels(0,0,el.width,el.height,gl.RGBA,gl.UNSIGNED_BYTE,p);
   let count=0,hash=0;for(let i=3;i<p.length;i+=4)if(p[i]){count++;hash=(hash+p[i-2]*(i+1))%2147483647;}
   return [count,hash];
  });
  await q('caption').getByText(/1800 мм/).waitFor();assert.ok((await read())[0]>20000);
  assert.equal(await q('left').getAttribute('max'),'110');assert.equal(await q('markers').locator('circle').count(),8);
  await q('reveal').uncheck();await q('left-toggle').click();assert.equal(await q('left').inputValue(),'110');
  await q('toggle').click();assert.equal(await q('door').inputValue(),'200');
  await page.screenshot({path:'/tmp/cambusa-v30-open.png',fullPage:true});
  await q('model').selectOption('right');assert.match(await q('caption').textContent(),/404/);assert.ok((await read())[0]>20000);
  await page.screenshot({path:'/tmp/cambusa-v30-right.png',fullPage:true});
  await q('yaw').fill('-51');await page.screenshot({path:'/tmp/cambusa-v30-right-reverse.png',fullPage:true});
  await q('model').selectOption('mount');await q('explode').fill('0');await read();
  assert.equal(await q('markers').locator('circle').count(),5);assert.ok(await q('legend').isVisible());
  await page.screenshot({path:'/tmp/cambusa-v30-mount.png',fullPage:true});
  await q('model').selectOption('section');await q('explode').fill('0');const joined=await read();
  await page.screenshot({path:'/tmp/cambusa-v30-section.png',fullPage:true});
  await q('explode').fill('100');assert.notEqual((await read())[1],joined[1]);
  await page.screenshot({path:'/tmp/cambusa-v30-exploded.png',fullPage:true});
  await q('model').selectOption('peg');assert.match(await q('caption').textContent(),/152 глухих/);await read();
  await page.screenshot({path:'/tmp/cambusa-v30-peg.png',fullPage:true});
  await q('model').selectOption('pegmount');assert.ok((await read())[0]>10000);
  await page.screenshot({path:'/tmp/cambusa-v30-peg-section.png',fullPage:true});
  const inserted=await read();await q('explode').fill('100');assert.notEqual((await read())[1],inserted[1]);await q('explode').fill('0');
  await q('model').selectOption('hinge');await q('left').fill('0');const hingeClosed=await read();
  await page.screenshot({path:'/tmp/cambusa-v30-hinge-closed.png',fullPage:true});
  await q('left').fill('110');assert.notEqual((await read())[1],hingeClosed[1]);
  await page.screenshot({path:'/tmp/cambusa-v30-hinge-open.png',fullPage:true});
  for(const key of ['frame','corner','foot']){await q('model').selectOption(key);assert.ok((await read())[0]>3000);}
  await q('zoom').fill('250');assert.equal(await q('zoom-value').textContent(),'250%');
  await page.setViewportSize({width:320,height:1100});await page.emulateMedia({colorScheme:'dark'});
  for(const view of ['right','section','hinge','pegmount']){
   await q('model').selectOption(view);if(view==='section')await q('explode').fill('0');assert.ok((await read())[0]>3000,view);
   assert.ok(await canvas.evaluate(el=>el.ownerDocument.documentElement.scrollWidth<=el.ownerDocument.defaultView.innerWidth));
  }
  await page.screenshot({path:'/tmp/cambusa-v30-narrow.png',fullPage:true});
  assert.deepEqual(errors,[]);
  if(process.argv[3])fs.writeFileSync(process.argv[3],JSON.stringify({version:'cambusa-v30-review-fixes',passed:true,checked_at:new Date().toISOString(),views:10,checks:['initial rendered mesh','8 full-assembly mount markers','left facade range 0–110','right facade control','right shelf 404 mm caption','5 mount/section labels','exploded section geometry','152 blind-hole caption','peg insertion/pullout','four-bar hinge motion','frame/corner/foot rendering','250 percent zoom','320 px dark layout without horizontal overflow','no JavaScript exceptions']},null,2)+'\n');
  console.log('v30: all ten views, physical support context, 5 part labels, blind peg detail, four-bar hinge 0–110, both doors, zoom and 320px dark layout passed.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
