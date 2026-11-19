import argparse,getpass,secrets
from sqlalchemy import text
from .db import init,Session,User
from .security import hasher,revoke_user_sessions
def main():
 p=argparse.ArgumentParser();p.add_argument('--username',default='admin');p.add_argument('--generate',action='store_true');p.add_argument('--reset',action='store_true',help='Reset an existing user and revoke their sessions');a=p.parse_args()
 password=secrets.token_urlsafe(24) if a.generate else getpass.getpass('New admin password: ')
 if not 14<=len(password)<=128:raise SystemExit('Password must contain 14 to 128 characters')
 init()
 with Session.begin() as s:
  s.execute(text('BEGIN IMMEDIATE'))
  u=s.get(User,a.username)
  if a.reset:
   if not u:raise SystemExit('User not found')
   u.password=hasher.hash(password);revoke_user_sessions(s,a.username)
  else:
   if u:raise SystemExit('User already exists; use --reset for a deliberate password reset')
   s.add(User(id=a.username,password=hasher.hash(password)))
 if a.generate:print(password)
if __name__=='__main__':main()
