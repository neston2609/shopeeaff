import os,json,time,secrets,io,csv,uuid,shutil,hashlib
from pathlib import Path
from fastapi import FastAPI,Request,Response,HTTPException,Depends,UploadFile,File
from fastapi.responses import FileResponse
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy import select,func,text
from PIL import Image,UnidentifiedImageError
from .db import *
from .schemas import *
from .security import auth,hasher,digest,cipher
from . import providers
from . import budgets,google_verification
from .google_errors import GoogleFailure,classify

app=FastAPI(title='Shopee Aff AI Studio',docs_url=None,redoc_url=None,openapi_url=None)
app.add_middleware(TrustedHostMiddleware,allowed_hosts=os.getenv('ALLOWED_HOSTS','localhost,127.0.0.1,testserver,aff.pramool.bid').split(','))
init()
@app.middleware('http')
async def security_headers(request,call_next):
 if int(request.headers.get('content-length','0'))>110*1024*1024: return Response(status_code=413)
 if request.method not in ('GET','HEAD','OPTIONS') and request.headers.get('origin') and request.headers['origin']!=os.getenv('APP_URL','http://localhost:3000'): return Response(status_code=403)
 response=await call_next(request)
 response.headers['X-Content-Type-Options']='nosniff';response.headers['Cache-Control']='no-store'
 return response
def uid(): return uuid.uuid4().hex
def get_record(s,id,kind=None):
 r=s.get(Record,id)
 if not r or (kind and r.kind!=kind): raise HTTPException(404,'Not found')
 return r
def job_json(j):
 with Session() as s:operations=[{'id':o.id,'state':o.state,'operation_name':o.name,'estimated_cost_usd':o.cost} for o in s.scalars(select(Operation).where(Operation.job_id==j.id)).all()]
 return {**json.loads(j.data),'id':j.id,'product_id':j.product_id,'status':j.status,'progress':j.progress,'stage':j.stage,'error':j.error,'created':j.created,'updated':j.updated,'operations':operations}
def get_job(s,id):
 j=s.get(Job,id)
 if not j: raise HTTPException(404,'Job not found')
 return j
@app.get('/api/health')
def health():
 with Session() as s: s.execute(text('SELECT 1'))
 return {'status':'ok'}
