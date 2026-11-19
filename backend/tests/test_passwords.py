"""Account password changes, identity binding and session revocation."""
import uuid
import pytest
from fastapi.testclient import TestClient
from test_studio import app
from app.db import Session,User,Record
from app.security import hasher,revoke_user_sessions

OLD='isolated-old-password!'
NEW='isolated-new-password!'

@pytest.fixture
def account():
 name='password-test-'+uuid.uuid4().hex
 with Session.begin() as s:
  s.query(Record).filter(Record.kind=='ratelimit').delete()
  s.add(User(id=name,password=hasher.hash(OLD)))
 yield name
 with Session.begin() as s:
  revoke_user_sessions(s,name)
  s.delete(s.get(User,name))

def sign_in(name,password=OLD):
 c=TestClient(app)
 r=c.post('/api/login',json={'username':name,'password':password})
 assert r.status_code==200
 c.headers['x-csrf-token']=r.json()['csrf']
 return c

def body():return dict(current_password=OLD,new_password=NEW,confirm_password=NEW)

def test_change_uses_session_identity_and_revokes_all_own_sessions(account):
 first=sign_in(account);second=sign_in(account)
 assert first.get('/api/me').json()['username']==account
 r=first.post('/api/account/password',json=body())
 assert r.status_code==200 and r.json()['sign_in_required']
 assert first.get('/api/me').status_code==401
 assert second.get('/api/products').status_code==401
 assert TestClient(app).post('/api/login',json={'username':account,'password':OLD}).status_code==401
 assert sign_in(account,NEW).get('/api/me').json()['username']==account
 with Session() as s:
  saved=s.get(User,account).password
  assert NEW not in saved and hasher.verify(saved,NEW)

def test_password_change_requires_auth_csrf_and_current_password(account):
 assert TestClient(app).post('/api/account/password',json=body()).status_code==401
 c=sign_in(account);csrf=c.headers.pop('x-csrf-token')
 assert c.post('/api/account/password',json=body()).status_code==403
 c.headers['x-csrf-token']=csrf
 request=body();request['current_password']='wrong-private-password'
 r=c.post('/api/account/password',json=request)
 assert r.status_code==400 and 'private' not in r.text and NEW not in r.text
 assert sign_in(account).get('/api/me').status_code==200

@pytest.mark.parametrize('changes',[{'new_password':'short','confirm_password':'short'},{'confirm_password':'mismatch'},{'new_password':OLD,'confirm_password':OLD},{'new_password':{'private':'secret'}},{'new_password':'x'*129}])
def test_invalid_password_input_is_safe(account,changes):
 c=sign_in(account);request=body();request.update(changes)
 r=c.post('/api/account/password',json=request)
 assert r.status_code==422 and OLD not in r.text and NEW not in r.text and 'secret' not in r.text

def test_wrong_current_password_attempts_are_limited(account):
 c=sign_in(account);request=body();request['current_password']='wrong'
 for _ in range(5):assert c.post('/api/account/password',json=request).status_code==400
 assert c.post('/api/account/password',json=body()).status_code==429

def test_change_does_not_revoke_another_account(account):
 other='password-test-'+uuid.uuid4().hex
 with Session.begin() as s:s.add(User(id=other,password=hasher.hash(OLD)))
 try:
  first=sign_in(account);second=sign_in(other)
  assert first.post('/api/account/password',json=body()).status_code==200
  assert second.get('/api/me').json()['username']==other
 finally:
  with Session.begin() as s:
   revoke_user_sessions(s,other);s.delete(s.get(User,other))

def test_legacy_unbound_session_cannot_change_another_account(account):
 c=sign_in(account)
 with Session.begin() as s:
  for row in s.query(Record).filter(Record.kind=='session_owner').all():
   if account in row.data:s.delete(row)
 assert c.get('/api/me').status_code==401
 assert c.post('/api/account/password',json=body()).status_code==401

def test_admin_recovery_requires_explicit_reset_and_revokes_sessions(account,monkeypatch):
 import sys
 from app import admin
 c=sign_in(account)
 monkeypatch.setattr(admin.getpass,'getpass',lambda _:NEW)
 monkeypatch.setattr(sys,'argv',['admin','--username',account])
 with pytest.raises(SystemExit,match='already exists'):admin.main()
 assert c.get('/api/me').status_code==200
 monkeypatch.setattr(sys,'argv',['admin','--username',account,'--reset'])
 admin.main()
 assert c.get('/api/me').status_code==401
 assert sign_in(account,NEW).get('/api/me').json()['username']==account
