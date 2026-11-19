"""Public Shopee HTML metadata only: no private endpoints, cookies or browser bypass."""
import http.client,ipaddress,json,math,re,socket,ssl,time
from html.parser import HTMLParser
from urllib.parse import urlsplit,urljoin,quote,urlunsplit

HOSTS=('shopee.co.th','shopee.com','shope.ee')
MAX_BYTES=2*1024*1024

class FetchFailure(Exception):pass
class MetadataUnavailable(FetchFailure):pass

def validate_url(url):
 if not isinstance(url,str) or not 1<=len(url)<=2000 or re.search(r'[\x00-\x20\\]',url):
  raise FetchFailure('Enter a valid HTTPS Shopee product URL.')
 try:u=urlsplit(url);port=u.port
 except ValueError:raise FetchFailure('Enter a valid HTTPS Shopee product URL.') from None
 if u.scheme!='https' or not u.hostname or u.username is not None or u.password is not None or port not in (None,443) or not any(u.hostname==h or u.hostname.endswith('.'+h) for h in HOSTS):
  raise FetchFailure('Only HTTPS Shopee links on port 443 are supported.')
 return u

def public_addresses(host):
 try:addresses=list(dict.fromkeys(x[4][0] for x in socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)))
 except OSError:raise FetchFailure('Could not resolve the Shopee host. Try again later.') from None
 if not addresses or any(not ipaddress.ip_address(x).is_global or ipaddress.ip_address(x).is_multicast for x in addresses):
  raise FetchFailure('The link resolved to a non-public network address and was blocked.')
 return addresses

class PinnedHTTPS(http.client.HTTPSConnection):
 def __init__(self,host,address,timeout):
  super().__init__(host,timeout=timeout,context=ssl.create_default_context());self.address=address
 def connect(self):
  # Connect only to the validated IP; verify TLS using the original Shopee hostname.
  raw=socket.create_connection((self.address,443),self.timeout)
  try:self.sock=self._context.wrap_socket(raw,server_hostname=self.host)
  except Exception:raw.close();raise

def request_page(url,deadline):
 u=validate_url(url);address=public_addresses(u.hostname)[0]
 timeout=min(8,deadline-time.monotonic())
 if timeout<=0:raise FetchFailure('Shopee took too long to respond. Try again later.')
 connection=PinnedHTTPS(u.hostname,address,timeout)
 try:
  path=quote(u.path or '/',safe='/%:@!$&\'()*+,;=-._~')
  if u.query:path+='?'+quote(u.query,safe='/%?:@!$&\'()*+,;=-._~')
  connection.request('GET',path,headers={'User-Agent':'ShopeeAffAIStudio/1.2 (+https://aff.pramool.bid)','Accept':'text/html,application/xhtml+xml','Accept-Encoding':'identity','Accept-Language':'th-TH,th;q=0.9,en;q=0.5'})
  response=connection.getresponse();headers=dict((k.lower(),v) for k,v in response.getheaders())
  if response.status in (301,302,303,307,308):return response.status,headers,b''
  if response.status!=200:return response.status,headers,b''
  if headers.get('content-type','').split(';')[0].strip().lower() not in ('text/html','application/xhtml+xml'):
   raise FetchFailure('Shopee did not return a public product web page.')
  if headers.get('content-encoding','identity').lower() not in ('identity',''):
   raise FetchFailure('Shopee returned an unsupported response format.')
  chunks=[];size=0
  while True:
   if time.monotonic()>=deadline:raise FetchFailure('Shopee took too long to respond. Try again later.')
   part=response.read1(min(65536,MAX_BYTES+1-size))
   if not part:break
   size+=len(part)
   if size>MAX_BYTES:raise FetchFailure('The Shopee page exceeds the import size limit.')
   chunks.append(part)
  return response.status,headers,b''.join(chunks)
 finally:connection.close()

class MetadataParser(HTMLParser):
 def __init__(self):super().__init__(convert_charrefs=True);self.meta={};self.documents=[];self.script=None
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=='meta':
   key=(a.get('property') or a.get('name') or '').lower()
   if a.get('content'):self.meta.setdefault(key,a['content'])
  if tag=='script' and a.get('type','').lower()=='application/ld+json':self.script=[]
 def handle_data(self,data):
  if self.script is not None:self.script.append(data)
 def handle_endtag(self,tag):
  if tag=='script' and self.script is not None:
   try:self.documents.append(json.loads(''.join(self.script)))
   except (ValueError,RecursionError):pass
   self.script=None

class PlainText(HTMLParser):
 def __init__(self):super().__init__(convert_charrefs=True);self.parts=[];self.hidden=0
 def handle_starttag(self,tag,attrs):
  if tag in ('script','style'):self.hidden+=1
  elif tag in ('br','p','div','li'):self.parts.append('\n')
 def handle_endtag(self,tag):
  if tag in ('script','style'):self.hidden=max(0,self.hidden-1)
 def handle_data(self,data):
  if not self.hidden:self.parts.append(data)

def clean(value,limit):
 if not isinstance(value,(str,int,float)) or isinstance(value,bool):return ''
 parser=PlainText();parser.feed(str(value))
 return re.sub(r'[ \t]+',' ',''.join(parser.parts)).strip()[:limit]

