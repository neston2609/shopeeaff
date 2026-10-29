import os,tempfile,io,json,shutil
os.environ['STORAGE_PATH']=tempfile.mkdtemp(prefix='studio-test-')
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
