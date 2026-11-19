import io,json,zipfile
from fastapi.testclient import TestClient
from test_studio import app,c
from app.browser_tools import FILES
from app import product_fetch

def test_helper_download_requires_auth_and_contains_only_reviewable_sources(c):
 assert TestClient(app).get('/api/tools/browser-import-extension.zip').status_code==401
 r=c.get('/api/tools/browser-import-extension.zip');assert r.status_code==200
 assert 'attachment' in r.headers['content-disposition']
 with zipfile.ZipFile(io.BytesIO(r.content)) as package:
  assert set(package.namelist())==set(FILES)
  manifest=json.loads(package.read('manifest.json'))
  assert manifest['permissions']==['activeTab','scripting'] and 'host_permissions' not in manifest
  assert all('..' not in name and not name.startswith('/') for name in package.namelist())

def test_restricted_product_redirect_still_identifies_browser_import_target(monkeypatch):
 original='https://s.shopee.co.th/example?share_channel_code=6'
 replies=[(302,{'location':'https://shopee.co.th/product/1873957794/45613484259'},b''),(403,{},b'private challenge')]
 monkeypatch.setattr(product_fetch,'request_page',lambda *_:replies.pop(0))
 result=product_fetch.fetch_information(original)
 assert result['status']=='metadata_unavailable' and result['data']=={}
 assert result['original_url']==original and result['product_reference']['item_id']=='45613484259'
 assert 'Chrome' in result['warnings'][0] and 'private challenge' not in str(result)
