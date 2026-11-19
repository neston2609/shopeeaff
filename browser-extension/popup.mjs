import {extractProduct} from './extractor.mjs';
const element=id=>document.getElementById(id);let payload=null;
element('read').addEventListener('click',async()=>{
 element('read').disabled=true;element('status').textContent='Reading the current product…';element('preview').hidden=true;payload=null;
 try{
  const [tab]=await chrome.tabs.query({active:true,currentWindow:true});
  if(!tab?.id)throw new Error('Select a Shopee product tab first.');
  const [execution]=await chrome.scripting.executeScript({target:{tabId:tab.id},func:extractProduct});
  const result=execution?.result;
  if(!result?.ok)throw new Error(result?.message||'Could not read product information.');
  payload=result;element('name').textContent=result.data.name;element('fields').textContent='Available fields: '+result.fields.join(', ');
  element('warnings').replaceChildren(...result.warnings.map(text=>{const li=document.createElement('li');li.textContent=text;return li}));
  element('json').value=JSON.stringify(result,null,2);element('preview').hidden=false;element('status').textContent='Product read. Review it, then copy or download the data.';
 }catch(error){element('status').textContent=error.message||'Could not read this page.'}finally{element('read').disabled=false}
});
element('copy').addEventListener('click',async()=>{if(!payload)return;try{await navigator.clipboard.writeText(JSON.stringify(payload));element('status').textContent='Copied. Paste this into Import from Chrome in Studio.'}catch{element('status').textContent='Clipboard unavailable. Use Download JSON instead.'}});
element('download').addEventListener('click',()=>{if(!payload)return;const url=URL.createObjectURL(new Blob([JSON.stringify(payload,null,2)],{type:'application/json'}));const link=document.createElement('a');link.href=url;link.download=`shopee-product-${payload.product_reference.item_id}.json`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000)});
