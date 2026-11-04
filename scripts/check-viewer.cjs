const { chromium } = require('playwright');
const { strict: assert } = require('node:assert');
const { pathToFileURL } = require('node:url');
const { resolve } = require('node:path');
(async () => {
  const target = process.argv[2] || pathToFileURL(resolve('docs/index.html')).href;
  const browser = await chromium.launch({args:['--enable-unsafe-swiftshader','--use-angle=swiftshader']});
  try {
    const page = await browser.newPage({viewport:{width:736,height:860}});
    const errors = [];
    page.on('pageerror',error => errors.push(error.message));
    await page.goto(target);
    const status = page.locator('#v16-status');
    await status.getByText('1000 × 1800 × 500 мм',{exact:false}).waitFor();
    const canvas = page.locator('#v16-canvas');
    const fingerprint = () => canvas.evaluate(canvas => {
      const gl = canvas.getContext('webgl');
      const pixels = new Uint8Array(canvas.width*canvas.height*4);
      gl.readPixels(0,0,canvas.width,canvas.height,gl.RGBA,gl.UNSIGNED_BYTE,pixels);
      let filled=0, score=0;
      for (let i=3; i<pixels.length; i+=4) {
        if (pixels[i]>0) {filled++; score = (score + pixels[i-1]*(i+1)) % 2147483647;}
      }
      return {filled,score};
    });
    const closed = await fingerprint();
    assert.ok(closed.filled > 20000);
    await page.locator('#v16-mode').selectOption('open');
    assert.match(await status.innerText(), /180°/);
    const opened = await fingerprint();
    assert.ok(opened.filled > 20000 && opened.score !== closed.score);
    await page.locator('#v16-mode').selectOption('frame');
    const frame = await fingerprint();
    assert.ok(frame.filled > 1000 && frame.filled < opened.filled);
    await page.locator('#v16-yaw').fill('-33');
    assert.notEqual((await fingerprint()).score, frame.score);
    await page.setViewportSize({width:320,height:760});
    await page.emulateMedia({colorScheme:'dark'});
    await page.locator('#v16-mode').selectOption('closed');
    assert.ok((await fingerprint()).filled > 12000);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),true);
    assert.deepEqual(errors,[]);
    if (process.argv[3]) await page.screenshot({path:process.argv[3],fullPage:true});
    console.log('3 вида, поворот, тёмная тема и 320 px проверены:',target);
  } finally {
    await browser.close();
  }
})().catch(error => {console.error(error); process.exitCode=1;});
