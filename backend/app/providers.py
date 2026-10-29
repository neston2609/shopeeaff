"""Official Google SDK adapters. No network access in mock mode."""
import json, math
from google import genai
from google.genai import types
from google.oauth2 import service_account
import google.auth
from google.cloud import texttospeech,storage
from .db import setting,STORAGE
from .security import cipher
from .schemas import Brief,ProviderConfig

def config(): return ProviderConfig.model_validate(setting('provider',{}))
def credentials():
 c=config()
 if c.auth_method=='adc': return google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])[0]
 encrypted=setting('credential')
 if not encrypted: raise ValueError('Upload Google Service Account JSON first')
 info=json.loads(cipher().decrypt(encrypted.encode()))
 return service_account.Credentials.from_service_account_info(info,scopes=['https://www.googleapis.com/auth/cloud-platform'])
def client():
 c=config()
 # A billable submission must never be retried implicitly by the SDK.
 return genai.Client(vertexai=True,project=c.project,location=c.location,credentials=credentials(),http_options=types.HttpOptions(api_version='v1',timeout=120000,retry_options=types.HttpRetryOptions(attempts=1)))
def mock_brief(product,duration=30,style='Problem → Solution'):
 name=product['name']; n=math.ceil(duration/8)
 lines=[f'กำลังมองหา {name} อยู่ใช่ไหม',product.get('description','')[:180] or f'มาทำความรู้จัก {name}',f'ราคา {product["price"]:,.0f} บาท' if product.get('price') else 'ดูรายละเอียดสินค้าจากร้านค้า', 'ตรวจสอบรายละเอียดและเงื่อนไขที่ลิงก์สินค้า', 'สนใจดูเพิ่มเติมได้ที่ลิงก์สินค้า']
 return Brief(summary=product.get('description') or name,verified_features=[x for x in [name,product.get('brand'),product.get('specifications')] if x],suggestions=['แสดงสินค้าจริงจากภาพที่ได้รับอนุญาต','ใช้ภาพระยะใกล้พร้อมคำบรรยาย'],audience='ผู้ที่กำลังค้นหาสินค้าประเภทนี้',hook=lines[0],caption=f'{name} — ดูรายละเอียดและราคาปัจจุบันที่ลิงก์สินค้า (ลิงก์ Affiliate)',hashtags=['#Shopee','#ช้อปออนไลน์','#Affiliate'],scenes=[dict(number=i+1,purpose='Hook' if i==0 else 'Product details',prompt=f'Professional vertical product showcase, {name}. {style}. Preserve the exact product appearance. No invented accessories, no unsupported demonstrations, no generated text.',narration=lines[min(i,len(lines)-1)],overlay=name if i==0 else lines[min(i,len(lines)-1)][:70],duration=8,transition='fade') for i in range(n)])
def generate_brief(product,duration,style):
 prompt='Generate a natural Thai affiliate video storyboard. Use only supplied verified product facts; do not invent reviews, experiences, discounts or certifications. Separate creative suggestions. Scene visual prompts must be English. Include affiliate disclosure in caption. Each scene is 8 seconds. Return '+str(math.ceil(duration/8))+' scenes. Target seconds: '+str(duration)+' Style: '+style+' Product JSON: '+json.dumps(product,ensure_ascii=False)
 r=client().models.generate_content(model=config().text_model,contents=prompt,config=types.GenerateContentConfig(response_mime_type='application/json',response_schema=Brief,temperature=.5,max_output_tokens=8192))
 return Brief.model_validate_json(r.text)
def submit_video(scene,image=None):
 c=config()
 opts=dict(aspect_ratio='9:16',duration_seconds=8,number_of_videos=1,resolution='720p',generate_audio=False)
 if c.bucket: opts['output_gcs_uri']=f'gs://{c.bucket}/shopee-aff/'
 return client().models.generate_videos(model=c.video_model,prompt=scene['prompt'],image=types.Image.from_file(location=str(image)) if image else None,config=types.GenerateVideosConfig(**opts))
def poll_video(name): return client().operations.get(types.GenerateVideosOperation(name=name))
def download_video(video,path):
 if video.video_bytes: path.write_bytes(video.video_bytes)
 elif video.uri and video.uri.startswith('gs://'):
  bucket,key=video.uri[5:].split('/',1)
  storage.Client(project=config().project,credentials=credentials()).bucket(bucket).blob(key).download_to_filename(str(path))
 else: raise ValueError('Provider returned no supported output; configure a Google Cloud Storage bucket')
def speech(text,path,voice='th-TH-Standard-A',speed=1):
 c=texttospeech.TextToSpeechClient(credentials=credentials())
 r=c.synthesize_speech(input=texttospeech.SynthesisInput(text=text),voice=texttospeech.VoiceSelectionParams(language_code='th-TH',name=voice),audio_config=texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3,speaking_rate=speed),retry=None,timeout=60)
 path.write_bytes(r.audio_content)
def test_connection(test_id=None):
 from .google_verification import run_checks
 return run_checks(test_id or __import__('uuid').uuid4().hex)
