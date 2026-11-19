"""ElevenLabs voice adapter: encrypted key, fixed API origin and no automatic paid retries."""
import hashlib,json,time
import httpx
from .db import setting,set_setting
from .security import cipher
from .schemas import ElevenLabsConfig

class SpeechFailure(Exception):
 def __init__(self,category,uncertain=False):
  self.category=category;self.uncertain=uncertain
  messages={'authentication':'ElevenLabs rejected the API key. Check the key and its access permissions.','permission':'ElevenLabs denied this action. Check API-key restrictions, voice permissions and plan.','quota':'ElevenLabs credits or quota are exhausted. Check your account allowance.','billing':'ElevenLabs requires an eligible plan or sufficient credits.','configuration':'Choose an available ElevenLabs voice and a Thai-capable model.','timeout':'ElevenLabs timed out. Audio may have been billed; automatic re-submission is blocked.','unavailable':'ElevenLabs is temporarily unavailable. No automatic paid retry was made.','provider_error':'ElevenLabs voice generation failed. Check the provider settings.','submission_uncertain':'This audio request may already have been billed. Automatic re-submission is blocked.'}
  super().__init__(messages.get(category,messages['provider_error']))
 def public(self):return {'provider':'elevenlabs','category':self.category,'message':str(self),'submission_uncertain':self.uncertain}

def config():return ElevenLabsConfig.model_validate(setting('elevenlabs_config',{}))
def key():
 value=setting('elevenlabs_credential')
 if not value:raise SpeechFailure('authentication')
 try:return cipher().decrypt(value.encode()).decode()
 except Exception:raise SpeechFailure('authentication') from None
def fingerprint():return hashlib.sha256(json.dumps([config().model_dump(),setting('elevenlabs_credential','')],sort_keys=True).encode()).hexdigest()
def selected(data):return bool(data.get('narration',True) and data.get('narration_provider')=='elevenlabs')
def has_paid_voice(data):return selected(data)
def session():return httpx.Client(base_url='https://api.elevenlabs.io',headers={'xi-api-key':key()},timeout=45,follow_redirects=False,transport=httpx.HTTPTransport(retries=0))
def failure(error):
 if isinstance(error,SpeechFailure):return error
 code=getattr(getattr(error,'response',None),'status_code',None)
 reason=None
 try:
  detail=error.response.json().get('detail',{})
  reason=detail.get('status') if isinstance(detail,dict) else None
 except Exception:pass
 if reason in ['quota_exceeded','insufficient_credits','not_enough_credits']:category='quota'
 elif reason in ['payment_required','paid_plan_required']:category='billing'
 elif reason in ['missing_permissions','insufficient_permissions']:category='permission'
 elif reason in ['voice_not_found','model_not_found']:category='configuration'
 elif code==401:category='authentication'
 elif code==403:category='permission'
 elif code==402:category='billing'
 elif code==429:category='quota'
 elif code in [400,404,422]:category='configuration'
 elif isinstance(error,(TimeoutError,httpx.TimeoutException)):category='timeout'
 elif code and code>=500:category='unavailable'
 else:category='provider_error'
 return SpeechFailure(category,uncertain=category in ['timeout','unavailable','provider_error'])
def status():
 result=setting('elevenlabs_status',{'status':'Not configured','live_verified':False})
 if result.get('fingerprint') and result['fingerprint']!=fingerprint():return {'status':'Configuration changed - verify the key again','live_verified':False}
 return result
def verify():
 """Read-only API calls. Never label them as successful live audio generation."""
 c=config();result={'fingerprint':fingerprint(),'checked_at':time.time(),'live_verified':False,'status':'Key/model verification required','voices':[],'models':[]}
 try:
  with session() as client:
   r=client.get('/v2/voices',params={'page_size':100});r.raise_for_status()
   result['voices']=[{'voice_id':str(v['voice_id'])[:100],'name':str(v.get('name','Voice'))[:150],'language':str(v.get('labels',{}).get('language',''))[:50]} for v in r.json().get('voices',[])[:100]]
   r=client.get('/v1/models');r.raise_for_status()
   models=r.json()
   result['models']=[{'model_id':str(m['model_id'])[:100],'name':str(m.get('name',''))[:150],'thai_supported':any(l.get('language_id')=='th' for l in m.get('languages',[]))} for m in models if m.get('can_do_text_to_speech')]
   chosen=next((m for m in result['models'] if m['model_id']==c.model_id),None)
   if not chosen or not chosen['thai_supported']:raise SpeechFailure('configuration')
   result['authenticated']=True;result['status']='Key valid - Thai model available; live audio not tested'
   r=client.get('/v1/user/subscription')
   if r.status_code==200:
    sub=r.json();result['usage']={k:sub.get(k) for k in ['tier','character_count','character_limit']}
   else:result['usage']={'status':'unavailable','note':'Account metadata may require additional API-key permission.'}
 except Exception as error:result.update(status='Verification failed',error=failure(error).public())
 old=status()
 if old.get('fingerprint')==result['fingerprint'] and old.get('live_verified'):
  result['live_verified']=True;result['live_evidence']=old.get('live_evidence')
  result['preview_audio_url']=old.get('preview_audio_url')
 set_setting('elevenlabs_status',result);return result
def speech(text,path,voice,speed=1):
 c=config()
 if not voice or not .7<=speed<=1.2:raise SpeechFailure('configuration')
 try:
  with session() as client:
   r=client.post('/v1/text-to-speech/'+voice,params={'output_format':'mp3_44100_128'},json={'text':text,'model_id':c.model_id,'language_code':'th','voice_settings':{'speed':speed,'stability':.5,'similarity_boost':.75}})
   r.raise_for_status()
   if not r.content or len(r.content)>25*1024*1024:raise SpeechFailure('provider_error')
   tmp=path.with_suffix('.pending.mp3');tmp.write_bytes(r.content)
   from .media import probe
   info=probe(tmp)
   if not any(s.get('codec_type')=='audio' for s in info.get('streams',[])):tmp.unlink(missing_ok=True);raise SpeechFailure('provider_error')
   tmp.replace(path)
 except Exception as error:raise failure(error) from None
def record_success(job_id):
 value=status();value.update(fingerprint=fingerprint(),status='Live voice generation verified',live_verified=True,live_evidence={'job_id':job_id,'verified_at':time.time()});set_setting('elevenlabs_status',value)

PREVIEW_TEXT='สวัสดีค่ะ นี่คือตัวอย่างเสียงภาษาไทยสำหรับวิดีโอสินค้า'
def preview_estimate():return {'text':PREVIEW_TEXT,'estimate_usd':round(len(PREVIEW_TEXT)*config().usd_per_1000_characters/1000,6),'model':config().model_id,'voice_id':config().voice_id,'pricing_verified':config().pricing_verified}