def product_nodes(documents):
 found=[];visited=0
 def visit(value,depth=0):
  nonlocal visited
  visited+=1
  if visited>500 or depth>8:return
  if isinstance(value,dict):
   kind=value.get('@type',[]);kind=[kind] if isinstance(kind,str) else kind
   if isinstance(kind,list) and any(x in ('Product','https://schema.org/Product','http://schema.org/Product') for x in kind):found.append(value);return
   for key in ('@graph','mainEntity','itemListElement','item'):visit(value.get(key),depth+1)
  elif isinstance(value,list):
   for item in value:visit(item,depth+1)
 for document in documents:visit(document)
 return found

def extract(html,final_url):
 parser=MetadataParser();parser.feed(html);nodes=product_nodes(parser.documents);m=parser.meta
 if len(nodes)>1:
  current=urlsplit(final_url)
  nodes=[n for n in nodes if any(isinstance(n.get(k),str) and urlsplit(urljoin(final_url,n[k])).path==current.path for k in ('url','@id'))]
  if len(nodes)!=1:raise FetchFailure('This page contains multiple products. Import was stopped to avoid using the wrong product.')
 node=nodes[0] if nodes else {}
 is_product=m.get('og:type','').lower() in ('product','product.item') or 'product:price:amount' in m
 name=clean(node.get('name') or (m.get('og:title') if is_product else ''),200)
 if not name or name.lower() in ('shopee','shopee thailand','shopee thailand | buy and sell on mobile or online'):
  raise MetadataUnavailable('Shopee did not expose public product information in this page. It may require JavaScript, sign-in or authorized Shopee API access. No fields were changed.')
 data={'name':name};warnings=[]
 for field,limit in [('description',10000),('category',200)]:
  value=clean(node.get(field) or (m.get('og:description') if field=='description' else ''),limit)
  if value:data[field]=value
 brand=node.get('brand');brand=brand.get('name') if isinstance(brand,dict) else brand
 if clean(brand,200):data['brand']=clean(brand,200)
 offers=node.get('offers',{});offers=offers[0] if isinstance(offers,list) and offers else offers
 offers=offers if isinstance(offers,dict) else {}
 seller=offers.get('seller',{});seller=seller.get('name') if isinstance(seller,dict) else seller
 if clean(seller,200):data['shop']=clean(seller,200)
 raw=offers.get('price',offers.get('lowPrice',m.get('product:price:amount')))
 currency=str(offers.get('priceCurrency',m.get('product:price:currency',''))).upper()
 try:
  price=float(str(raw).replace(',',''))
  if currency=='THB' and math.isfinite(price) and 0<=price<=10000000:
   data['price']=price
   if 'lowPrice' in offers and 'price' not in offers:warnings.append('Price is the lowest listed variant price. Check the selected variant before saving.')
 except (ValueError,TypeError):pass
 properties=node.get('additionalProperty',[])
 if isinstance(properties,list):
  specs=[clean(p.get('name'),100)+': '+clean(p.get('value'),300) for p in properties[:30] if isinstance(p,dict) and clean(p.get('name'),100) and clean(p.get('value'),300)]
  if specs:data['specifications']='\n'.join(specs)[:4000]
 warnings.append('Review product details, price and variant before saving. Missing fields were left unchanged; images must be uploaded separately.')
 return data,warnings

def read_page(url,deadline):
 for _ in range(5):
  status,headers,content=request_page(url,deadline)
  if status in (301,302,303,307,308):
   if not headers.get('location'):raise FetchFailure('Shopee returned an invalid redirect.')
   url=urljoin(url,headers['location']);validate_url(url);continue
  if status in (401,403,429):raise FetchFailure('Shopee blocked this public request or requires sign-in. No fields were changed. Try manual entry or authorized Shopee API access.')
  if status!=200:raise FetchFailure('The Shopee product page is unavailable. Check the link and try again.')
  return url,content
 raise FetchFailure('The Shopee link redirected too many times.')

def product_page(url):
 """Normalize only recognized product paths for reading, never the saved affiliate URL."""
 u=validate_url(url)
 if u.hostname not in ('shopee.co.th','www.shopee.co.th'):return None,None
 match=re.fullmatch(r'/(?:opaanlp|product)/(\d+)/(\d+)/?',u.path) or re.search(r'-i\.(\d+)\.(\d+)/?$',u.path)
 if not match:return None,None
 shop,item=match.groups()
 return f'https://shopee.co.th/product/{shop}/{item}',{'shop_id':shop,'item_id':item}

def fetch_information(original):
 validate_url(original);deadline=time.monotonic()+20
 try:
  url,content=read_page(original,deadline)
  source=urlsplit(url);source_url=urlunsplit((source.scheme,source.netloc,source.path,'',''))
  canonical,ids=product_page(url)
  base={'original_url':original,'source_url':source_url,'product_page_url':canonical or source_url,'product_reference':ids,'redirect_resolved':url!=original,'source':'public_html_metadata'}
  try:data,warnings=extract(content.decode('utf-8',errors='replace'),url)
  except MetadataUnavailable:
   data=None;warnings=[]
   if canonical and canonical!=source_url:
    # One normal public product-page lookup; never retry blocked requests or use private APIs.
    try:
     resolved,content=read_page(canonical,deadline)
     data,warnings=extract(content.decode('utf-8',errors='replace'),resolved)
    except Exception:pass
   if data is None:
    return {**base,'status':'metadata_unavailable','data':{},'fields':[],'warnings':['The link opened successfully, but Shopee did not expose public product name or price metadata. The page may require JavaScript or authorized API access. No product fields were changed. Your original affiliate link is preserved.']}
  return {**base,'status':'fetched','data':data,'fields':list(data),'warnings':warnings}
 except FetchFailure:raise
 except Exception:raise FetchFailure('Could not fetch Shopee information. The request failed or timed out; no fields were changed.') from None
