import os,tempfile,io,json,shutil
os.environ['STORAGE_PATH']=tempfile.mkdtemp(prefix='studio-test-')
# Tests must never inherit a production database URL from an operator's shell.
os.environ.pop('DATABASE_URL',None)
os.environ['APP_ENV']='development'
os.environ['APP_URL']='http://localhost:3000'
os.environ['ALLOWED_HOSTS']='localhost,127.0.0.1,testserver,aff.pramool.bid'
from cryptography.fernet import Fernet
os.environ['CREDENTIAL_ENCRYPTION_KEY']=Fernet.generate_key().decode()
from fastapi.testclient import TestClient
from app.main import app
from app.db import Session,User,Job,Operation,Record,STORAGE,setting
from app.security import hasher
from app import providers
from PIL import Image
import pytest

@pytest.fixture
def c():
 with Session.begin() as s:
  s.query(Record).filter(Record.kind=='ratelimit').delete()
  if not s.get(User,'tester'):s.add(User(id='tester',password=hasher.hash('test-strong-password!')))
 client=TestClient(app)
 r=client.post('/api/login',json={'username':'tester','password':'test-strong-password!'})
 assert r.status_code==200
 client.headers['x-csrf-token']=r.json()['csrf']
 return client
def product(c):
 r=c.post('/api/products',json={'name':'กระเป๋าผ้า','price':199,'description':'กระเป๋าผ้าสีครีม','url':'https://shopee.co.th/product/1/2?affiliate_id=original'})
 assert r.status_code==200
 p=r.json();buf=io.BytesIO();Image.new('RGB',(400,600),'#d8b58b').save(buf,'PNG')
 r=c.post('/api/products/'+p['id']+'/images',files={'file':('product.png',buf.getvalue(),'image/png')})
 assert r.status_code==200
 return r.json()
def test_auth_and_csrf(c):
 assert TestClient(app).get('/api/products').status_code==401
 token=c.headers.pop('x-csrf-token')
 assert c.post('/api/products',json={'name':'x'}).status_code==403
 c.headers['x-csrf-token']=token
 assert c.post('/api/products',json={'name':'x'},headers={'Origin':'https://evil.example'}).status_code==403
 assert c.post('/api/settings/credentials',files={'file':('key.json',b'{"type":"service_account"}')}).status_code==422
def test_products_and_upload(c):
 p=product(c)
 assert p['url'].endswith('affiliate_id=original')
 assert c.get('/api/images/'+p['images'][0]).status_code==200
 assert c.post('/api/products/'+p['id']+'/images',files={'file':('bad.jpg',b'not an image')}).status_code==422
 assert c.post('/api/products',json={'name':'SSRF','url':'https://127.0.0.1/'}).status_code==422
 assert c.post('/api/products/csv/import',files={'file':('products.csv','name,price\nสินค้าทดสอบ,99'.encode())}).json()['imported']==1
def test_approval_and_queue(c):
 p=product(c);body={'product_id':p['id'],'provider':'mock','duration':15}
 assert c.post('/api/jobs',json=body).status_code==422
 body['approved']=True
 j=c.post('/api/jobs',json=body).json()
 assert j['status']=='draft' and len(j['brief']['scenes'])==2
 assert c.post('/api/jobs/'+j['id']+'/start').json()['status']=='queued'
 assert c.post('/api/jobs/'+j['id']+'/start').status_code==409
 assert c.post('/api/jobs/'+j['id']+'/cancel').json()['status']=='cancelled'
 assert c.post('/api/jobs/'+j['id']+'/resume').json()['status']=='queued'
def test_uncertain_paid_submission_blocks_retry(c):
 p=product(c)
 j=c.post('/api/jobs',json={'product_id':p['id'],'approved':True}).json()
 with Session.begin() as s:
  s.get(Job,j['id']).status='failed';s.add(Operation(id=j['id']+':scene:0',job_id=j['id'],state='intent'))
 assert c.post('/api/jobs/'+j['id']+'/resume').status_code==409
def test_structured_storyboard():
 b=providers.mock_brief({'name':'สินค้า','price':0},45)
 assert len(b.scenes)==6
 assert not any('ราคา' in s.narration for s in b.scenes)
 assert 'Affiliate' in b.caption
def test_image_identifiers_and_scene_constraints(c):
 assert c.post('/api/products',json={'name':'x','images':['../../etc/passwd']}).status_code==422
 from app.schemas import Scene
 with pytest.raises(Exception):Scene(number=1,purpose='x',prompt='x',narration='x',overlay='x',duration=60)
def test_budget_limit_prevents_paid_request(c,monkeypatch):
 p=product(c)
 monkeypatch.setattr(providers,'credentials',lambda:object())
 from app.schemas import ProviderConfig
 monkeypatch.setattr(providers,'config',lambda:ProviderConfig(max_video=.01))
 r=c.post('/api/jobs',json={'product_id':p['id'],'provider':'google','approved':True,'approved_budget':100})
 assert r.status_code==422 and 'budget' in r.json()['detail']
