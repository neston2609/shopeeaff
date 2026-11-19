"""Isolated provider contracts; these doubles never constitute live ElevenLabs verification."""
import json,uuid,shutil
from types import SimpleNamespace as NS
import pytest,httpx
from test_studio import c,product
from app import elevenlabs,media,providers
from app.db import Session,Record,Job,Operation,STORAGE,set_setting,setting
from app.security import cipher
from app.schemas import ElevenLabsConfig

@pytest.fixture(autouse=True)
def isolated():
 with Session.begin() as s:s.query(Operation).delete();s.query(Job).delete();s.query(Record).delete()
 set_setting('elevenlabs_config',ElevenLabsConfig(voice_id='voice-test').model_dump())
 set_setting('elevenlabs_credential',cipher().encrypt(b'isolated-key-not-a-real-api-key').decode())

def project(c):
 p=product(c);body={'product_id':p['id'],'provider':'mock','duration':15,'resolution':'720','narration_provider':'elevenlabs','approved':True,'approved_budget':1,'request_id':uuid.uuid4().hex}
 quote=c.post('/api/estimate',json=body);assert quote.status_code==200
 body['quote_id']=quote.json()['quote_id']
 response=c.post('/api/jobs',json=body);assert response.status_code==200,response.text
 return response.json(),body

def test_key_is_encrypted_write_only(c):
 value='isolated-new-key-not-a-real-api-key'
 response=c.post('/api/settings/elevenlabs/key',json={'key':value})
 assert response.status_code==200 and value not in response.text
 assert setting('elevenlabs_credential')!=value
 assert cipher().decrypt(setting('elevenlabs_credential').encode()).decode()==value
 assert value not in c.get('/api/settings/elevenlabs').text
 assert c.post('/api/settings/elevenlabs/key',json={'key':'short'}).json()['detail']=='Invalid ElevenLabs API key'

def test_readonly_verification_never_generates_speech(c,monkeypatch):
 requests=[]
 def transport(request):
  requests.append(request)
  assert request.method=='GET'
  if request.url.path=='/v2/voices':return httpx.Response(200,json={'voices':[{'voice_id':'voice-test','name':'Thai test voice','labels':{'language':'th'},'private_key':'never-return-this'}]})
  if request.url.path=='/v1/models':return httpx.Response(200,json=[{'model_id':'eleven_v3','name':'Flash','can_do_text_to_speech':True,'languages':[{'language_id':'th'}]}])
  return httpx.Response(200,json={'tier':'creator','character_count':12,'character_limit':1000,'private_data':'never-return-this'})
 monkeypatch.setattr(elevenlabs,'session',lambda:httpx.Client(base_url='https://api.elevenlabs.io',transport=httpx.MockTransport(transport)))
 response=c.post('/api/settings/elevenlabs/test');assert response.status_code==200
 result=response.json();assert result['authenticated'] and not result['live_verified']
 assert len(requests)==3 and 'never-return-this' not in response.text

def test_invalid_key_error_does_not_echo_key(c,monkeypatch):
 secret='isolated-key-not-a-real-api-key'
 monkeypatch.setattr(elevenlabs,'session',lambda:httpx.Client(base_url='https://api.elevenlabs.io',transport=httpx.MockTransport(lambda _:httpx.Response(401,json={'detail':secret}))))
 response=c.post('/api/settings/elevenlabs/test')
 assert response.json()['error']['category']=='authentication' and secret not in response.text
 assert response.json()['live_verified'] is False

def test_paid_voice_requires_quote_even_for_local_video(c):
 p=product(c);body={'product_id':p['id'],'provider':'mock','narration_provider':'elevenlabs','approved':True,'approved_budget':1,'request_id':uuid.uuid4().hex}
 assert c.post('/api/jobs',json=body).status_code==422
 q=c.post('/api/estimate',json=body).json();assert q['video_usd']==0 and q['tts_reserve_usd']>0
 assert q['voice_provider']=='elevenlabs'

def test_quote_is_invalid_after_voice_or_key_changes(c):
 p=product(c);body={'product_id':p['id'],'provider':'mock','narration_provider':'elevenlabs','approved':True,'approved_budget':1,'request_id':uuid.uuid4().hex}
 body['quote_id']=c.post('/api/estimate',json=body).json()['quote_id']
 set_setting('elevenlabs_credential',cipher().encrypt(b'changed-isolated-credential').decode())
 assert c.post('/api/jobs',json=body).status_code==409

def test_voice_job_creation_and_idempotency(c):
 job,body=project(c)
 assert job['voice_snapshot']['model_id']=='eleven_v3'
 assert job['approval']['voice_fingerprint']==elevenlabs.fingerprint()
 assert c.post('/api/jobs',json=body).json()['id']==job['id']
 with Session() as s:assert s.query(Job).count()==1

