"""Independent live checks and scoped, durable Veo success evidence."""
import hashlib,json,time,uuid
from google.auth.transport.requests import Request,AuthorizedSession
from google.cloud import texttospeech
from google.genai import types
from .db import STORAGE,setting,set_setting
from .google_errors import classify,GoogleFailure

def fingerprint():
 from . import providers
 c=providers.config()
 credential=setting('credential','') if c.auth_method=='service_account' else 'adc'
 return hashlib.sha256(json.dumps([c.project,c.location,c.video_model,c.auth_method,credential]).encode()).hexdigest()

def veo_status():
 from . import providers
 c=providers.config();evidence=setting('veo:'+fingerprint())
 return {'status':'live_verified' if evidence else 'not_live_verified','live_verified':bool(evidence),'model':c.video_model,'region':c.location,'project':c.project,'evidence':evidence,'message':'A real Veo operation completed and its video passed media validation.' if evidence else 'Configuration checks do not verify Veo generation. Approve a Studio budget and complete a real video operation.'}

def record_veo_success(job_id,operation_name):
 if not operation_name:raise ValueError('Completed operation ID required')
 set_setting('veo:'+fingerprint(),{'job_id':job_id,'operation_name':operation_name,'verified_at':time.time()})

def current_status():
 value=dict(setting('provider_status',{'status':'Not Configured'}))
 # Old provider status records are retained, but cannot substitute for scoped operation evidence.
 if value.get('fingerprint') and value['fingerprint']!=fingerprint():value={'status':'Configuration changed — run checks again','checks':{}}
 veo=veo_status();value['veo']=veo;value['live_verified']=veo['live_verified']
 if veo['live_verified']:value['status']='Veo live generation verified'
 elif value.get('status')=='Live Generation Tested':value['status']='Historical status — live operation evidence required'
 return value

def metadata(cred):
 from . import providers
 c=providers.config();session=AuthorizedSession(cred);result={'project':c.project,'region':c.location,'model':c.video_model,'metadata_only':True,'does_not_prove_veo_access':True}
 def get(url,**kwargs):
  response=session.request(timeout=10,**kwargs,url=url);response.raise_for_status();return response.json()
 try:
  project=get(f'https://cloudresourcemanager.googleapis.com/v3/projects/{c.project}',method='GET')
  number=project['name'].split('/')[-1];result['project_number']=number
 except Exception as error:
  result['project_lookup']={'status':'unavailable',**classify(error).public()};number=c.project
 for name,url,method,body in [
  ('service',f'https://serviceusage.googleapis.com/v1/projects/{number}/services/aiplatform.googleapis.com','GET',None),
  ('permissions',f'https://cloudresourcemanager.googleapis.com/v1/projects/{c.project}:testIamPermissions','POST',{'permissions':['aiplatform.endpoints.predict','serviceusage.services.get','serviceusage.quotas.get']}),
  ('quotas',f'https://serviceusage.googleapis.com/v1beta1/projects/{number}/services/aiplatform.googleapis.com/consumerQuotaMetrics?pageSize=20&view=FULL','GET',None),
 ]:
  try:
   raw=get(url,method=method,**({'json':body} if body else {}))
   if name=='service':value={'state':raw.get('state','UNKNOWN'),'name':'aiplatform.googleapis.com'}
   elif name=='permissions':value={'granted':raw.get('permissions',[]),'not_an_exhaustive_permission_check':True}
   else:
    value={'metrics':[{'metric':m.get('metric'),'display_name':m.get('displayName'),'limits':[{'unit':l.get('unit'),'buckets':[{'effective_limit':b.get('effectiveLimit'),'dimensions':b.get('dimensions',{})} for b in l.get('quotaBuckets',[])[:10]]} for l in m.get('consumerQuotaLimits',[])[:10]]} for m in raw.get('metrics',[])[:20]],'truncated':bool(raw.get('nextPageToken')),'remaining_capacity_verified':False,'note':'Visible quota metadata is not current usage, a capacity reservation or a billing approval.'}
   result[name]={'status':'available',**value}
  except Exception as error:result[name]={'status':'unavailable',**classify(error).public()}
 session.close()
 return result