def test_model_config_and_provider_adapter(monkeypatch):
 from types import SimpleNamespace
 seen={}
 def generate(**kwargs):seen.update(kwargs);return SimpleNamespace(name='projects/test/operations/123')
 monkeypatch.setattr(providers,'client',lambda:SimpleNamespace(models=SimpleNamespace(generate_videos=generate)))
 op=providers.submit_video({'prompt':'A product on a clean studio background'})
 assert op.name.endswith('/123') and seen['config'].duration_seconds==8 and seen['config'].aspect_ratio=='9:16'
def test_atomic_claim_and_recovery(c):
 from app.worker import recover,claim
 from concurrent.futures import ThreadPoolExecutor
 # Isolate this queue test from earlier deliberately queued jobs.
 with Session.begin() as s:
  for j in s.query(Job).all():
   if j.status in ['queued','running']:j.status='cancelled'
 p=product(c)
 ids=[]
 for _ in range(2):
  j=c.post('/api/jobs',json={'product_id':p['id'],'approved':True}).json();c.post('/api/jobs/'+j['id']+'/start');ids.append(j['id'])
 with ThreadPoolExecutor(max_workers=2) as pool:claimed=list(pool.map(lambda _:claim(),range(2)))
 assert len(set(claimed))==2 and set(claimed)==set(ids)
 recover()
 with Session() as s:assert all(s.get(Job,id).status=='queued' for id in ids)
def test_archive_restore_and_defaults(c):
 p=product(c);j=c.post('/api/jobs',json={'product_id':p['id'],'approved':True}).json()
 assert c.delete('/api/jobs/'+j['id']).status_code==200
 assert all(x['id']!=j['id'] for x in c.get('/api/jobs').json())
 assert c.post('/api/jobs/'+j['id']+'/restore').json()['status']=='draft'
 assert c.put('/api/settings/defaults',json={'duration':'15','subtitle_size':60}).status_code==200
 assert c.get('/api/settings').json()['defaults']['subtitle_size']==60
def test_credentials_encrypted_and_api_test_truthful(c,monkeypatch):
 from cryptography.hazmat.primitives.asymmetric import rsa
 from cryptography.hazmat.primitives import serialization
 from app.security import cipher
 key=rsa.generate_private_key(public_exponent=65537,key_size=2048).private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()).decode()
 info={'type':'service_account','project_id':'test-project','private_key_id':'test-key','private_key':key,'client_email':'studio@test-project.iam.gserviceaccount.com','client_id':'123','token_uri':'https://oauth2.googleapis.com/token'}
 r=c.post('/api/settings/credentials',files={'file':('key.json',json.dumps(info).encode(),'application/json')})
 assert r.status_code==200 and 'private_key' not in r.text
 encrypted=setting('credential');assert key not in encrypted
 assert json.loads(cipher().decrypt(encrypted.encode()))['project_id']=='test-project'
 monkeypatch.setattr(providers,'test_connection',lambda test_id:{'status':'API Accessible — Model Verification Required','voices':['th-TH-Standard-A'],'live_verified':False})
 r=c.post('/api/settings/test',json={'approve_live_checks':True,'request_id':'credential-test-0001'});assert r.status_code==200 and not r.json()['live_verified']
 assert c.get('/api/settings').json()['status']['live_verified'] is False
@pytest.mark.skipif(not shutil.which('ffmpeg'),reason='FFmpeg required')
def test_complete_mock_pipeline(c):
 from app.worker import pipeline
 from app.media import validate
 import zipfile
 p=product(c)
 j=c.post('/api/jobs',json={'product_id':p['id'],'provider':'mock','duration':15,'resolution':'720','approved':True}).json()
 c.post('/api/jobs/'+j['id']+'/start')
 pipeline(j['id'])
 r=c.get('/api/jobs/'+j['id']).json();assert r['status']=='completed'
 folder=STORAGE/'jobs'/j['id'];info=validate(folder/'final_video.mp4')
 assert abs(float(info['format']['duration'])-15)<.2
 video=next(s for s in info['streams'] if s['codec_type']=='video')
 assert (video['width'],video['height'])==(720,1280)
 assert 'กระเป๋าผ้า' in (folder/'subtitles.ass').read_text(encoding='utf-8')
 assert c.get('/api/jobs/'+j['id']+'/download/final_video.mp4').status_code==200
 with zipfile.ZipFile(folder/'export.zip') as z:assert len(z.namelist())==8
 assert TestClient(app).get('/api/jobs/'+j['id']+'/download/export.zip').status_code==401
 assert c.post('/api/jobs/'+j['id']+'/published',json={'url':'https://shopee.co.th/video/1'}).status_code==200
