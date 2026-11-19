import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {JSDOM} from 'jsdom';
import {extractProduct} from '../extractor.mjs';
import {validateBrowserImport,productReferenceFromUrl} from '../../frontend/lib/browser-import.mjs';

const source='https://shopee.co.th/product/1873957794/45613484259';
const ids={shop_id:'1873957794',item_id:'45613484259'};
function page(content,url=source){
 const dom=new JSDOM(content,{url});
 dom.window.HTMLElement.prototype.getClientRects=function(){return [{width:100,height:20}]};
 for(const key of ['document','location','DOMParser','NodeFilter'])globalThis[key]=dom.window[key];
 globalThis.getComputedStyle=dom.window.getComputedStyle.bind(dom.window);
 return dom;
}
function fixture(extra=''){
 return `<main><section itemtype="https://schema.org/Product"><h1>ม่านบังแดดรถยนต์</h1><div data-testid="product-price">฿125.50</div><p>Coupon ฿5</p><h2>Product Specifications</h2><h3>Category</h3><p>Automotive</p><h3>Brand</h3><p>Example Brand</p><h2>Product Description</h2><p>Visible product description.</p><p hidden>PRIVATE HIDDEN TEXT</p><input type="password" value="PRIVATE PASSWORD"><textarea>PRIVATE FORM DATA</textarea>${extra}</section><h3>Related products</h3><div data-testid="product-price">฿9999</div><p>Not the main product.</p></main>`;
}

test('reads the displayed product and imports it without affiliate URL changes',()=>{
 const dom=page(fixture());const original='https://s.shopee.co.th/AAIrCm9rvZ?share_channel_code=6';
 const result=extractProduct();assert.equal(result.ok,true);assert.equal(result.data.name,'ม่านบังแดดรถยนต์');assert.equal(result.data.price,125.5);
 assert.equal(result.data.description,'Visible product description.');assert.equal(result.data.brand,'Example Brand');assert.equal(result.data.category,'Automotive');
 const exported=JSON.stringify(result);assert.ok(!exported.includes('PRIVATE'));assert.ok(!result.data.description.includes('Related'));
 const imported=validateBrowserImport(exported,ids);const form={url:original,...imported.data};
 assert.equal(form.url,original);assert.equal(form.price,125.5);assert.ok(!('images' in imported.data));dom.window.close();
});

test('does not invent a price from coupon or related products',()=>{
 const dom=page(fixture().replace('<div data-testid="product-price">฿125.50</div>',''));
 const result=extractProduct();assert.equal(result.ok,true);assert.ok(!('price' in result.data));assert.ok(result.warnings.some(x=>x.includes('price')));dom.window.close();
});

test('reads matching structured offers and ignores other-product offers',()=>{
 const metadata=[{'@type':'Product',url:'https://shopee.co.th/product/1/2',name:'Related',offers:{price:999,priceCurrency:'THB'}},{'@type':'Product',url:source,name:'ม่านบังแดดรถยนต์',offers:{price:'199.00',priceCurrency:'THB',seller:{name:'Actual shop'}}}];
 const dom=page(fixture()+`<script type="application/ld+json">${JSON.stringify(metadata)}</script>`);
 const result=extractProduct();assert.equal(result.data.price,199);assert.equal(result.data.shop,'Actual shop');dom.window.close();
});

test('serialized extractor works without module closure, as required by scripting API',()=>{
 const dom=page(fixture());const isolated=Function('return ('+extractProduct.toString()+')')();
 assert.equal(isolated().data.name,'ม่านบังแดดรถยนต์');dom.window.close();
});

for(const url of ['https://shopee.co.th/verify/traffic/error','https://shopee.co.th/buyer/login','https://evil.example/product/1873957794/45613484259','http://shopee.co.th/product/1873957794/45613484259']){
 test('rejects non-product or untrusted location: '+url,()=>{const dom=page(fixture(),url);assert.equal(extractProduct().ok,false);dom.window.close()});
}

test('does not export a page without a visible product heading',()=>{
 const dom=page('<h1 hidden>Hidden product</h1><p>Please sign in</p>');assert.equal(extractProduct().ok,false);dom.window.close();
});

test('Studio rejects mismatched product IDs, forged source URLs and wrong versions',()=>{
 const dom=page(fixture());const payload=extractProduct();
 assert.throws(()=>validateBrowserImport(JSON.stringify(payload),{...ids,item_id:'1'}),/different product/);
 assert.throws(()=>validateBrowserImport(JSON.stringify({...payload,source_url:'https://evil.example/product/1873957794/45613484259'}),ids),/different product/);
 assert.throws(()=>validateBrowserImport(JSON.stringify({...payload,version:2}),ids),/not a supported/);
 assert.throws(()=>validateBrowserImport(JSON.stringify(payload),null),/resolve/);dom.window.close();
});

test('Studio caps input and imports only whitelisted product fields',()=>{
 const dom=page(fixture());const payload=extractProduct();payload.data.url='https://evil.example/';payload.data.images=['https://evil.example/image'];
 payload.data.__proto__={polluted:true};const result=validateBrowserImport(JSON.stringify(payload),ids);
 assert.ok(!('url' in result.data));assert.ok(!('images' in result.data));assert.equal({}.polluted,undefined);
 assert.throws(()=>validateBrowserImport('x'.repeat(65537),ids),/limit/);
 assert.throws(()=>validateBrowserImport(JSON.stringify({...payload,data:{name:'A',price:-1}}),ids),/price/);
 assert.throws(()=>validateBrowserImport(JSON.stringify({...payload,data:{name:'A',description:'x'.repeat(10001)}}),ids),/description/);dom.window.close();
});

test('helper is limited to active-tab reads and cannot send network requests',()=>{
 const manifest=JSON.parse(readFileSync(new URL('../manifest.json',import.meta.url)));
 assert.deepEqual(manifest.permissions,['activeTab','scripting']);assert.ok(!manifest.host_permissions);assert.ok(!manifest.background);assert.ok(!manifest.content_scripts);
 assert.ok(manifest.content_security_policy.extension_pages.includes("connect-src 'none'"));
 const scripts=readFileSync(new URL('../extractor.mjs',import.meta.url),'utf8')+readFileSync(new URL('../popup.mjs',import.meta.url),'utf8');
 assert.ok(!/document\.cookie|localStorage|chrome\.cookies|\bfetch\s*\(/.test(scripts));
 assert.deepEqual(productReferenceFromUrl(source),ids);
});
