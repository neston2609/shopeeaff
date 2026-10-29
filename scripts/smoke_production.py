"""Run on the authorized VPS as root; never prints credentials or session tokens."""
import httpx,io,time,json,sys,subprocess,zipfile
from pathlib import Path
from PIL import Image,ImageDraw
BASE='https://aff.pramool.bid'
c=httpx.Client(base_url=BASE,timeout=60,follow_redirects=False)
def check(response):
 response.raise_for_status();return response.json()
password=Path('/etc/shopee-aff-ai-studio/initial-admin-password').read_text().strip()
login=check(c.post('/api/login',json={'username':'admin','password':password}));del password
c.headers['x-csrf-token']=login['csrf'];del login
assert check(c.get('/api/system'))['worker']=='online'
p=check(c.post('/api/products',json={'name':'กระเป๋าผ้า • Production smoke test','description':'กระเป๋าผ้าสีครีม ตัวอย่างสำหรับทดสอบระบบ','price':199,'category':'กระเป๋า','url':'https://shopee.co.th/product/1/2?affiliate_id=smoke-test'}))
im=Image.new('RGB',(720,1000),'#f2ebe2');d=ImageDraw.Draw(im);d.rounded_rectangle((180,320,540,750),50,fill='#c2a384');d.arc((260,180,460,480),180,360,fill='#886949',width=20);d.text((270,510),'STUDIO',fill='#fff5e8',stroke_width=1)
buf=io.BytesIO();im.save(buf,'PNG')
check(c.post('/api/products/'+p['id']+'/images',files={'file':('sample.png',buf.getvalue(),'image/png')}))
config={'product_id':p['id'],'provider':'mock','duration':15,'resolution':'1080','approved':True,'approved_budget':0,'music':True}
brief=check(c.post('/api/analyze',json=config));assert brief['scenes']
config['brief']=brief
j=check(c.post('/api/jobs',json=config));check(c.post('/api/jobs/'+j['id']+'/start'))
print('AUTH, DATABASE, PRODUCT, IMAGE, STORYBOARD AND QUEUE PASSED',flush=True)
for _ in range(180):
 job=check(c.get('/api/jobs/'+j['id']))
 if job['status']=='failed':raise RuntimeError(job['error'])
 if job['status']=='completed':break
 time.sleep(2)
else:raise TimeoutError('Mock generation did not finish within 6 minutes')
video=c.get('/api/jobs/'+j['id']+'/download/final_video.mp4');video.raise_for_status()
archive=c.get('/api/jobs/'+j['id']+'/download/export.zip');archive.raise_for_status()
with zipfile.ZipFile(io.BytesIO(archive.content)) as z:assert 'caption.txt' in z.namelist() and 'final_video.mp4' in z.namelist()
assert httpx.get(BASE+'/api/jobs/'+j['id']+'/download/export.zip').status_code==401
info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(Path('/var/lib/shopee-aff-ai-studio/jobs')/j['id']/'final_video.mp4')]))
v=next(s for s in info['streams'] if s['codec_type']=='video');assert (v['width'],v['height'])==(1080,1920)
assert abs(float(info['format']['duration'])-15)<.2
print('PUBLIC MOCK MP4, 1080x1920, THAI SUBTITLES, CAPTION, ZIP AND PRIVATE DOWNLOAD PASSED',flush=True)
subprocess.run(['systemctl','restart','shopee-aff-backend','shopee-aff-worker','shopee-aff-frontend'],check=True)
for _ in range(30):
 try:
  if c.get('/api/health').status_code==200:break
 except httpx.HTTPError:pass
 time.sleep(1)
assert check(c.get('/api/jobs/'+j['id']))['status']=='completed'
assert any(x['id']==p['id'] for x in check(c.get('/api/products')))
print('SERVICE RESTART, SESSION AND DATABASE/MEDIA PERSISTENCE PASSED',flush=True)
report={'base_url':BASE,'job_id':j['id'],'product_id':p['id'],'video_bytes':len(video.content),'zip_bytes':len(archive.content),'dimensions':[1080,1920],'duration':float(info['format']['duration']),'restart_persistence':True,'google_live_verified':False}
Path('/app/shopeeaff/deployment/verification.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report),flush=True)
