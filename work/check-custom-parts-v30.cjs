const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {pathToFileURL}=require('node:url');
(async()=>{
 const browser=await chromium.launch({args:['--enable-unsafe-swiftshader','--use-angle=swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:736,height:1000},reducedMotion:'reduce'}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(pathToFileURL(process.argv[2]).href);
  const f=page.frameLocator('iframe').first(),q=id=>f.locator('#cp30-'+id),canvas=q('canvas');
  const read=()=>canvas.evaluate(async el=>{
   await new Promise(done=>requestAnimationFrame(()=>requestAnimationFrame(done)));
   const g=el.getContext('webgl'),v=new Uint8Array(el.width*el.height*4);g.readPixels(0,0,el.width,el.height,g.RGBA,g.UNSIGNED_BYTE,v);
   let count=0,hash=0;for(let i=3;i<v.length;i+=4)if(v[i]){count++;hash=(hash+v[i-2]*(i+1))%2147483647;}return[count,hash];
  });
  await q('view').locator('option').last().waitFor({state:'attached'});await q('caption').getByText(/захода оси/).waitFor();
  const options=await q('view').locator('option').evaluateAll(nodes=>nodes.map(n=>n.value));
  assert.equal(options.length,11);
  const coverage={};
  for(const view of options){await q('view').selectOption(view);coverage[view]=(await read())[0];assert.ok(coverage[view]>1000,view);
   if(['axis-l','runner-cut','ledge-cut','hinge-context','mechanism'].includes(view))await page.screenshot({path:'/tmp/custom-parts-'+view+'.png',fullPage:true});
  }
  await q('view').selectOption('mechanism');await q('progress').fill('0');const closed=await read();
  await q('progress').fill('100');assert.notEqual((await read())[1],closed[1]);
  await q('progress').fill('200');const opened=await read();assert.notEqual(opened[1],closed[1]);
  await q('neighbours').uncheck();assert.notEqual((await read())[1],opened[1]);
  await page.screenshot({path:'/tmp/custom-parts-mechanism-bare.png',fullPage:true});
  await q('view').selectOption('hinge-spacer');const normal=await read();await q('zoom').fill('250');assert.notEqual((await read())[1],normal[1]);
  await q('pan').click();assert.equal(await q('pan').getAttribute('aria-pressed'),'true');
  await page.setViewportSize({width:320,height:1000});await page.emulateMedia({colorScheme:'dark'});
  for(const view of ['axis-l','ledge-cut','runner-cut','mechanism']){await q('view').selectOption(view);assert.ok((await read())[0]>1000);assert.ok(await canvas.evaluate(e=>e.ownerDocument.documentElement.scrollWidth<=e.ownerDocument.defaultView.innerWidth));}
  await page.screenshot({path:'/tmp/custom-parts-narrow.png',fullPage:true});assert.deepEqual(errors,[]);
  if(process.argv[3])fs.writeFileSync(process.argv[3],JSON.stringify({passed:true,views:11,pixel_coverage:coverage,motion_0_100_200:true,context_toggle:true,zoom:true,narrow_dark_layout:true,javascript_exceptions:errors},null,2)+'\n');
  console.log('11 part views, right-facade motion, context, zoom, pan and narrow dark layout passed.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
