"""Contract/integration tests with isolated SDK doubles, never live verification evidence.

No production Google request is made by this suite. A separate opt-in script runs real checks.
"""
import json,uuid,threading
from types import SimpleNamespace as NS
import pytest,httpx
from test_studio import c,product
from app.db import Session,Record,Job,Operation,STORAGE,set_setting,setting
from app import providers,google_verification as verification,media,video_jobs
from app.schemas import ProviderConfig,Project
from app.google_errors import GoogleFailure,classify

@pytest.fixture(autouse=True)
def isolated():
 with Session.begin() as s:
  s.query(Operation).delete();s.query(Job).delete();s.query(Record).delete()
 set_setting('provider',ProviderConfig(project='test-project').model_dump())

def prepare(c,monkeypatch):
 monkeypatch.setattr(providers,'credentials',lambda:NS(refresh=lambda request:None))
 p=product(c)
 body={'product_id':p['id'],'provider':'google','duration':15,'approved':True,'approved_budget':10,'request_id':uuid.uuid4().hex,'brief':providers.mock_brief(p,15).model_dump()}
 q=c.post('/api/estimate',json=body);assert q.status_code==200
 body['quote_id']=q.json()['quote_id']
 response=c.post('/api/jobs',json=body);assert response.status_code==200,response.text
 return response.json(),body

def double_checks(monkeypatch,gemini_error=None,tts_error=None,metadata_error=None):
 counts={'text':0,'tts':0,'metadata':0}
 monkeypatch.setattr(providers,'credentials',lambda:NS(refresh=lambda request:None))
 def text(**kwargs):
  counts['text']+=1
  if gemini_error:raise gemini_error
  return NS(text='สวัสดี')
 def synth(**kwargs):
  counts['tts']+=1
  if tts_error:raise tts_error
  return NS(audio_content=b'test-only-audio-not-a-live-result')
 def metadata(cred):
  counts['metadata']+=1
  if metadata_error:raise metadata_error
  return {'metadata_only':True,'does_not_prove_veo_access':True,'service':{'status':'available','state':'ENABLED'},'permissions':{'status':'available','granted':['aiplatform.endpoints.predict']},'quotas':{'status':'available','remaining_capacity_verified':False}}
 monkeypatch.setattr(providers,'client',lambda:NS(models=NS(generate_content=text)))
 monkeypatch.setattr(verification.texttospeech,'TextToSpeechClient',lambda **_:NS(synthesize_speech=synth,list_voices=lambda **_:NS(voices=[NS(name='th-TH-Standard-A')])))
 monkeypatch.setattr(media,'probe',lambda _: {'streams':[{'codec_type':'audio'}]})
 monkeypatch.setattr(verification,'metadata',metadata)
 return counts

def test_independent_live_call_contracts_and_no_veo_claim(c,monkeypatch):
 counts=double_checks(monkeypatch)
 response=c.post('/api/settings/test',json={'approve_live_checks':True,'request_id':'checks-success-test-01'})
 assert response.status_code==200
 result=response.json();assert all(result['checks'][k]['status']=='passed' for k in ['authentication','gemini','tts','vertex'])
 assert counts=={'text':1,'tts':1,'metadata':1}
 assert result['checks']['gemini']['live_generation'] and result['checks']['tts']['live_generation']
 assert result['live_verified'] is False and result['veo']['live_verified'] is False
 assert c.get(result['audio_url']).status_code==200
 from fastapi.testclient import TestClient
 from app.main import app
 assert TestClient(app).get(result['audio_url']).status_code==401
 # An HTTP retry returns the recorded result, without paying again for checks.
 assert c.post('/api/settings/test',json={'approve_live_checks':True,'request_id':'checks-success-test-01'}).json()==result
 assert counts['text']==1 and counts['tts']==1

def test_gemini_failure_does_not_skip_tts_or_metadata(c,monkeypatch):
 counts=double_checks(monkeypatch,gemini_error=httpx.HTTPStatusError('SECRET PRIVATE KEY should not escape',request=httpx.Request('POST','https://example.invalid'),response=httpx.Response(403)))
 result=c.post('/api/settings/test',json={'approve_live_checks':True,'request_id':'checks-partial-test-01'}).json()
 assert result['checks']['gemini']['category']=='permission'
 assert result['checks']['tts']['status']=='passed' and counts['metadata']==1
 assert 'SECRET' not in json.dumps(result) and not result['live_verified']

def test_tts_failure_does_not_skip_vertex(c,monkeypatch):
 double_checks(monkeypatch,tts_error=TimeoutError('raw secret'))
 result=c.post('/api/settings/test',json={'approve_live_checks':True,'request_id':'checks-tts-failure-01'}).json()
 assert result['checks']['gemini']['status']=='passed'
 assert result['checks']['tts']['category']=='timeout' and result['checks']['vertex']['status']=='passed'
 assert result['audio_url'] is None and 'raw secret' not in json.dumps(result)

