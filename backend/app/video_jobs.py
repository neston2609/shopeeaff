"""At-most-once Veo submission; recover/poll/download an existing operation on retry."""
import time,json
from sqlalchemy import select,text
from .db import Session,Job,Operation
from .google_errors import GoogleFailure,classify
from . import providers,media,google_verification

def generate_scene(job_id,index,scene,path,image,progress,stop):
 key=f'{job_id}:scene:{index}'
 with Session.begin() as s:
  s.execute(text('BEGIN IMMEDIATE'))
  job=s.get(Job,job_id);data=json.loads(job.data)
  if job.status=='cancelled':raise InterruptedError('Cancelled')
  approval=data.get('approval')
  if not data.get('approved') or data.get('reserved_cost',0)>data.get('approved_budget',0):raise GoogleFailure('configuration')
  if approval and approval['fingerprint']!=google_verification.fingerprint():raise GoogleFailure('configuration')
  op=s.get(Operation,key);new=op is None
  if new:
   cost=8*data['pricing_snapshot']['video_rate']
   used=sum(o.cost for o in s.scalars(select(Operation).where(Operation.job_id==job_id)).all())
   if used+cost>data['approved_budget']:raise GoogleFailure('configuration')
   s.add(Operation(id=key,job_id=job_id,state='intent',cost=cost));name=None
  else:
   name=op.name
   if not name:raise GoogleFailure('submission_uncertain',uncertain=True)
   if op.state=='failed':raise GoogleFailure('generation_failed')
 if new:
  try:
   operation=providers.submit_video(scene,image);name=operation.name
   if not name:raise GoogleFailure('submission_uncertain',uncertain=True)
  except Exception as error:
   failure=classify(error)
   # Even timeout/transport errors may follow a server-side accepted request.
   state='rejected' if failure.category in ['authentication','permission','quota','billing','model_unavailable','configuration'] else 'submission_uncertain'
   with Session.begin() as s:s.get(Operation,key).state=state
   raise GoogleFailure(failure.category,uncertain=state=='submission_uncertain') from None
  with Session.begin() as s:
   row=s.get(Operation,key);row.name=name;row.state='polling'
 deadline=time.monotonic()+7200
 for attempt in range(720):
  if time.monotonic()>deadline:raise GoogleFailure('timeout')
  progress(job_id,f'Polling Google scene {index+1}',15+int(50*index/max(1,len(data.get('brief',{}).get('scenes',[])))))
  try:operation=providers.poll_video(name)
  except Exception as error:
   failure=classify(error)
   if failure.category in ['timeout','quota','unavailable'] and attempt<719:
    if stop.wait(min(30,5+attempt)):raise InterruptedError('Worker stopping; operation saved')
    continue
   raise failure from None
  if operation.done:break
  if stop.wait(10):raise InterruptedError('Worker stopping; operation saved')
 else:raise GoogleFailure('timeout')
 if operation.error:
  # Do not persist the provider's raw error message (it may echo request contents).
  raw=operation.error
  failure=classify(_OperationError(raw))
  if failure.category=='provider_error':failure=GoogleFailure('generation_failed')
  with Session.begin() as s:s.get(Operation,key).state='failed'
  raise failure from None
 result=operation.response or operation.result
 if not result or not result.generated_videos:
  with Session.begin() as s:s.get(Operation,key).state='failed'
  raise GoogleFailure('generation_failed')
 # An interrupted download cannot leave a partially valid scene used on recovery.
 tmp=path.with_suffix('.download.mp4')
 try:
  providers.download_video(result.generated_videos[0].video,tmp);media.validate(tmp);tmp.replace(path)
 except Exception as error:
  tmp.unlink(missing_ok=True)
  raise classify(error) from None
 with Session.begin() as s:s.get(Operation,key).state='done'
 google_verification.record_veo_success(job_id,name)

class _OperationError(Exception):
 def __init__(self,value):
  self.code=value.get('code') if isinstance(value,dict) else getattr(value,'code',None)
  super().__init__(value.get('message','') if isinstance(value,dict) else str(value))
