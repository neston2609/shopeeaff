export function productReferenceFromUrl(value){
 try{
  const url=new URL(value);
  if(url.protocol!=='https:'||!['shopee.co.th','www.shopee.co.th'].includes(url.hostname)||url.username||url.password||url.port&&url.port!=='443')return null;
  const match=url.pathname.match(/^\/(?:product|opaanlp)\/(\d+)\/(\d+)\/?$/)||url.pathname.match(/-i\.(\d+)\.(\d+)\/?$/);
  return match?{shop_id:match[1],item_id:match[2]}:null;
 }catch{return null}
}

export function validateBrowserImport(text,expected){
 if(typeof text!=='string'||text.length>65536)throw new Error('Product data exceeds the import limit.');
 let payload;try{payload=JSON.parse(text)}catch{throw new Error('Paste the JSON exported by Shopee Product Import, or upload its JSON file.');}
 if(!payload||payload.type!=='shopee_aff_browser_product'||payload.version!==1||payload.ok!==true)throw new Error('This is not a supported Shopee Product Import file.');
 if(!expected?.shop_id||!expected?.item_id)throw new Error('Use Fetch Information to resolve your affiliate link before importing browser data.');
 const actual=productReferenceFromUrl(payload.source_url);
 if(!actual||actual.shop_id!==String(expected.shop_id)||actual.item_id!==String(expected.item_id)||payload.product_reference?.shop_id!==actual.shop_id||payload.product_reference?.item_id!==actual.item_id)
  throw new Error('This data belongs to a different product. Open the product page resolved from your current affiliate link and read it again.');
 if(!payload.data||typeof payload.data!=='object'||Array.isArray(payload.data))throw new Error('Product fields are missing.');
 const data={};
 for(const [key,max] of Object.entries({name:200,shop:200,brand:200,category:200,description:10000,specifications:4000})){
  const value=payload.data[key];
  if(value===undefined)continue;
  if(typeof value!=='string'||value.length>max)throw new Error('Invalid imported '+key+'.');
  if(value.trim())data[key]=value.trim();
 }
 if(!data.name)throw new Error('The exported product has no name.');
 if(payload.data.price!==undefined){
  if(typeof payload.data.price!=='number'||!Number.isFinite(payload.data.price)||payload.data.price<0||payload.data.price>10000000)throw new Error('Invalid imported price.');
  data.price=payload.data.price;
 }
 const warnings=Array.isArray(payload.warnings)?payload.warnings.filter(v=>typeof v==='string').slice(0,6).map(v=>v.slice(0,400)):[];
 return {data,fields:Object.keys(data),warnings,source_url:payload.source_url};
}
