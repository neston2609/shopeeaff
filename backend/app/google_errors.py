"""Public-safe provider failures. Never return or log exception bodies or credentials."""
import socket
import httpx
from google.auth.exceptions import RefreshError,DefaultCredentialsError

MESSAGES={
 'authentication':'Google authentication failed. Re-upload a valid service account or check ADC.',
 'permission':'Google denied access. Check IAM permissions and enabled APIs for this project.',
 'quota':'Google quota or rate limit exceeded. Check Cloud quotas before resuming the saved operation.',
 'billing':'Google Cloud billing is disabled or unavailable. Check the billing account for this project.',
 'model_unavailable':'Model or region unavailable. Check the configured Veo/Gemini model, region and project access.',
 'timeout':'Google request timed out. A submitted request may still be running; do not submit another video.',
 'generation_failed':'Google video operation failed or returned no video. Check the provider operation before approving a new generation.',
 'unavailable':'Google service is temporarily unavailable. Resume polling the saved operation; no new video will be submitted.',
 'configuration':'Google configuration is incomplete or invalid. Check project, region, model and credentials.',
 'provider_error':'Google request failed. Check project configuration and the Google Cloud console.',
 'submission_uncertain':'A paid submission may have been accepted but no operation ID was saved. Automatic resubmission is blocked; reconcile it in Google Cloud.',
}
class GoogleFailure(Exception):
 def __init__(self,category,*,uncertain=False,provider_code=None):
  self.category=category;self.uncertain=uncertain;self.provider_code=provider_code
  super().__init__(MESSAGES.get(category,MESSAGES['provider_error']))
 def public(self):return {'category':self.category,'message':str(self),'submission_uncertain':self.uncertain,**({'provider_code':self.provider_code} if self.provider_code is not None else {})}

def classify(error):
 if isinstance(error,GoogleFailure):return error
 # Inspect raw provider text only to categorize it; never persist/return it.
 raw=str(error).lower()
 code=getattr(error,'code',None)
 if callable(code):
  try:code=code()
  except Exception:code=None
 response=getattr(error,'response',None)
 if response is not None and getattr(response,'status_code',None) is not None:code=response.status_code
 code=getattr(code,'value',code)
 if isinstance(code,tuple):code=code[0]
 code=str(code).upper()
 if any(w in raw for w in ['billing_disabled','billingnotenabled','billing account','billing is','billing must','billing not enabled']):category='billing'
 elif isinstance(error,(RefreshError,DefaultCredentialsError)) or '401' in code or code=='16' or 'UNAUTHENTICATED' in code:category='authentication'
 elif '429' in code or code=='8' or 'RESOURCE_EXHAUSTED' in code:category='quota'
 elif '403' in code or code=='7' or 'PERMISSION_DENIED' in code:category='permission'
 elif '404' in code or code=='5' or 'NOT_FOUND' in code or ('model' in raw and any(w in raw for w in ['not found','not supported','unavailable'])):category='model_unavailable'
 elif isinstance(error,(TimeoutError,socket.timeout,httpx.TimeoutException)) or code=='4' or 'DEADLINE_EXCEEDED' in code or 'timeout' in raw or 'timed out' in raw:category='timeout'
 elif code in ['13','14'] or any(w in code for w in ['500','502','503','504','UNAVAILABLE','INTERNAL']):category='unavailable'
 elif '400' in code or isinstance(error,ValueError):category='configuration'
 elif 'quota exceeded' in raw or 'rate limit' in raw:category='quota'
 else:category='provider_error'
 return GoogleFailure(category,provider_code=int(code) if code.isdigit() else None)
