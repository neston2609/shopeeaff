// Serialized by chrome.scripting: all helpers must remain inside this function.
export function extractProduct(){
 const fail=message=>({ok:false,message});
 const reference=value=>{
  try{const u=new URL(value);if(u.protocol!=='https:'||!['shopee.co.th','www.shopee.co.th'].includes(u.hostname)||u.username||u.password||u.port&&u.port!=='443')return null;
   const m=u.pathname.match(/^\/(?:product|opaanlp)\/(\d+)\/(\d+)\/?$/)||u.pathname.match(/-i\.(\d+)\.(\d+)\/?$/);
   return m?{shop_id:m[1],item_id:m[2]}:null;
  }catch{return null}
 };
 const ids=reference(location.href);
 if(!ids)return fail('Open the actual Shopee product page after signing in. Login, verification and search pages cannot be imported.');
 const tidy=(value,max)=>typeof value==='string'?value.replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/g,'').replace(/[ \t]+/g,' ').trim().slice(0,max):'';
 const plain=(value,max)=>{
  if(typeof value!=='string')return '';
  // Decode text without parsing resource-loading elements or inserting anything into the page.
  const text=value.replace(/<(script|style|noscript|template)\b[^>]*>[\s\S]*?<\/\1\s*>/gi,'').replace(/<[^>]*>/g,' ');
  const entities={amp:'&',lt:'<',gt:'>',quot:'"',apos:"'",nbsp:' '};
  return tidy(text.replace(/&(#x[0-9a-f]+|#\d+|amp|lt|gt|quot|apos|nbsp);/gi,(all,key)=>{
   if(key[0]!=='#')return entities[key.toLowerCase()]||all;
   const n=key[1]?.toLowerCase()==='x'?parseInt(key.slice(2),16):Number(key.slice(1));
   return Number.isInteger(n)&&n>0&&n<=0x10ffff?String.fromCodePoint(n):all;
  }),max);
 };
 const visible=element=>{
  if(!element||element.closest('script,style,noscript,template,input,textarea,select,[aria-hidden="true"],[hidden]'))return false;
  for(let e=element;e&&e!==document.documentElement;e=e.parentElement){const s=getComputedStyle(e);if(s.display==='none'||s.visibility==='hidden'||s.visibility==='collapse'||s.opacity==='0')return false}
  return element.getClientRects().length>0;
 };
 const heading=Array.from(document.querySelectorAll('h1')).find(visible);
 const name=tidy(heading?.innerText||heading?.textContent||'',200);
 if(!name||/^(shopee|login|sign in|เข้าสู่ระบบ|ต้องเข้าสู่ระบบ)$/i.test(name))return fail('Product details are not displayed. Sign in to Shopee yourself, finish any verification, and reopen the product page before reading it.');
 const headings=Array.from(document.querySelectorAll('h2,h3,[role="heading"]')).filter(visible);
 const afterHeading=(labels,max,includeSubheadings=false)=>{
  const start=headings.find(h=>labels.includes(tidy(h.innerText||h.textContent||'',100).toLowerCase()));
  if(!start)return '';
  const startIndex=headings.indexOf(start);
  const end=headings.slice(startIndex+1).find(h=>!includeSubheadings||h.tagName==='H2');
  const range=document.createRange();range.setStartAfter(start);if(end)range.setEndBefore(end);else range.setEndAfter(document.body.lastChild||start);
  const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);const pieces=[];let node;
  while((node=walker.nextNode())){
   if(range.intersectsNode(node)&&visible(node.parentElement)){
    const text=tidy(node.nodeValue||'',max);if(text)pieces.push(text);
    if(pieces.join('\n').length>=max)break;
   }
  }
  return pieces.join('\n').slice(0,max);
 };
 const data={name};
 const description=afterHeading(['รายละเอียดสินค้า','product description'],10000);
 if(description)data.description=description;
 const specifications=afterHeading(['ข้อมูลจำเพาะของสินค้า','product specifications'],4000,true);
 if(specifications)data.specifications=specifications;
 const category=afterHeading(['หมวดหมู่','category'],200);
 if(category)data.category=category.replace(/\n/g,' > ');
 const brand=afterHeading(['ยี่ห้อ','แบรนด์','brand'],200);
 if(brand)data.brand=brand;
 const products=[];let count=0;
 function visit(value,depth=0){
  if(++count>500||depth>8)return;
  if(Array.isArray(value)){value.forEach(v=>visit(v,depth+1));return}
  if(!value||typeof value!=='object')return;
  const types=Array.isArray(value['@type'])?value['@type']:[value['@type']];
  if(types.some(t=>['Product','https://schema.org/Product','http://schema.org/Product'].includes(t))){products.push(value);return}
  for(const key of ['@graph','mainEntity','itemListElement','item'])visit(value[key],depth+1);
 }
 document.querySelectorAll('script[type="application/ld+json"]').forEach(script=>{try{if(script.textContent.length<=1000000)visit(JSON.parse(script.textContent))}catch{}});
 const schema=products.find(p=>{
  const productIds=reference(p.url||p['@id']);
  return productIds?productIds.shop_id===ids.shop_id&&productIds.item_id===ids.item_id:tidy(p.name,200)===name;
 });
 const warnings=[];
 if(schema){
  if(!data.description&&plain(schema.description,10000))data.description=plain(schema.description,10000);
  if(!data.brand){const b=typeof schema.brand==='object'?schema.brand?.name:schema.brand;if(tidy(b,200))data.brand=tidy(b,200)}
  if(!data.category&&tidy(schema.category,200))data.category=tidy(schema.category,200);
  const offer=(Array.isArray(schema.offers)?schema.offers[0]:schema.offers)||{};
  const price=Number(String(offer.price??offer.lowPrice??'').replace(/,/g,''));
  if(offer.priceCurrency==='THB'&&(offer.price!==undefined||offer.lowPrice!==undefined)&&Number.isFinite(price)&&price>=0&&price<=10000000){data.price=price;if(offer.price===undefined)warnings.push('Price is the lowest listed variant price. Review the selected variant.');}
  const shop=typeof offer.seller==='object'?offer.seller?.name:offer.seller;
  if(tidy(shop,200))data.shop=tidy(shop,200);
 }
 if(data.price===undefined){
  // Only explicit price markup near the main product; never coupon or recommendation prices.
  const root=heading.closest('[itemtype*="Product"],section,[class*="product-briefing"]')||heading.parentElement?.parentElement;
  const candidates=Array.from(root?.querySelectorAll('[itemprop="price"],[data-testid="product-price"]')||[]).filter(visible);
  if(candidates.length===1){
   const text=tidy(candidates[0].innerText||candidates[0].textContent||'',100);
   const match=text.match(/^(?:฿|THB)\s*([\d,]+(?:\.\d{1,2})?)$/i);
   if(match){const price=Number(match[1].replace(/,/g,''));if(Number.isFinite(price)&&price>=0&&price<=10000000)data.price=price}
  }
 }
 if(data.price===undefined)warnings.push('No unambiguous product price was available. Enter and verify the price manually.');
 if(!data.description)warnings.push('No product description was displayed. Expand the description and read the page again if needed.');
 warnings.push('Review all product claims, price and variant before saving. Images are not imported.');
 return {ok:true,type:'shopee_aff_browser_product',version:1,source_url:`https://shopee.co.th/product/${ids.shop_id}/${ids.item_id}`,product_reference:ids,data,fields:Object.keys(data),warnings,captured_at:new Date().toISOString()};
}
