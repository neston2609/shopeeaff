from pydantic import BaseModel,Field,field_validator,model_validator
from typing import Literal
from urllib.parse import urlparse
class Product(BaseModel):
 name:str=Field(min_length=1,max_length=200)
 url:str=Field(default='',max_length=2000)
 shop:str=Field(default='',max_length=200)
 brand:str=Field(default='',max_length=200)
 category:str=Field(default='',max_length=200)
 description:str=Field(default='',max_length=10000)
 price:float=Field(default=0,ge=0,le=10000000)
 discount:str=Field(default='',max_length=300)
 specifications:str=Field(default='',max_length=4000)
 notes:str=Field(default='',max_length=4000)
 images:list[str]=Field(default_factory=list,max_length=20)
 @field_validator('images')
 @classmethod
 def valid_images(cls,v):
  import re
  if any(not re.fullmatch(r'[a-f0-9]{32}\.jpg',name) for name in v):raise ValueError('Invalid image identifier')
  return v
 @field_validator('url')
 @classmethod
 def valid_url(cls,v):
  if v:
   u=urlparse(v)
   if u.scheme!='https' or not u.hostname or not any(u.hostname==h or u.hostname.endswith('.'+h) for h in ['shopee.co.th','shopee.com','shope.ee','s.shopee.co.th']): raise ValueError('Use an HTTPS Shopee URL')
  return v
class Scene(BaseModel):
 number:int=Field(ge=1,le=20)
 purpose:str=Field(max_length=300)
 prompt:str=Field(min_length=1,max_length=3000)
 narration:str=Field(max_length=1500)
 overlay:str=Field(max_length=160)
 duration:Literal[8]=8
 transition:Literal['cut','fade']='fade'
 subtitle_start:float=Field(default=0,ge=0,lt=8)
 subtitle_end:float=Field(default=8,gt=0,le=8)
 @model_validator(mode='after')
 def timing(self):
  if self.subtitle_end<=self.subtitle_start:raise ValueError('Subtitle end must be after start')
  return self
class Brief(BaseModel):
 summary:str
 verified_features:list[str]
 suggestions:list[str]
 audience:str
 hook:str
 caption:str
 hashtags:list[str]
 scenes:list[Scene]=Field(min_length=1,max_length=15)
class Project(BaseModel):
 product_id:str
 provider:Literal['mock','google','manual']='mock'
 duration:Literal[15,20,30,45,60]=30
 style:str=Field(default='Problem → Solution',max_length=100)
 accuracy:bool=True
 voice:str=Field(default='th-TH-Standard-A',max_length=100)
 speed:float=Field(default=1,ge=.5,le=2)
 narration:bool=True
 subtitles:bool=True
 music:bool=False
 resolution:Literal['1080','720']='1080'
 subtitle_size:int=Field(default=52,ge=28,le=90)
 subtitle_color:str=Field(default='FFFFFF',pattern=r'^[A-Fa-f0-9]{6}$')
 subtitle_margin:int=Field(default=290,ge=140,le=600)
 approved_budget:float=Field(default=0,ge=0,le=1000)
 approved:bool=False
 brief:Brief|None=None
 regenerate_source:str|None=Field(default=None,pattern=r'^[a-f0-9]{32}$')
 regenerate_scene:int|None=Field(default=None,ge=0,le=14)
 regenerate_voice:bool=False
 quote_id:str|None=Field(default=None,pattern=r'^[a-f0-9]{32}$')
 request_id:str|None=Field(default=None,min_length=16,max_length=80,pattern=r'^[a-zA-Z0-9_-]+$')
class ConnectionTest(BaseModel):
 approve_live_checks:bool=False
 request_id:str=Field(min_length=16,max_length=80,pattern=r'^[a-zA-Z0-9_-]+$')
class ProviderConfig(BaseModel):
 auth_method:Literal['service_account','adc']='service_account'
 project:str=Field(default='',max_length=200,pattern=r'^[a-zA-Z0-9._:-]*$')
 location:str=Field(default='us-central1',pattern=r'^[a-z0-9-]+$')
 video_model:str=Field(default='veo-3.1-fast-generate-001',max_length=150,pattern=r'^veo-[a-zA-Z0-9.-]+$')
 text_model:str=Field(default='gemini-2.5-flash',pattern=r'^[a-zA-Z0-9.-]+$')
 bucket:str=Field(default='',pattern=r'^[a-z0-9._-]*$')
 video_rate:float=Field(default=.15,ge=0,le=20)
 text_reserve:float=Field(default=.1,ge=.01,le=100)
 tts_rate:float=Field(default=.000016,gt=0,le=1)
 pricing_verified:str=Field(default='Unverified — configure before paid use',max_length=100)
 daily_budget:float=Field(default=10,ge=0,le=10000)
 monthly_budget:float=Field(default=100,ge=0,le=100000)
 max_video:float=Field(default=10,ge=0,le=1000)