def run_checks(test_id):
 from . import providers
 checks={};started=time.time();voices=[];audio_url=None
 def check(name,fn):
  try:
   value=fn();checks[name]={'status':'passed','checked_at':time.time(),**(value or {})};return value
  except Exception as error:
   checks[name]={'status':'failed','checked_at':time.time(),**classify(error).public()};return None
 holder={}
 def authenticate():
  cred=providers.credentials();request=Request()
  cred.refresh(lambda *args,**kwargs:request(*args,**{**kwargs,'timeout':20}));holder['credential']=cred
  return {'method':providers.config().auth_method,'token_refreshed':True}
 check('authentication',authenticate)
 if not holder:
  for name in ['gemini','tts','vertex']:checks[name]={'status':'skipped','message':'Authentication did not succeed; no API request submitted.'}
 else:
  def gemini():
   model=providers.config().text_model
   thinking=types.ThinkingConfig(thinking_budget=0) if model.startswith('gemini-2.5-flash') else None
   with providers.client() as ai:
    response=ai.models.generate_content(model=model,contents='ตอบเพียงคำว่า สวัสดี',config=types.GenerateContentConfig(max_output_tokens=256,temperature=0,thinking_config=thinking,http_options=types.HttpOptions(timeout=30000)))
   if not response.text or not response.text.strip():raise GoogleFailure('provider_error')
   return {'live_generation':True,'model':providers.config().text_model,'generated_characters':len(response.text)}
  check('gemini',gemini)
  def tts():
   nonlocal voices,audio_url
   client=texttospeech.TextToSpeechClient(credentials=holder['credential'])
   # Use a documented Thai voice for synthesis; voice listing is independently optional.
   response=client.synthesize_speech(input=texttospeech.SynthesisInput(text='สวัสดีค่ะ ทดสอบระบบเสียงภาษาไทย'),voice=texttospeech.VoiceSelectionParams(language_code='th-TH',name='th-TH-Standard-A'),audio_config=texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3),retry=None,timeout=20)
   if not response.audio_content:raise GoogleFailure('provider_error')
   folder=STORAGE/'provider-tests'/test_id;folder.mkdir(parents=True,exist_ok=True)
   tmp=folder/'preview.tmp';tmp.write_bytes(response.audio_content)
   from .media import probe
   info=probe(tmp)
   if not any(s['codec_type']=='audio' for s in info.get('streams',[])):tmp.unlink(missing_ok=True);raise GoogleFailure('provider_error')
   tmp.replace(folder/'preview.mp3');audio_url=f'/api/settings/tests/{test_id}/audio'
   try:voices=[v.name for v in client.list_voices(language_code='th-TH',timeout=20).voices]
   except Exception:voices=[]
   return {'live_generation':True,'audio_url':audio_url,'bytes':len(response.audio_content)}
  check('tts',tts)
  def vertex():
   if not providers.config().project:raise GoogleFailure('configuration')
   return metadata(holder['credential'])
  check('vertex',vertex)
  if checks.get('vertex',{}).get('service',{}).get('state')=='DISABLED':checks['vertex']['status']='failed';checks['vertex']['message']='Vertex AI API is disabled in this project.'
  elif checks.get('vertex',{}).get('status')=='passed' and any(checks['vertex'].get(k,{}).get('status')=='unavailable' for k in ['service','permissions','quotas']):checks['vertex']['status']='limited'
 live_ok=all(checks[k]['status']=='passed' for k in ['authentication','gemini','tts'])
 return {'test_id':test_id,'fingerprint':fingerprint(),'checked_at':started,'status':'Live text/audio checks passed — Veo generation not tested' if live_ok else 'Some Google checks failed — inspect individual results','checks':checks,'voices':voices,'audio_url':audio_url,'veo':veo_status(),'live_verified':veo_status()['live_verified'],'notice':'These checks can incur small Gemini/TTS charges. They do not submit a Veo video or replace Google Cloud Billing/quota controls.'}