def test_auth_failure_skips_billable_checks(c,monkeypatch):
 counts=double_checks(monkeypatch)
 monkeypatch.setattr(providers,'credentials',lambda:(_ for _ in ()).throw(GoogleFailure('authentication')))
 result=c.post('/api/settings/test',json={'approve_live_checks':True,'request_id':'checks-auth-failure-01'}).json()
 assert result['checks']['authentication']['status']=='failed'
 assert result['checks']['gemini']['status']=='skipped' and counts['tts']==0

def test_connection_requires_consent(c,monkeypatch):
 counts=double_checks(monkeypatch)
 assert c.post('/api/settings/test',json={'approve_live_checks':False,'request_id':'checks-not-approved-01'}).status_code==422
 assert not any(counts.values())

def test_real_veo_evidence_preserved_across_connection_checks(c,monkeypatch):
 verification.record_veo_success('completed-test-job','projects/test/operations/completed-test-operation')
 double_checks(monkeypatch)
 result=c.post('/api/settings/test',json={'approve_live_checks':True,'request_id':'checks-preserve-proof-01'}).json()
 assert result['live_verified'] and c.get('/api/settings').json()['status']['veo']['evidence']['job_id']=='completed-test-job'
 conf=providers.config();conf.location='asia-southeast1';set_setting('provider',conf.model_dump())
 assert not c.get('/api/settings').json()['status']['live_verified']

def test_server_quotes_and_project_idempotency(c,monkeypatch):
 job,body=prepare(c,monkeypatch)
 second=c.post('/api/jobs',json=body);assert second.status_code==200 and second.json()['id']==job['id']
 with Session() as s:assert s.query(Job).count()==1
 body['request_id']=uuid.uuid4().hex
 assert c.post('/api/jobs',json=body).status_code==409
 assert job['approval']['model']=='veo-3.1-fast-generate-001'
 assert 'Billing' in job['approval']['notice']

def test_missing_stale_or_unapproved_quote_rejected(c,monkeypatch):
 monkeypatch.setattr(providers,'credentials',lambda:object())
 p=product(c);body={'product_id':p['id'],'provider':'google','duration':15,'approved':True,'approved_budget':10,'request_id':uuid.uuid4().hex}
 assert c.post('/api/jobs',json=body).status_code==422
 body['quote_id']=c.post('/api/estimate',json=body).json()['quote_id'];body['duration']=30
 assert c.post('/api/jobs',json=body).status_code==409
 body['duration']=15
 with Session.begin() as s:
  row=s.get(Record,'quote:'+body['quote_id']);value=json.loads(row.data);value['expires_at']=0;row.data=json.dumps(value)
 assert c.post('/api/jobs',json=body).status_code==409

def test_editing_configuration_invalidates_quote(c,monkeypatch):
 monkeypatch.setattr(providers,'credentials',lambda:object())
 p=product(c);body={'product_id':p['id'],'provider':'google','approved':True,'approved_budget':10,'request_id':uuid.uuid4().hex}
 body['quote_id']=c.post('/api/estimate',json=body).json()['quote_id']
 conf=providers.config();conf.video_model='veo-future-supported-model';set_setting('provider',conf.model_dump())
 assert c.post('/api/jobs',json=body).status_code==409

def test_metadata_permission_failures_are_not_veo_success(monkeypatch):
 class Response:
  def raise_for_status(self):raise httpx.HTTPStatusError('SECRET',request=httpx.Request('GET','https://example.invalid'),response=httpx.Response(403))
 monkeypatch.setattr(verification,'AuthorizedSession',lambda _:NS(request=lambda **_:Response(),close=lambda:None))
 data=verification.metadata(object())
 assert data['permissions']['status']=='unavailable' and data['quotas']['category']=='permission'
 assert data['does_not_prove_veo_access'] and 'SECRET' not in json.dumps(data)

@pytest.mark.parametrize('code,message,category',[(401,'x','authentication'),(403,'x','permission'),(403,'BILLING_DISABLED','billing'),(429,'x','quota'),(404,'x','model_unavailable'),(503,'x','unavailable')])
def test_safe_provider_error_categories(code,message,category):
 error=httpx.HTTPStatusError('PRIVATE_KEY '+message,request=httpx.Request('POST','https://example.invalid'),response=httpx.Response(code))
 safe=classify(error)
 assert safe.category==category and 'PRIVATE_KEY' not in str(safe)

def test_sdk_submission_retries_disabled(monkeypatch):
 seen={}
 monkeypatch.setattr(providers,'credentials',lambda:object())
 monkeypatch.setattr(providers.genai,'Client',lambda **kw:seen.update(kw))
 providers.client()
 assert seen['http_options'].retry_options.attempts==1

def video_doubles(monkeypatch,submitted,polls):
 def submit(*_):submitted.append(True);return NS(name='projects/test/locations/us-central1/operations/test')
 monkeypatch.setattr(providers,'submit_video',submit)
 monkeypatch.setattr(providers,'poll_video',lambda _:polls.pop(0))
 monkeypatch.setattr(providers,'download_video',lambda _,p:p.write_bytes(b'isolated-test-video'))
 monkeypatch.setattr(media,'validate',lambda _: {'streams':[{'codec_type':'video'}]})
 return NS(wait=lambda _:False)
