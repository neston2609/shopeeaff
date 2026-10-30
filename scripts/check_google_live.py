"""Opt-in REAL Google checks. Load production.env first. No mock adapters used."""
import argparse,json,sys,time,uuid,os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--approve-text-audio',action='store_true')
 parser.add_argument('--approved-veo-budget',type=float)
 parser.add_argument('--product-id')
 parser.add_argument('--request-id',default=None,help='Reuse this ID after an interrupted CLI session')
 args=parser.parse_args()
 if not args.approve_text_audio:parser.error('Explicit --approve-text-audio required for real billable Gemini/TTS checks')
 if args.approved_veo_budget is not None and not args.product_id:parser.error('--product-id is required for Veo generation')
 # Match the production services' identity so private generated audio remains readable by the API.
 if os.name!='nt' and os.geteuid()==0 and os.getenv('APP_ENV')=='production':
  import pwd
  account=pwd.getpwnam('shopeeaff')
  os.setgroups([]);os.setgid(account.pw_gid);os.setuid(account.pw_uid)
 from app.main import test_provider,create_job,action,job
 from app.schemas import ConnectionTest,Project
 from app import providers,budgets
 request_id=args.request_id or uuid.uuid4().hex
 print('Request ID (retain for safe retries): '+request_id,flush=True)
 result=test_provider(ConnectionTest(approve_live_checks=True,request_id=request_id))
 print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
 if args.approved_veo_budget is None:return
 p=Project(product_id=args.product_id,provider='google',duration=15,approved=True,approved_budget=args.approved_veo_budget,request_id=request_id+'-veo')
 from app.db import Session,Record
 with Session() as s:
  existing=s.get(Record,'job-request:'+p.request_id)
  existing_id=json.loads(existing.data)['job_id'] if existing else None
 if existing_id:created=job(existing_id)
 else:
  quote=budgets.quote(p,providers.config())
  print('Estimated USD: '+str(quote['estimate_usd']),flush=True)
  if quote['estimate_usd']>args.approved_veo_budget:raise SystemExit('Approved limit below estimate; no Veo request submitted')
  p.quote_id=quote['quote_id'];created=create_job(p)
 if created['status']=='draft':action(created['id'],'start')
 print('Veo job: '+created['id']+' - dedicated worker will submit and poll the real operation',flush=True)
 for _ in range(900):
  current=job(created['id'])
  if current['status']=='completed':
   print(json.dumps({'status':'completed','job_id':current['id'],'operations':current['operations'],'download':'/api/jobs/'+current['id']+'/download/final_video.mp4'},indent=2));return
  if current['status'] in ['failed','cancelled']:raise SystemExit(json.dumps({'status':current['status'],'error':current.get('last_error',current['error']),'operations':current['operations']}))
  time.sleep(2)
 raise SystemExit('Polling stopped. Saved job/operation may still run; use the same request ID. Do not submit a new request.')
if __name__=='__main__':main()
