'use client';
import {useRef,useState} from 'react';
import BrowserProductImport from './BrowserProductImport';
import {productReferenceFromUrl} from '../lib/browser-import.mjs';
type Props={url:string;onChange:(url:string)=>void;onFetched:(data:Record<string,any>)=>void;api:(path:string,method?:string,body?:any)=>Promise<any>;disabled:boolean;onBusy:(busy:boolean)=>void};
export default function ProductLinkFetch({url,onChange,onFetched,api,disabled,onBusy}:Props){
 const [busy,setBusy]=useState(false),[error,setError]=useState(''),[message,setMessage]=useState(''),[resolved,setResolved]=useState<Record<string,any>|null>(null);
 const latest=useRef(url);latest.current=url;
 return <div className="product-link-fetch"><label>Shopee / Affiliate Link<input type="url" value={url} placeholder="https://s.shopee.co.th/..." onChange={e=>{onChange(e.target.value);setError('');setMessage('');setResolved(null)}}/></label>
  <button type="button" disabled={disabled||busy||!url.trim()} onClick={async()=>{
   const requested=url;setBusy(true);onBusy(true);setError('');setMessage('');setResolved(null);
   try{
    const result=await api('/products/fetch-information','POST',{url:requested});
    if(latest.current!==requested)return;
    setResolved(result);
    if(result.fields.length)onFetched(result.data);
    setMessage(`${result.fields.length?`Fetched ${result.fields.join(', ')}. `:''}${(result.warnings||[]).join(' ')}`);
   }catch(e){if(latest.current===requested)setError((e as Error).message)}
   finally{setBusy(false);onBusy(false)}
  }}>{busy?'Fetching information…':'Fetch Information'}</button>
  {error&&<p className="error" role="alert">{error}</p>}
  {resolved&&<div className="callout"><strong>{resolved.redirect_resolved?'Short link resolved successfully':'Product link identified'}</strong><p>Viewer / affiliate link (unchanged): <a href={resolved.original_url} target="_blank" rel="noreferrer">{resolved.original_url}</a></p><p>Product page for reading details: <a href={resolved.product_page_url} target="_blank" rel="noreferrer">Open Product Page</a></p>{resolved.product_reference&&<small>Shop ID: {resolved.product_reference.shop_id} · Item ID: {resolved.product_reference.item_id}</small>}</div>}
  {message&&<p className="callout" role="status">{message}</p>}
  <BrowserProductImport key={url} originalUrl={url} expected={resolved?.product_reference||productReferenceFromUrl(url)} disabled={disabled||busy} onApply={onFetched}/>
 </div>
}
