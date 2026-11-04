const {chromium}=require('playwright');
(async()=>{
 let browser;
 try {
 browser=await chromium.launch({headless:true});
 const page=await browser.newPage({viewport:{width:1000,height:700},deviceScaleFactor:1});
 const errors=[];page.on('pageerror',e=>{errors.push(e.message);console.error('Preview error:',e.message);});
 await page.goto('file://./work/spherical-cabinet-preview.html');
 const f=page.frameLocator('iframe');
 await f.locator('canvas[data-model="top"][data-rendered="true"]').waitFor({timeout:10000});
 if(await f.locator('canvas[data-rendered="true"]').count()!==3)throw Error('Expected three rendered sketches');
 await page.screenshot({path:'work/spherical-sketches.png',fullPage:true});
 await f.locator('[data-view]').selectOption('front');
 await page.screenshot({path:'work/spherical-sketches-front.png',fullPage:true});
 await f.locator('[data-height]').selectOption('1800');
 if(!(await f.locator('.sc-dimensions').textContent()).includes('180'))throw Error('Height did not update');
 await page.screenshot({path:'work/spherical-sketches-tall.png',fullPage:true});
 await f.locator('[data-view]').selectOption('perspective');
 await f.locator('[data-height]').selectOption('1200');
 await page.setViewportSize({width:360,height:800});
 await page.screenshot({path:'work/spherical-sketches-mobile.png',fullPage:true});
 const overflow=await f.locator('body').evaluate(e=>e.scrollWidth>e.clientWidth+1);
 console.log(JSON.stringify({errors,overflow,canvases:await f.locator('canvas').count()}));
 if(errors.length||overflow)process.exitCode=1;
 } finally {if(browser)await browser.close();}
})().catch(e=>{console.error(e.message);process.exitCode=1;});
