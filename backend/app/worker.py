import time,json,logging,signal,threading,os
from sqlalchemy import select,text
from .db import *
from . import providers,media
stop=threading.Event()
logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
def update(id,stage,progress):
 with Session.begin() as s:
  j=s.get(Job,id)
  if j.status=='cancelled':raise InterruptedError('Cancelled')
  j.stage=stage;j.progress=progress;j.updated=time.time();j.lease=time.time()+120
def heartbeat():
 while not stop.is_set():
  set_setting('worker_heartbeat',time.time());stop.wait(10)
def save_data(id,data):
 with Session.begin() as s:s.get(Job,id).data=json.dumps(data,ensure_ascii=False)
def pipeline(id):
 with Session() as s:j=s.get(Job,id);data=json.loads(j.data);product=data['product_snapshot']
 folder=STORAGE/'jobs'/id;folder.mkdir(parents=True,exist_ok=True)
 if data['provider']=='google' and not data.get('approved'):raise ValueError('Duplicate project needs new cost approval; create a new approved project')
 if data['provider']=='google' and providers.config().model_dump()!=data['pricing_snapshot']:raise ValueError('Provider configuration changed since cost approval. Create a new project with a fresh estimate.')
 update(id,'Analyzing product and creating Thai storyboard',8)
 if not data.get('brief'):
  # Intent prevents duplicate Gemini requests after a crash.
  with Session.begin() as s:
   op=s.get(Operation,id+':text')
   if op:raise ValueError('Content request needs reconciliation; no automatic paid resubmission')
   s.add(Operation(id=id+':text',job_id=id,state='intent',cost=data['pricing_snapshot']['text_reserve']))
  brief=providers.generate_brief(product,data['duration'],data['style']);data['brief']=brief.model_dump();save_data(id,data)
  with Session.begin() as s:s.get(Operation,id+':text').state='done'
 scenes=data['brief']['scenes']
 if len(scenes)!=__import__('math').ceil(data['duration']/8):raise ValueError('Storyboard scene count does not match approved estimate')
 image=STORAGE/'uploads'/product['images'][0] if product.get('images') else None
 for i,scene in enumerate(scenes):
  update(id,f'Generating scene {i+1}/{len(scenes)}',15+int(50*i/len(scenes)))
  path=folder/f'scene-{i}.mp4'
  if path.exists():
   try:media.validate(path);continue
   except Exception:path.unlink()
  if data['provider']=='mock':media.demo_scene(path,image,i)
  elif data['provider']=='manual':
   source=folder/f'scene-{i}-import'
   if not source.exists():raise ValueError(f'Upload Google Flow clip {i+1} before starting')
   media.run(['ffmpeg','-y','-i',str(source),'-t','8','-an','-vf','scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=25','-c:v','libx264','-preset','veryfast','-pix_fmt','yuv420p','-threads','2',str(path)])
  else:
   from .video_jobs import generate_scene
   generate_scene(id,i,scene,path,image if data['accuracy'] else None,update,stop)
 update(id,'Generating narration (mock uses silence unless uploaded)',72)
 media.narration(folder,scenes,data,providers.speech)
 update(id,'Composing vertical MP4 and Thai subtitles',82)
 info=media.compose(folder,scenes,data,product)
 update(id,'Validating and packaging export',95)
 data['media']={'duration':float(info['format']['duration']),'mock':data['provider']=='mock'};data['accuracy_review_required']=True
 media.export(folder,product,data);save_data(id,data)
 with Session.begin() as s:
  j=s.get(Job,id)
  if j.status=='cancelled':raise InterruptedError('Cancelled')
  j.status='completed';j.stage='Completed — review product accuracy before publishing';j.progress=100;j.updated=time.time();j.error=''

def recover():
 with Session.begin() as s:
  for j in s.scalars(select(Job).where(Job.status=='running')).all():j.status='queued';j.stage='Recovered after restart'
def claim():
 with Session.begin() as s:
  s.execute(text('BEGIN IMMEDIATE'))
  j=s.scalar(select(Job).where(Job.status=='queued').order_by(Job.created).limit(1))
  if j:j.status='running';j.updated=time.time();return j.id
 return None
def main():
 init()
 # Only one dedicated worker owns this SQLite queue. flock releases automatically after a crash.
 lock=open(STORAGE/'worker.lock','w')
 if os.name!='nt':
  import fcntl
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 for sig in [signal.SIGINT,signal.SIGTERM]:signal.signal(sig,lambda *_:stop.set())
 threading.Thread(target=heartbeat,daemon=True).start()
 recover()
 while not stop.is_set():
  id=claim()
  if not id:stop.wait(2);continue
  try:pipeline(id)
  except Exception as e:
   from .google_errors import classify
   with Session() as s: is_google=json.loads(s.get(Job,id).data).get('provider')=='google'
   safe=classify(e) if is_google else None
   logging.warning('Job %s failed: %s',id,safe.category if safe else type(e).__name__)
   with Session.begin() as s:
    j=s.get(Job,id)
    if j.status!='cancelled':j.status='queued' if stop.is_set() else 'failed'
    j.error=str(safe) if safe else str(e)[-1500:];j.updated=time.time()
    if safe:
     data=json.loads(j.data);data['last_error']=safe.public();j.data=json.dumps(data,ensure_ascii=False)
if __name__=='__main__':main()
