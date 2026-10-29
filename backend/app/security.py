import os,secrets,time,hashlib
from cryptography.fernet import Fernet
from argon2 import PasswordHasher
from fastapi import HTTPException,Request
from .db import Session,LoginSession
hasher=PasswordHasher()
def cipher():
 key=os.getenv('CREDENTIAL_ENCRYPTION_KEY')
 if not key: raise RuntimeError('CREDENTIAL_ENCRYPTION_KEY must be configured')
 return Fernet(key.encode())
def digest(token): return hashlib.sha256(token.encode()).hexdigest()
def auth(request:Request):
 token=request.cookies.get('studio_session','')
 with Session() as s:
  row=s.get(LoginSession,digest(token))
  if not row or row.expires<time.time(): raise HTTPException(401,'Please sign in')
  if request.method not in ('GET','HEAD','OPTIONS'):
   if not secrets.compare_digest(request.headers.get('x-csrf-token',''),row.csrf): raise HTTPException(403,'Invalid CSRF token')
 return row
