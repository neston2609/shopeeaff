'use client';
import {useState} from 'react';

type Props={api:(path:string,method?:string,body?:any)=>Promise<any>;onChanged:()=>void};
export default function PasswordSettings({api,onChanged}:Props){
 const [busy,setBusy]=useState(false),[error,setError]=useState('');
 return <form className="panel" onSubmit={async e=>{
  e.preventDefault();const form=e.currentTarget;const values=Object.fromEntries(new FormData(form));
  if(values.new_password!==values.confirm_password){setError('รหัสผ่านใหม่ทั้งสองช่องไม่ตรงกัน');return}
  setBusy(true);setError('');
  try{await api('/account/password','POST',values);form.reset();onChanged()}
  catch(e){setError((e as Error).message)}finally{setBusy(false)}
 }}>
  <h3>เปลี่ยนรหัสผ่าน</h3>
  <p className="muted">รหัสผ่านใหม่ 14–128 ตัวอักษร หลังเปลี่ยนสำเร็จ บัญชีนี้จะออกจากระบบทุกอุปกรณ์</p>
  <div className="form-grid">
   <label>รหัสผ่านปัจจุบัน<input name="current_password" type="password" autoComplete="current-password" required maxLength={500}/></label>
   <label>รหัสผ่านใหม่<input name="new_password" type="password" autoComplete="new-password" required minLength={14} maxLength={128}/></label>
   <label>ยืนยันรหัสผ่านใหม่<input name="confirm_password" type="password" autoComplete="new-password" required minLength={14} maxLength={128}/></label>
  </div>
  {error&&<p className="error" role="alert">{error}</p>}
  <button className="primary" disabled={busy}>{busy?'กำลังเปลี่ยนรหัสผ่าน…':'เปลี่ยนรหัสผ่านและออกจากระบบ'}</button>
 </form>
}
