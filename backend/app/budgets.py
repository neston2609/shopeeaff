"""Server-issued, expiring cost quotes. Existing settings and jobs are not migrated away."""
import hashlib,json,time,uuid,math
from fastapi import HTTPException
from sqlalchemy import text
from .db import Record,Session,payload
from .schemas import Project
from . import elevenlabs

NOTICE='Application approval limits estimated application spending only. It does not enable Google Cloud Billing, increase quota, reserve capacity, or guarantee actual Google charges.'
def requires_quote(p):return p.provider=='google' or elevenlabs.selected(p.model_dump())
def input_digest(p):
 values=p.model_dump()
 for key in ['approved','approved_budget','quote_id','request_id']:values.pop(key,None)
 return hashlib.sha256(json.dumps(values,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def breakdown(p,c):
 n=math.ceil(p.duration/8);google=p.provider=='google'
 video=round(n*8*c.video_rate,6) if google else 0
 text=c.text_reserve if google else 0
 voice=elevenlabs.selected(p.model_dump())
 tts=round(n*1500*elevenlabs.config().usd_per_1000_characters/1000,6) if voice else (round(n*1500*c.tts_rate,6) if google and p.narration and p.narration_provider=='auto' else 0)
 return {'scenes':n,'scene_seconds':8,'video_usd':video,'video_per_scene_usd':round(8*c.video_rate,6) if google else 0,'text_reserve_usd':text,'tts_reserve_usd':tts,'estimate_usd':round(video+text+tts,4),'model':c.video_model if google else p.provider,'region':c.location if google else 'local','pricing_verified':c.pricing_verified,'voice_provider':'elevenlabs' if voice else ('google' if google and p.narration_provider=='auto' else p.narration_provider),'voice_model':elevenlabs.config().model_id if voice else None,'voice_pricing_verified':elevenlabs.config().pricing_verified if voice else None,'currency':'USD','label':'Estimate, not actual provider billing','notice':NOTICE+' ElevenLabs credits and billing are also controlled independently by your ElevenLabs account.'}
def quote(p,c):
 from .google_verification import fingerprint
 if p.provider=='google' and c.video_rate<=0:raise HTTPException(422,'Configure a positive Veo price per second before approving paid video generation')
 result=breakdown(p,c);id=uuid.uuid4().hex;now=time.time()
 with Session.begin() as s:
  s.execute(text('BEGIN IMMEDIATE'));result=breakdown(p,c)
  product=s.get(Record,p.product_id)
  if not product or product.kind!='product':raise HTTPException(404,'Product not found')
  s.add(Record(id='quote:'+id,kind='cost_quote',data=json.dumps({'input_digest':input_digest(p),'product_digest':hashlib.sha256(product.data.encode()).hexdigest(),'config':c.model_dump(),'fingerprint':fingerprint(),'voice_fingerprint':elevenlabs.fingerprint() if elevenlabs.selected(p.model_dump()) else None,'expires_at':now+900,'estimate':result['estimate_usd']})))
 return {**result,'quote_id':id,'expires_at':now+900}
def validate_quote(s,p,c,product):
 from .google_verification import fingerprint
 if not p.quote_id or not p.request_id:raise HTTPException(422,'Get a current Studio estimate and explicitly approve it before creating a Google project')
 row=s.get(Record,'quote:'+p.quote_id)
 if not row:raise HTTPException(422,'Cost quote not found; request a new estimate')
 value=json.loads(row.data)
 if value.get('job_id'):raise HTTPException(409,'This quote has already been used. Open the existing project instead of submitting another.')
 if value['expires_at']<time.time():raise HTTPException(409,'Cost quote expired; request a new estimate and approve again')
 if value['input_digest']!=input_digest(p) or value['config']!=c.model_dump() or value['fingerprint']!=fingerprint() or value['product_digest']!=hashlib.sha256(product.data.encode()).hexdigest():raise HTTPException(409,'Settings, credentials, storyboard or product changed; request a new estimate and approve again')
 if elevenlabs.selected(p.model_dump()) and value.get('voice_fingerprint')!=elevenlabs.fingerprint():raise HTTPException(409,'ElevenLabs key or settings changed; get a new estimate and approve again')
 if not p.approved or p.approved_budget<value['estimate']:raise HTTPException(422,'Explicit cost approval and sufficient budget required')
 return row,value
def approve_job(s,j,p,c,quote_row,quote_value):
 data=json.loads(j.data);quote_value['job_id']=j.id;quote_row.data=json.dumps(quote_value)
 data['approval']={'approved_at':time.time(),'limit_usd':p.approved_budget,'estimate_usd':quote_value['estimate'],'quote_id':p.quote_id,'model':c.video_model,'region':c.location,'fingerprint':quote_value['fingerprint'],'voice_fingerprint':quote_value.get('voice_fingerprint'),'notice':NOTICE}
 j.data=json.dumps(data,ensure_ascii=False)
