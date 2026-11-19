'use client';
import {useState} from 'react';

type Props={api:(path:string,method?:string,body?:any)=>Promise<any>;onChanged:()=>void};
export default function PasswordSettings({api,onChanged}:Props){
 const [busy,setBusy]=useState(false),[error,setError]=useState('');
 return <form className="panel" onSubmit={async e=>{
  e.preventDefault();const form=e.currentTarget;const values=Object.fromEntries(new FormData(form));
  if(values.new_password!==values.confirm_password){setError('The new passwords do not match.');return}
  setBusy(true);setError('');
  try{await api('/account/password','POST',values);form.reset();onChanged()}
  catch(e){setError((e as Error).message)}finally{setBusy(false)}
 }}>
  <h3>Change Password</h3>
  <p className="muted">Use 14–128 characters. Changing your password signs this account out on every device.</p>
  <div className="form-grid">
   <label>Current password<input name="current_password" type="password" autoComplete="current-password" required maxLength={500}/></label>
   <label>New password<input name="new_password" type="password" autoComplete="new-password" required minLength={14} maxLength={128}/></label>
   <label>Confirm new password<input name="confirm_password" type="password" autoComplete="new-password" required minLength={14} maxLength={128}/></label>
  </div>
  {error&&<p className="error" role="alert">{error}</p>}
  <button className="primary" disabled={busy}>{busy?'Changing password…':'Change Password and Sign Out'}</button>
 </form>
}
