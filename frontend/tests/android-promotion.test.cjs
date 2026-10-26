const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {execFileSync} = require('node:child_process');
const root = path.resolve(__dirname, '..');
test('production build always includes Android promotion after homepage restore', () => {
 const build = fs.readFileSync(path.join(root,'scripts/build-site.js'),'utf8');
 assert.ok(build.indexOf("require('./enhance-article-promotion')") > build.indexOf('fs.writeFileSync(homepagePath, homepageContents)'));
});
test('promotion survives repeat generation with one banner and page-specific copy', () => {
 const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'myrecon-promotion-'));
 try {
 fs.mkdirSync(path.join(tmp,'scripts'));
 fs.copyFileSync(path.join(root,'scripts/enhance-article-promotion.js'),path.join(tmp,'scripts/enhance-article-promotion.js'));
 const routes={'index.html':'Your next discovery.','services.html':'Know your footprint.','breaches/example.html':'Big breaches.','breaches/case-files/example.html':'Real breaches.','blog/example.html':'From reading.'};
 for(const route of Object.keys(routes)){const file=path.join(tmp,route);fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file,'<html><head></head><body><main><h1>Original page</h1><p>Original content</p></main></body></html>');}
 const run=()=>execFileSync(process.execPath,[path.join(tmp,'scripts/enhance-article-promotion.js')]);run();run();
 for(const [route,copy] of Object.entries(routes)){const html=fs.readFileSync(path.join(tmp,route),'utf8');assert.equal((html.match(/class="android-promo"/g)||[]).length,1,route);assert.ok(html.includes(copy),route);assert.ok(html.includes('Original content'));assert.ok(html.includes('id=com.Myrecon.osint'));assert.equal((html.match(/class="promo-layout"/g)||[]).length,route==='index.html'?0:1);}
 } finally {fs.rmSync(tmp,{recursive:true,force:true});}
});
