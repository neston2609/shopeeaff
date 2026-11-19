'use client';
import {useRef,useState} from 'react';
type Props={url:string;onChange:(url:string)=>void;onFetched:(data:Record<string,any>)=>void;api:(path:string,method?:string,body?:any)=>Promise<any>;disabled:boolean;onBusy:(busy:boolean)=>void};
export default function ProductLinkFetch({url,onChange,onFetched,api,disabled,onBusy}:Props){
 const [busy,setBusy]=useState(false),[error,setError]=useState(''),[message,setMessage]=useState('');
 const latest=useRef(url);latest.current=url;
 return <div className="product-link-fetch"><label>Shopee / Affiliate Link<input type="url" value={url} placeholder="https://s.shopee.co.th/..." onChange={e=>{onChange(e.target.value);setError('');setMessage('')}}/></label>
  <button type="button" disabled={disabled||busy||!url.trim()} onClick={async()=>{
   const requested=url;setBusy(true);onBusy(true);setError('');setMessage('');
   try{
    const result=await api('/products/fetch-information','POST',{url:requested});
    if(latest.current!==requested)return;
    onFetched(result.data);setMessage(`Fetched ${result.fields.join(', ')}. ${(result.warnings||[]).join(' ')}`);
   }catch(e){if(latest.current===requested)setError((e as Error).message)}
   finally{setBusy(false);onBusy(false)}
  }}>{busy?'Fetching information…':'Fetch Information'}</button>
  {error&&<p className="error" role="alert">{error}</p>}
  {message&&<p className="callout" role="status">{message}</p>}
 </div>
}
