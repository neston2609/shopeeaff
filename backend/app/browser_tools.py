"""Download the auditable, credential-free browser helper source package."""
from pathlib import Path
import io,zipfile
from fastapi import HTTPException

FILES=('manifest.json','extractor.mjs','popup.html','popup.mjs','popup.css','README.md')

def extension_package():
 root=Path(__file__).resolve().parents[2]/'browser-extension'
 output=io.BytesIO()
 with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
  for name in FILES:
   path=root/name
   if not path.is_file():raise HTTPException(503,'Browser helper package is unavailable. Contact the administrator.')
   archive.writestr(name,path.read_bytes())
 return output.getvalue()