def completed():return NS(done=True,error=None,response=NS(generated_videos=[NS(video=object())]),result=None)

def test_submit_poll_download_and_library_evidence(c,monkeypatch):
 job,body=prepare(c,monkeypatch);c.post('/api/jobs/'+job['id']+'/start')
 submitted=[];stop=video_doubles(monkeypatch,submitted,[NS(done=False),completed()])
 path=STORAGE/'workflow-video.mp4'
 video_jobs.generate_scene(job['id'],0,body['brief']['scenes'][0],path,None,lambda *_:None,stop)
 assert path.read_bytes()==b'isolated-test-video' and len(submitted)==1
 with Session() as s:assert s.get(Operation,job['id']+':scene:0').state=='done'
 assert verification.veo_status()['live_verified']

def test_resume_saved_operation_never_resubmits(c,monkeypatch):
 job,body=prepare(c,monkeypatch)
 with Session.begin() as s:s.add(Operation(id=job['id']+':scene:0',job_id=job['id'],state='polling',name='projects/test/operations/saved'))
 submitted=[];stop=video_doubles(monkeypatch,submitted,[completed()])
 video_jobs.generate_scene(job['id'],0,body['brief']['scenes'][0],STORAGE/'resumed.mp4',None,lambda *_:None,stop)
 assert submitted==[]

def test_submission_timeout_blocks_retry_and_extra_billing(c,monkeypatch):
 job,body=prepare(c,monkeypatch);calls=[]
 def submit(*_):calls.append(1);raise TimeoutError('PRIVATE_KEY timeout')
 monkeypatch.setattr(providers,'submit_video',submit)
 for _ in range(2):
  with pytest.raises(GoogleFailure):video_jobs.generate_scene(job['id'],0,body['brief']['scenes'][0],STORAGE/'uncertain.mp4',None,lambda *_:None,NS(wait=lambda _:False))
 assert len(calls)==1
 with Session.begin() as s:s.get(Job,job['id']).status='failed'
 assert c.post('/api/jobs/'+job['id']+'/resume').status_code==409
 assert not verification.veo_status()['live_verified']

def test_failed_operation_never_verifies_or_resubmits(c,monkeypatch):
 job,body=prepare(c,monkeypatch);submitted=[]
 stop=video_doubles(monkeypatch,submitted,[NS(done=True,error={'code':8,'message':'quota exceeded PRIVATE_KEY'})])
 with pytest.raises(GoogleFailure) as error:video_jobs.generate_scene(job['id'],0,body['brief']['scenes'][0],STORAGE/'failed.mp4',None,lambda *_:None,stop)
 assert error.value.category=='quota' and not verification.veo_status()['live_verified']
 with pytest.raises(GoogleFailure):video_jobs.generate_scene(job['id'],0,body['brief']['scenes'][0],STORAGE/'failed.mp4',None,lambda *_:None,stop)
 assert len(submitted)==1

def test_poll_timeout_retries_only_polling(c,monkeypatch):
 job,body=prepare(c,monkeypatch);submitted=[];stop=video_doubles(monkeypatch,submitted,[]);calls=[]
 def poll(_):
  calls.append(1)
  if len(calls)==1:raise TimeoutError('network timeout')
  return completed()
 monkeypatch.setattr(providers,'poll_video',poll)
 video_jobs.generate_scene(job['id'],0,body['brief']['scenes'][0],STORAGE/'polled.mp4',None,lambda *_:None,stop)
 assert len(submitted)==1 and len(calls)==2

def test_bad_video_output_never_verifies(c,monkeypatch):
 job,body=prepare(c,monkeypatch);submitted=[];stop=video_doubles(monkeypatch,submitted,[completed()])
 monkeypatch.setattr(media,'validate',lambda _:(_ for _ in ()).throw(ValueError('invalid media')))
 with pytest.raises(GoogleFailure):video_jobs.generate_scene(job['id'],0,body['brief']['scenes'][0],STORAGE/'bad-output.mp4',None,lambda *_:None,stop)
 assert not verification.veo_status()['live_verified']

def test_configuration_updates_are_blocked_during_active_jobs(c,monkeypatch):
 job,body=prepare(c,monkeypatch)
 c.post('/api/jobs/'+job['id']+'/start')
 config=providers.config().model_dump();config['location']='asia-southeast1'
 assert c.put('/api/settings/provider',json=config).status_code==409
 assert providers.config().location=='us-central1'

def test_old_connection_request_cannot_verify_new_configuration(c,monkeypatch):
 double_checks(monkeypatch)
 body={'approve_live_checks':True,'request_id':'test-config-replay-0001'}
 assert c.post('/api/settings/test',json=body).status_code==200
 conf=providers.config();conf.location='asia-southeast1';set_setting('provider',conf.model_dump())
 assert c.post('/api/settings/test',json=body).status_code==409

def test_quote_does_not_allow_zero_priced_google_submission(c):
 p=product(c);conf=providers.config();conf.video_rate=0;set_setting('provider',conf.model_dump())
 assert c.post('/api/estimate',json={'product_id':p['id'],'provider':'google'}).status_code==422