def test_key_changes_blocked_while_voice_job_active(c):
 job,body=project(c);c.post('/api/jobs/'+job['id']+'/start')
 assert c.post('/api/settings/elevenlabs/key',json={'key':'another-isolated-test-key-0001'}).status_code==409

def test_tts_single_request_fixed_origin_and_safe_error(monkeypatch):
 calls=[]
 def transport(request):
  calls.append(request)
  assert request.url.host=='api.elevenlabs.io'
  assert json.loads(request.content)['language_code']=='th'
  return httpx.Response(429,json={'detail':'isolated-key-not-a-real-api-key'})
 monkeypatch.setattr(elevenlabs,'session',lambda:httpx.Client(base_url='https://api.elevenlabs.io',transport=httpx.MockTransport(transport)))
 with pytest.raises(elevenlabs.SpeechFailure) as error:elevenlabs.speech('ทดสอบ',STORAGE/'tts-test.mp3','voice-test',1)
 assert error.value.category=='quota' and len(calls)==1
 assert 'isolated-key' not in str(error.value)

def test_uncertain_voice_submission_does_not_retry(c,monkeypatch):
 job,body=project(c);folder=STORAGE/'jobs'/job['id'];folder.mkdir(parents=True,exist_ok=True);calls=[]
 def speech(*_):calls.append(1);raise elevenlabs.SpeechFailure('timeout',uncertain=True)
 monkeypatch.setattr(elevenlabs,'speech',speech)
 with pytest.raises(elevenlabs.SpeechFailure):media.narration(folder,job['brief']['scenes'],job,providers.speech)
 with pytest.raises(ValueError):media.narration(folder,job['brief']['scenes'],job,providers.speech)
 assert len(calls)==1
 with Session.begin() as s:
  assert s.get(Operation,job['id']+':tts:0').state=='submission_uncertain'
  s.get(Job,job['id']).status='failed'
 assert c.post('/api/jobs/'+job['id']+'/resume').status_code==409

def test_uploaded_narration_required_before_start(c):
 p=product(c);j=c.post('/api/jobs',json={'product_id':p['id'],'provider':'mock','narration_provider':'uploaded','approved':True}).json()
 assert c.post('/api/jobs/'+j['id']+'/start').status_code==422

def test_provider_quota_error_is_not_confused_with_bad_key():
 response=httpx.Response(401,json={'detail':{'status':'quota_exceeded','message':'do not echo'}})
 error=httpx.HTTPStatusError('do not echo',request=httpx.Request('POST','https://api.elevenlabs.io/v1/text-to-speech/test'),response=response)
 assert elevenlabs.failure(error).category=='quota'

def test_voice_preview_requires_approval_and_is_idempotent(c,monkeypatch):
 calls=[]
 def speech(text,path,voice,speed):calls.append(1);path.write_bytes(b'isolated-test-audio')
 monkeypatch.setattr(elevenlabs,'speech',speech)
 body={'request_id':'isolated-preview-0001','approved':False,'approved_budget':.01}
 assert c.post('/api/settings/elevenlabs/preview',json=body).status_code==422 and not calls
 body['approved']=True
 first=c.post('/api/settings/elevenlabs/preview',json=body);assert first.status_code==200 and first.json()['status']=='completed'
 assert c.post('/api/settings/elevenlabs/preview',json=body).json()==first.json() and len(calls)==1
 assert c.get(first.json()['audio_url']).status_code==200

def test_uncertain_voice_preview_never_repeats(c,monkeypatch):
 calls=[]
 def speech(*_):calls.append(1);raise elevenlabs.SpeechFailure('timeout',uncertain=True)
 monkeypatch.setattr(elevenlabs,'speech',speech)
 body={'request_id':'isolated-preview-timeout-0001','approved':True,'approved_budget':.01}
 assert c.post('/api/settings/elevenlabs/preview',json=body).json()['status']=='failed'
 assert c.post('/api/settings/elevenlabs/preview',json=body).json()['error']['submission_uncertain']
 assert len(calls)==1

@pytest.mark.skipif(not shutil.which('ffmpeg'),reason='FFmpeg required')
def test_mock_video_with_isolated_eleven_voice_pipeline(c,monkeypatch):
 from app.worker import pipeline
 def speech(text,path,voice,speed):media.run(['ffmpeg','-y','-f','lavfi','-i','anullsrc=r=44100:cl=stereo','-t','1',str(path)])
 monkeypatch.setattr(elevenlabs,'speech',speech)
 job,body=project(c);c.post('/api/jobs/'+job['id']+'/start');pipeline(job['id'])
 result=c.get('/api/jobs/'+job['id']).json();assert result['status']=='completed'
 assert c.get('/api/jobs/'+job['id']+'/download/final_video.mp4').status_code==200
 assert len([o for o in result['operations'] if ':tts:' in o['id'] and o['state']=='done'])==2
