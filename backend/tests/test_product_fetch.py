"""Public metadata extraction and SSRF boundaries; no live Shopee calls in tests."""
import json,socket,time
from types import SimpleNamespace as NS
import pytest
from fastapi.testclient import TestClient
from test_studio import app,c
from app import product_fetch as f
from app.db import Session,Record

URL='https://s.shopee.co.th/exampleAffiliate'
FINAL='https://shopee.co.th/product/123/456?affiliate_id=original'

def html(product=None):
 product=product or {'@type':'Product','name':'Thai product','description':'<p>Verified description</p><script>bad()</script>','brand':{'name':'Brand'},'category':'Bags','offers':{'price':'1,299.50','priceCurrency':'THB','seller':{'name':'Shop'}},'additionalProperty':[{'name':'Color','value':'Cream'}]}
 return '<script type="application/ld+json">'+json.dumps(product).replace('<',r'\u003c')+'</script>'

def test_structured_metadata_is_plain_text_and_does_not_invent_fields():
 data,warnings=f.extract(html(),FINAL)
 assert data=={'name':'Thai product','description':'Verified description','brand':'Brand','category':'Bags','shop':'Shop','price':1299.5,'specifications':'Color: Cream'}
 assert warnings and 'discount' not in data and 'images' not in data

def test_public_open_graph_fallback_and_missing_price_currency():
 data,_=f.extract('<meta property="og:type" content="product"><meta property="og:title" content="A &amp; B"><meta property="product:price:amount" content="99">',FINAL)
 assert data=={'name':'A & B'}
 with pytest.raises(f.FetchFailure):f.extract('<meta property="og:title" content="Shopee">',FINAL)

def test_graph_and_multiple_products_are_not_confused():
 product={'@graph':[{'@type':'Product','name':'Related','url':'/product/1/2'},{'@type':'Product','name':'Actual','url':'/product/123/456'}]}
 assert f.extract(html(product),FINAL)[0]['name']=='Actual'
 with pytest.raises(f.FetchFailure):f.extract(html({'@graph':[{'@type':'Product','name':'A'},{'@type':'Product','name':'B'}]}),FINAL)

@pytest.mark.parametrize('url',['http://shopee.co.th/product/1/2','https://127.0.0.1/','https://shopee.co.th.evil.example/','https://shopee.co.th:444/','https://name:password@shopee.co.th/','https://shopee.co.th/\nHeader: x','https://shopee.co.th\\@evil.example/'])
def test_invalid_targets_are_rejected(url):
 with pytest.raises(f.FetchFailure):f.validate_url(url)

def test_dns_rebinding_is_prevented_before_connect(monkeypatch):
 monkeypatch.setattr(f.socket,'getaddrinfo',lambda *_a,**_k:[(None,None,None,None,('203.0.113.10',443)),(None,None,None,None,('127.0.0.1',443))])
 with pytest.raises(f.FetchFailure,match='non-public'):f.public_addresses('shopee.co.th')

def test_tls_connect_uses_pinned_public_ip_and_original_hostname(monkeypatch):
 seen={};raw=NS(close=lambda:None)
 monkeypatch.setattr(f.socket,'create_connection',lambda address,timeout:seen.update(address=address) or raw)
 connection=f.PinnedHTTPS('shopee.co.th','8.8.8.8',3)
 connection._context=NS(wrap_socket=lambda sock,server_hostname:seen.update(host=server_hostname) or sock)
 connection.connect()
 assert seen=={'address':('8.8.8.8',443),'host':'shopee.co.th'}

def test_redirects_preserve_original_affiliate_link_and_block_external_hosts(monkeypatch):
 replies=[(301,{'location':FINAL},b''),(200,{},html().encode())]
 monkeypatch.setattr(f,'request_page',lambda *_:replies.pop(0))
 result=f.fetch_information(URL)
 assert result['original_url']==URL and 'url' not in result['data']
 assert result['source_url']=='https://shopee.co.th/product/123/456'
 monkeypatch.setattr(f,'request_page',lambda *_:(302,{'location':'https://127.0.0.1/private'},b''))
 with pytest.raises(f.FetchFailure):f.fetch_information(URL)

def test_fetch_is_authenticated_csrf_protected_and_does_not_save(c,monkeypatch):
 assert TestClient(app).post('/api/products/fetch-information',json={'url':URL}).status_code==401
 csrf=c.headers.pop('x-csrf-token')
 assert c.post('/api/products/fetch-information',json={'url':URL}).status_code==403
 c.headers['x-csrf-token']=csrf
 monkeypatch.setattr(f,'request_page',lambda *_:(200,{},html().encode()))
 before=c.get('/api/products').json()
 r=c.post('/api/products/fetch-information',json={'url':URL})
 assert r.status_code==200 and r.json()['data']['name']=='Thai product'
 assert c.get('/api/products').json()==before
 assert c.post('/api/products/fetch-information',json={'url':'https://127.0.0.1/'}).status_code==422

def test_shell_only_and_blocked_responses_are_honest(c,monkeypatch):
 monkeypatch.setattr(f,'request_page',lambda *_:(200,{},b'<html><script src="app.js"></script></html>'))
 r=c.post('/api/products/fetch-information',json={'url':URL})
 assert r.status_code==422 and 'JavaScript' in r.json()['detail']
 monkeypatch.setattr(f,'request_page',lambda *_:(403,{},b'private provider error'))
 r=c.post('/api/products/fetch-information',json={'url':URL})
 assert r.status_code==422 and 'private provider error' not in r.text

def test_oversized_html_is_rejected(monkeypatch):
 monkeypatch.setattr(f,'MAX_BYTES',10)
 monkeypatch.setattr(f,'public_addresses',lambda _:['8.8.8.8'])
 response=NS(status=200,getheaders=lambda:[('Content-Type','text/html')],read1=lambda size:b'x'*size)
 monkeypatch.setattr(f,'PinnedHTTPS',lambda *_:NS(request=lambda *_a,**_k:None,getresponse=lambda:response,close=lambda:None))
 with pytest.raises(f.FetchFailure,match='size limit'):f.request_page(FINAL,time.monotonic()+10)

def test_fetch_rate_limit(c,monkeypatch):
 monkeypatch.setattr(f,'request_page',lambda *_:(200,{},html().encode()))
 with Session.begin() as s:s.query(Record).filter(Record.id.like('product-fetch-limit:%')).delete(synchronize_session=False)
 for _ in range(10):assert c.post('/api/products/fetch-information',json={'url':URL}).status_code==200
 assert c.post('/api/products/fetch-information',json={'url':URL}).status_code==429
