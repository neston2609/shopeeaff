import argparse,getpass,secrets
from .db import init,Session,User
from .security import hasher
def main():
 p=argparse.ArgumentParser();p.add_argument('--username',default='admin');p.add_argument('--generate',action='store_true');a=p.parse_args()
 password=secrets.token_urlsafe(24) if a.generate else getpass.getpass('New admin password: ')
 if len(password)<14:raise SystemExit('Password must be at least 14 characters')
 init()
 with Session.begin() as s:
  u=s.get(User,a.username)
  if u:raise SystemExit('User already exists; use a new account or deliberate password reset')
  s.add(User(id=a.username,password=hasher.hash(password)))
 if a.generate:print(password)
if __name__=='__main__':main()