@app.post('/api/login')
async def login(request:Request,response:Response):
 body=await request.json();name=str(body.get('username',''))[:100];password=str(body.get('password',''))[:500]
 ip=request.client.host if request.client else 'unknown';key='ratelimit:'+hashlib.sha256(ip.encode()).hexdigest()+':'+str(int(time.time()//900))
 with Session.begin() as s:
  s.execute(text('BEGIN IMMEDIATE'))
  r=s.get(Record,key)
  n=int(r.data) if r else 0
  if n>=10: raise HTTPException(429,'Too many attempts; try again in 15 minutes')
  if not r: s.add(Record(id=key,kind='ratelimit',data='1'))
  else:r.data=str(n+1)
  u=s.get(User,name)
  try:
   hasher.verify(u.password if u else hasher.hash(secrets.token_hex(32)),password)
  except Exception: u=None
  if not u: return Response(content='{"detail":"Invalid username or password"}',status_code=401,media_type='application/json')
  token=secrets.token_urlsafe(48);csrf=secrets.token_urlsafe(32)
  s.add(LoginSession(id=digest(token),csrf=csrf,expires=time.time()+43200))
 response.set_cookie('studio_session',token,httponly=True,secure=os.getenv('APP_ENV')=='production',samesite='strict',max_age=43200,path='/')
 return {'username':name,'csrf':csrf}
@app.get('/api/me')
def me(session=Depends(auth)): return {'username':'admin','csrf':session.csrf}
@app.post('/api/logout')
def logout(response:Response,session=Depends(auth)):
 with Session.begin() as s:s.delete(s.get(LoginSession,session.id))
 response.delete_cookie('studio_session');return {'ok':True}
@app.get('/api/dashboard',dependencies=[Depends(auth)])
def dashboard():
 with Session() as s:
  jobs=s.scalars(select(Job)).all();products=s.scalars(select(Record).where(Record.kind=='product')).all()
  return dict(products=len(products),videos=sum(j.status=='completed' for j in jobs),failed=sum(j.status=='failed' for j in jobs),active=sum(j.status in ['queued','running'] for j in jobs),estimated_cost=sum(json.loads(j.data).get('reserved_cost',0) for j in jobs),recent_products=[payload(r) for r in products[-5:]],recent_jobs=[job_json(j) for j in jobs[-5:]],provider=google_verification.current_status())
@app.get('/api/products',dependencies=[Depends(auth)])
def products():
 with Session() as s:return [payload(r) for r in s.scalars(select(Record).where(Record.kind=='product').order_by(Record.created.desc())).all()]
@app.post('/api/products',dependencies=[Depends(auth)])
def create_product(p:Product):
 with Session.begin() as s:
  r=Record(id=uid(),kind='product',data=p.model_dump_json());s.add(r);s.flush();return payload(r)
@app.put('/api/products/{id}',dependencies=[Depends(auth)])
def update_product(id:str,p:Product):
 with Session.begin() as s:r=get_record(s,id,'product');r.data=p.model_dump_json();return payload(r)
@app.delete('/api/products/{id}',dependencies=[Depends(auth)])
def delete_product(id:str):
 with Session.begin() as s:
  if s.scalar(select(func.count()).select_from(Job).where(Job.product_id==id)): raise HTTPException(409,'Product has projects; keep it for project history')
  s.delete(get_record(s,id,'product'))
 return {'ok':True}
@app.post('/api/products/csv/import',dependencies=[Depends(auth)])
async def csv_import(file:UploadFile):
 raw=await file.read(2*1024*1024+1)
 if len(raw)>2*1024*1024:raise HTTPException(413,'CSV limit is 2 MB')
 try:
  rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
  if len(rows)>500:raise ValueError('Maximum 500 rows')
  ps=[Product.model_validate({k:v for k,v in row.items() if v and k in Product.model_fields}) for row in rows]
 except Exception as e:raise HTTPException(422,str(e)[:300])
 with Session.begin() as s:
  for p in ps:s.add(Record(id=uid(),kind='product',data=p.model_dump_json()))
 return {'imported':len(ps)}
@app.post('/api/products/{id}/images',dependencies=[Depends(auth)])
async def upload_image(id:str,file:UploadFile):
 raw=await file.read(12*1024*1024+1)
 if len(raw)>12*1024*1024:raise HTTPException(413,'Image limit is 12 MB')
 try:
  im=Image.open(io.BytesIO(raw));im.verify();im=Image.open(io.BytesIO(raw));im.thumbnail((2400,2400));im=im.convert('RGB')
 except Exception:raise HTTPException(422,'Invalid image; use JPEG, PNG or WebP')
 with Session.begin() as s:
  r=get_record(s,id,'product');p=json.loads(r.data)
  if len(p.get('images',[]))>=20:raise HTTPException(422,'Maximum 20 images')
  name=uid()+'.jpg';(STORAGE/'uploads').mkdir(exist_ok=True);im.save(STORAGE/'uploads'/name,'JPEG',quality=92)
  p.setdefault('images',[]).append(name);r.data=json.dumps(p,ensure_ascii=False);return payload(r)
@app.get('/api/images/{name}',dependencies=[Depends(auth)])
def image(name:str):
 if not __import__('re').fullmatch(r'[a-f0-9]{32}\.jpg',name):raise HTTPException(404)
 p=STORAGE/'uploads'/name
 if not p.is_file():raise HTTPException(404)
 return FileResponse(p)
@app.post('/api/analyze',dependencies=[Depends(auth)])
def analyze(p:Project):
 with Session() as s: product=payload(get_record(s,p.product_id,'product'))
 if p.provider=='google':raise HTTPException(409,'Create and approve a Google project to run paid content analysis')
 return providers.mock_brief(product,p.duration,p.style).model_dump()
@app.get('/api/jobs',dependencies=[Depends(auth)])
def jobs():
 with Session() as s:return [job_json(j) for j in s.scalars(select(Job).where(Job.status!='archived').order_by(Job.created.desc())).all()]
@app.get('/api/jobs/{id}',dependencies=[Depends(auth)])
def job(id:str):
 with Session() as s:return job_json(get_job(s,id))
def estimate(p:Project):
 return budgets.breakdown(p,providers.config())['estimate_usd']
@app.post('/api/estimate',dependencies=[Depends(auth)])
def estimate_api(p:Project):return budgets.quote(p,providers.config())
@app.post('/api/jobs',dependencies=[Depends(auth)])
def create_job(p:Project):
 cost=estimate(p);c=providers.config()
 if not p.approved or cost>p.approved_budget:raise HTTPException(422,'Explicit approval and sufficient budget required')
 if p.provider=='google' and cost>c.max_video:raise HTTPException(422,'Per-video budget exceeded')
 if p.brief and len(p.brief.scenes)!=__import__('math').ceil(p.duration/8):raise HTTPException(422,'Storyboard scene count must match target duration')
 with Session.begin() as s:
  s.execute(text('BEGIN IMMEDIATE'));product=payload(get_record(s,p.product_id,'product'))
  # One browser request key represents one project, even if the HTTP response is lost.
  request_digest=hashlib.sha256(p.model_dump_json().encode()).hexdigest()
  request_row=s.get(Record,'job-request:'+p.request_id) if p.request_id else None
  if request_row:
   previous=json.loads(request_row.data)
   if previous['digest']!=request_digest:raise HTTPException(409,'Request key was already used for different project settings')
   return job_json(get_job(s,previous['job_id']))
  quote_row=quote_value=None
  if p.provider=='google':
   quote_row,quote_value=budgets.validate_quote(s,p,c,get_record(s,p.product_id,'product'))
   try:providers.credentials()
   except Exception as error:raise classify(error) from None
  if p.accuracy and not product.get('images'):raise HTTPException(422,'Product Accuracy Mode requires an authorized product image')
  all_jobs=s.scalars(select(Job)).all()
  now=time.time()
  for period,budget in [(86400,c.daily_budget),(86400*31,c.monthly_budget)]:
   used=sum(json.loads(j.data).get('reserved_cost',0) for j in all_jobs if j.created>=now-period)
   if cost+used>budget:raise HTTPException(422,'Daily or monthly budget exceeded')
  data=p.model_dump();data['reserved_cost']=cost;data['pricing_snapshot']=c.model_dump();data['product_snapshot']=product
  if p.provider!='google' and not p.brief:data['brief']=providers.mock_brief(product,p.duration,p.style).model_dump()
  j=Job(id=uid(),product_id=p.product_id,status='draft',stage='Review storyboard / upload assets',data=json.dumps(data,ensure_ascii=False));s.add(j);s.flush()
  if p.regenerate_source:
   source=get_job(s,p.regenerate_source);old=json.loads(source.data)
   if source.status!='completed' or old['product_id']!=p.product_id or old['provider']!=p.provider or old['duration']!=p.duration or (p.regenerate_scene is None and not p.regenerate_voice) or (p.regenerate_scene is not None and p.regenerate_scene>=len(old['brief']['scenes'])):raise HTTPException(422,'Source project must match product, provider and duration')
   data['brief']=old['brief'];j.data=json.dumps(data,ensure_ascii=False)
   folder=STORAGE/'jobs'/j.id;folder.mkdir(parents=True,exist_ok=True)
   for i in range(len(old['brief']['scenes'])):
    for filename in [f'scene-{i}.mp4',f'voice-{i}.mp3']:
     src=STORAGE/'jobs'/source.id/filename
     if src.exists() and not (i==p.regenerate_scene and filename.endswith('.mp4')) and not (p.regenerate_voice and filename.endswith('.mp3')):shutil.copy2(src,folder/filename)
  if quote_row:budgets.approve_job(s,j,p,c,quote_row,quote_value)
  if p.request_id:s.add(Record(id='job-request:'+p.request_id,kind='job_request',data=json.dumps({'digest':request_digest,'job_id':j.id})))
  return job_json(j)
@app.delete('/api/jobs/{id}',dependencies=[Depends(auth)])
def archive_job(id:str):
 with Session.begin() as s:
  j=get_job(s,id)
  if j.status in ['running','queued']:raise HTTPException(409,'Cancel active job first')
  data=json.loads(j.data);data['previous_status']=j.status;j.data=json.dumps(data,ensure_ascii=False);j.status='archived'
 return {'ok':True,'restore':f'/api/jobs/{id}/restore'}
@app.post('/api/jobs/{id}/published',dependencies=[Depends(auth)])
async def published(id:str,request:Request):
 body=await request.json();url=str(body.get('url',''))
 Product(name='Publication',url=url)
 with Session.begin() as s:
  j=get_job(s,id);data=json.loads(j.data);data['publication']={'url':url,'date':time.time()};j.data=json.dumps(data,ensure_ascii=False)
 return {'ok':True}
@app.post('/api/jobs/{id}/{action}',dependencies=[Depends(auth)])
def action(id:str,action:str):
 with Session.begin() as s:
  j=get_job(s,id)
  if action=='start':
   if j.status!='draft':raise HTTPException(409,'Only draft projects can start')
   data=json.loads(j.data)
   if data.get('provider')=='google':
    if not data.get('approved') or data.get('approved_budget',0)<data.get('reserved_cost',0):raise HTTPException(422,'Approve this project in Studio before starting')
    approval=data.get('approval')
    if approval and approval['fingerprint']!=google_verification.fingerprint():raise HTTPException(409,'Google configuration changed; create a new approved project')
   j.status='queued';j.stage='Queued'
  elif action=='cancel':
   if j.status=='completed':raise HTTPException(409,'Already completed')
   j.status='cancelled';j.stage='Cancelled'
  elif action in ['retry','resume']:
   if j.status not in ['failed','cancelled']:raise HTTPException(409,'Job must be failed or cancelled')
   uncertain=s.scalars(select(Operation).where(Operation.job_id==id,Operation.state.in_(['intent','submission_uncertain','rejected','failed']))).all()
   if uncertain:raise HTTPException(409,'Uncertain paid submission. Reconcile Google operation before resuming; automatic resubmission is blocked')
   j.status='queued';j.error='';j.stage='Resuming existing assets'
   data=json.loads(j.data);data.pop('last_error',None);j.data=json.dumps(data,ensure_ascii=False)
  elif action=='duplicate':
   data=json.loads(j.data);data['reserved_cost']=0;data['approved']=False
   new=Job(id=uid(),product_id=j.product_id,status='draft',data=json.dumps(data,ensure_ascii=False));s.add(new);s.flush();return job_json(new)
  elif action=='restore':
   if j.status!='archived':raise HTTPException(409,'Job is not archived')
   j.status=json.loads(j.data).get('previous_status','draft')
  else:raise HTTPException(404)
  j.updated=time.time();return job_json(j)
@app.put('/api/jobs/{id}/content',dependencies=[Depends(auth)])
def edit_content(id:str,b:Brief):
 with Session.begin() as s:
  j=get_job(s,id)
  if j.status not in ['draft','completed']:raise HTTPException(409,'Edit only drafts or completed captions')
  data=json.loads(j.data)
  if j.status=='draft':data['brief']=b.model_dump()
  else:
   data['brief']['caption']=b.caption;data['brief']['hashtags']=b.hashtags
  j.data=json.dumps(data,ensure_ascii=False)
  if j.status=='completed':
   from .media import export
   export(STORAGE/'jobs'/id,data['product_snapshot'],data)
 return {'ok':True}
@app.post('/api/jobs/{id}/assets/{kind}',dependencies=[Depends(auth)])
async def upload_asset(id:str,kind:str,file:UploadFile):
 with Session() as s:
  j=get_job(s,id)
  if j.status!='draft':raise HTTPException(409,'Upload assets before starting')
  data=json.loads(j.data)
 if kind!='narration' and not __import__('re').fullmatch(r'scene-[0-9]+',kind):raise HTTPException(422,'Invalid asset type')
 if kind.startswith('scene') and data['provider']!='manual':raise HTTPException(422,'Select Manual Flow provider to import clips')
 raw=await file.read(100*1024*1024+1)
 if len(raw)>100*1024*1024:raise HTTPException(413,'Maximum 100 MB')
 folder=STORAGE/'jobs'/id;folder.mkdir(parents=True,exist_ok=True);tmp=folder/('upload-'+uid());tmp.write_bytes(raw)
 try:
  from .media import probe
  info=probe(tmp);codec='audio' if kind=='narration' else 'video'
  if not any(x['codec_type']==codec for x in info['streams']):raise ValueError('Wrong media type')
  if codec=='video' and float(info['format']['duration'])<8:raise ValueError('Each imported scene must be at least 8 seconds')
  dest=folder/('uploaded-narration' if kind=='narration' else kind+'-import')
  tmp.replace(dest)
 except Exception:tmp.unlink(missing_ok=True);raise HTTPException(422,'Invalid media; clips must be at least 8 seconds')
 return {'ok':True}
@app.get('/api/jobs/{id}/download/{name}',dependencies=[Depends(auth)])
def download(id:str,name:str):
 if name not in ['final_video.mp4','thumbnail.jpg','export.zip','caption.txt','hashtags.txt','product_link.txt','project_metadata.json','subtitles.ass','narration.wav']:raise HTTPException(404)
 with Session() as s:
  j=get_job(s,id)
  if j.status!='completed':raise HTTPException(409,'Export not ready')
 p=STORAGE/'jobs'/id/name
 if not p.is_file():raise HTTPException(404)
 return FileResponse(p,filename=None if name.endswith(('.mp4','.jpg','.wav')) else name)
@app.get('/api/settings',dependencies=[Depends(auth)])
def settings():return dict(provider=providers.config().model_dump(),status=google_verification.current_status(),has_credentials=bool(setting('credential')),defaults=setting('defaults',{}))
@app.put('/api/settings/provider',dependencies=[Depends(auth)])
def save_provider(c:ProviderConfig):
 from .provider_settings import update_settings
 update_settings({'provider':c.model_dump(),'provider_status':{'status':'Configuration saved - live checks required','live_verified':False}})
 return {'ok':True}
@app.post('/api/settings/credentials',dependencies=[Depends(auth)])
async def save_credentials(file:UploadFile):
 raw=await file.read(65537)
 try:
  if len(raw)>65536:raise ValueError()
  info=json.loads(raw)
  if info.get('type')!='service_account' or not all(info.get(k) for k in ['private_key','client_email','project_id','token_uri']):raise ValueError()
  if info['token_uri']!='https://oauth2.googleapis.com/token':raise ValueError()
  if info.get('universe_domain','googleapis.com')!='googleapis.com':raise ValueError()
  from google.oauth2 import service_account
  service_account.Credentials.from_service_account_info(info)
 except Exception:raise HTTPException(422,'Invalid Google service-account JSON')
 from .provider_settings import update_settings
 c=providers.config();c.project=info['project_id']
 update_settings({'credential':cipher().encrypt(raw).decode(),'provider':c.model_dump(),'provider_status':{'status':'Credentials parsed - authentication and API test required','email':info['client_email'],'live_verified':False}})
 return {'email':info['client_email'],'project':info['project_id']}
@app.post('/api/settings/test',dependencies=[Depends(auth)])
def test_provider(body:ConnectionTest):
 if not body.approve_live_checks:raise HTTPException(422,'Approve the small live Gemini/TTS requests before testing; no Veo video will be submitted')
 test_id=hashlib.sha256(body.request_id.encode()).hexdigest()[:32]
 with Session.begin() as s:
  s.execute(text('BEGIN IMMEDIATE'))
  row=s.get(Record,'connection-test:'+test_id)
  if row:
   value=json.loads(row.data)
   if value.get('fingerprint',value.get('result',{}).get('fingerprint')) not in [None,google_verification.fingerprint()]:raise HTTPException(409,'Google configuration changed; run a new connection test')
   if value['state']=='running':return {'status':'Live checks pending or interrupted — automatic repetition blocked','test_id':test_id,'checks':{},'live_verified':google_verification.veo_status()['live_verified']}
   return value['result']
  if any(json.loads(r.data).get('state')=='running' and time.time()-r.created<600 for r in s.scalars(select(Record).where(Record.kind=='connection_test')).all()):raise HTTPException(409,'A connection test is already running')
  s.add(Record(id='connection-test:'+test_id,kind='connection_test',data=json.dumps({'state':'running','fingerprint':google_verification.fingerprint()})))
 try:r=providers.test_connection(test_id)
 except Exception as error:r={'status':'Connection check failed','checks':{'connection':{'status':'failed',**classify(error).public()}},'live_verified':google_verification.veo_status()['live_verified'],'veo':google_verification.veo_status()}
 with Session.begin() as s:s.get(Record,'connection-test:'+test_id).data=json.dumps({'state':'done','fingerprint':google_verification.fingerprint(),'result':r})
 set_setting('provider_status',r);return r
@app.get('/api/settings/tests/{test_id}/audio',dependencies=[Depends(auth)])
def test_audio(test_id:str):
 if not __import__('re').fullmatch(r'[a-f0-9]{32}',test_id):raise HTTPException(404)
 file=STORAGE/'provider-tests'/test_id/'preview.mp3'
 if not file.is_file():raise HTTPException(404)
 return FileResponse(file,media_type='audio/mpeg')
@app.put('/api/settings/defaults',dependencies=[Depends(auth)])
async def defaults(request:Request):
 body=await request.json()
 if len(json.dumps(body))>10000:raise HTTPException(422)
 set_setting('defaults',body);return {'ok':True}
@app.get('/api/templates',dependencies=[Depends(auth)])
def templates():
 presets=['Problem → Solution','Product Review','Quick Sales Promotion','Lifestyle Video','Premium Product Showcase','Product Demonstration','Educational Product Explanation']
 return presets+setting('templates',[])
@app.post('/api/templates',dependencies=[Depends(auth)])
async def add_template(request:Request):
 body=await request.json();name=str(body.get('name','')).strip()[:100]
 if not name:raise HTTPException(422,'Enter a template name')
 set_setting('templates',list(dict.fromkeys(setting('templates',[])+[name])));return {'ok':True}
@app.get('/api/system',dependencies=[Depends(auth)])
def system():
 beat=setting('worker_heartbeat',0)
 return dict(version='1.1.0',environment=os.getenv('APP_ENV','development'),url=os.getenv('APP_URL',''),database='ok',backend='ok',worker='online' if time.time()-beat<45 else 'offline',worker_last_seen=beat,free_disk_gb=round(shutil.disk_usage(STORAGE).free/1024**3,2),google=google_verification.current_status(),checked=time.time())
@app.exception_handler(GoogleFailure)
async def google_error(request,error):return __import__('fastapi').responses.JSONResponse({'detail':str(error),'error':error.public()},status_code=422)
@app.exception_handler(ValueError)
async def value_error(request,e):return __import__('fastapi').responses.JSONResponse({'detail':str(e)[:500]},status_code=422)
