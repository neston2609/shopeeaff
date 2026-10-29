import os, json, time
from pathlib import Path
from sqlalchemy import create_engine, event, Column, String, Text, Float, Integer
from sqlalchemy.orm import DeclarativeBase, sessionmaker

STORAGE=Path(os.getenv('STORAGE_PATH','data')).resolve()
STORAGE.mkdir(parents=True,exist_ok=True)
engine=create_engine(os.getenv('DATABASE_URL',f'sqlite:///{STORAGE}/studio.db'),connect_args={'check_same_thread':False,'timeout':30})
@event.listens_for(engine,'connect')
def pragmas(dbapi, _):
 dbapi.execute('PRAGMA journal_mode=WAL'); dbapi.execute('PRAGMA foreign_keys=ON'); dbapi.execute('PRAGMA busy_timeout=30000')
Session=sessionmaker(engine,expire_on_commit=False)
class Base(DeclarativeBase): pass
class Record(Base):
 __tablename__='records'
 id=Column(String,primary_key=True)
 kind=Column(String,index=True,nullable=False)
 data=Column(Text,nullable=False,default='{}')
 created=Column(Float,default=time.time,index=True)
class User(Base):
 __tablename__='users'
 id=Column(String,primary_key=True)
 password=Column(Text,nullable=False)
class LoginSession(Base):
 __tablename__='sessions'
 id=Column(String,primary_key=True)
 expires=Column(Float,index=True,nullable=False)
 csrf=Column(String,nullable=False)
class Job(Base):
 __tablename__='generation_jobs'
 id=Column(String,primary_key=True)
 product_id=Column(String,index=True,nullable=False)
 status=Column(String,index=True,default='draft')
 progress=Column(Integer,default=0)
 stage=Column(String,default='draft')
 data=Column(Text,default='{}')
 error=Column(Text,default='')
 created=Column(Float,default=time.time,index=True)
 updated=Column(Float,default=time.time)
 lease=Column(Float,default=0)
class Operation(Base):
 __tablename__='provider_operations'
 id=Column(String,primary_key=True)
 job_id=Column(String,index=True,nullable=False)
 state=Column(String,default='intent')
 name=Column(Text,default='')
 cost=Column(Float,default=0)
 created=Column(Float,default=time.time,index=True)
def init(): Base.metadata.create_all(engine)
def payload(r): return dict(id=r.id,created=r.created,**json.loads(r.data))
def setting(key,default=None):
 with Session() as s:
  r=s.get(Record,'setting:'+key)
  return json.loads(r.data) if r else default
def set_setting(key,value):
 with Session.begin() as s:
  r=s.get(Record,'setting:'+key)
  if not r: r=Record(id='setting:'+key,kind='setting');s.add(r)
  r.data=json.dumps(value,ensure_ascii=False)
