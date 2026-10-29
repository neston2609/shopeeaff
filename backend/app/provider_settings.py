"""Serialize provider changes with job/test state checks without replacing existing data."""
import json,time
from sqlalchemy import select,text
from fastapi import HTTPException
from .db import Session,Record,Job

def update_settings(changes):
 with Session.begin() as s:
  s.execute(text('BEGIN IMMEDIATE'))
  if any(json.loads(j.data).get('provider')=='google' for j in s.scalars(select(Job).where(Job.status.in_(['queued','running']))).all()):raise HTTPException(409,'Wait for active Google jobs before changing provider configuration or credentials')
  if any(json.loads(r.data).get('state')=='running' and time.time()-r.created<600 for r in s.scalars(select(Record).where(Record.kind=='connection_test')).all()):raise HTTPException(409,'Wait for live connection checks before changing provider configuration or credentials')
  for key,value in changes.items():
   row=s.get(Record,'setting:'+key)
   if not row:row=Record(id='setting:'+key,kind='setting');s.add(row)
   row.data=json.dumps(value,ensure_ascii=False)
