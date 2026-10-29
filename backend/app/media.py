import subprocess,json,zipfile,math,os
from pathlib import Path

def run(args):
 r=subprocess.run(args,capture_output=True,timeout=900)
 if r.returncode: raise RuntimeError(r.stderr.decode(errors='replace')[-2500:])
def probe(path):
 r=subprocess.run(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(path)],capture_output=True,timeout=30,check=True)
 return json.loads(r.stdout)
def validate(path):
 p=probe(path)
 if not any(s['codec_type']=='video' for s in p['streams']) or float(p['format']['duration'])<=0: raise ValueError('Invalid video')
 return p
def demo_scene(path,image=None,index=0):
 args=['ffmpeg','-y','-threads','2']
 if image: args+=['-loop','1','-i',str(image)]
 else: args+=['-f','lavfi','-i',f'color=c={ ["0x17243d","0x3c2441","0x243f42"][index%3]}:s=720x1280:r=25']
 vf='scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2:color=0x111c31,setsar=1'
 if image: vf+=",zoompan=z='min(zoom+0.0003,1.06)':d=200:s=720x1280:fps=25"
 args+=['-t','8','-vf',vf,'-an','-c:v','libx264','-preset','ultrafast','-pix_fmt','yuv420p','-threads','2',str(path)]
 run(args);validate(path)
def ass_text(text): return text.replace('\\','').replace('{','').replace('}','').replace('\n','\\N')
def timecode(v): return f'{int(v)//3600}:{int(v)//60%60:02}:{int(v)%60:02}.{int(v*100)%100:02}'
def compose(folder,scenes,settings,product):
 w=1080 if settings['resolution']=='1080' else 720; h=w*16//9
 ass='[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nWrapStyle: 0\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Default,Noto Sans Thai,52,&H00FFFFFF,&H000000FF,&H00131C30,&H80000000,1,0,0,0,100,100,0,0,1,3,1,2,90,90,290,1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n'
 cursor=0
 for scene in scenes:
  end=min(cursor+8,settings['duration'])
  text=scene['narration'] if settings['subtitles'] else scene['overlay']
  # Phrase-level timestamps are derived from scene audio; never represented as word alignment.
  chunks=[text[i:i+36] for i in range(0,len(text),36)]
  ass+=f'Dialogue: 0,{timecode(cursor)},{timecode(end)},Default,,0,0,0,,'+ass_text('\\N'.join(chunks))+'\n'
  cursor=end
 if settings['provider']=='mock': ass+=f'Dialogue: 0,0:00:00.00,{timecode(settings["duration"])},Default,,0,0,1450,,MOCK • ตัวอย่างจำลอง\n'
 (folder/'subtitles.ass').write_text(ass,encoding='utf-8')
 (folder/'concat.txt').write_text(''.join(f"file 'scene-{i}.mp4'\n" for i in range(len(scenes))))
 vf=f'scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,ass=subtitles.ass'
 # Use controlled relative names and cwd to avoid filter/path injection.
 args=['ffmpeg','-y','-threads','2','-f','concat','-safe','1','-i','concat.txt','-i','narration.wav','-t',str(settings['duration']),'-vf',vf,'-c:v','libx264','-preset','veryfast','-crf','23','-pix_fmt','yuv420p','-threads','2','-c:a','aac','-b:a','160k','-af','loudnorm=I=-16:TP=-1.5:LRA=11','-movflags','+faststart','final_video.mp4']
 r=subprocess.run(args,cwd=folder,capture_output=True,timeout=1500)
 if r.returncode: raise RuntimeError(r.stderr.decode(errors='replace')[-2500:])
 info=validate(folder/'final_video.mp4')
 run(['ffmpeg','-y','-i',str(folder/'final_video.mp4'),'-frames:v','1',str(folder/'thumbnail.jpg')])
 return info
def narration(folder,scenes,settings,speech):
 # Pad each scene narration to its exact scene boundary before concatenation.
 for i,scene in enumerate(scenes):
  src=folder/f'voice-{i}.mp3'
  uploaded=folder/'uploaded-narration'
  if settings['provider']=='google' and settings['narration'] and not uploaded.exists():
   if len(scene['narration'])>1500: raise ValueError('Narration too long')
   if not src.exists():
    from .db import Session,Operation
    key=folder.name+':tts:'+str(i)
    with Session.begin() as s:
     if s.get(Operation,key):raise ValueError('Uncertain paid TTS submission; reconcile before resuming')
     s.add(Operation(id=key,job_id=folder.name,state='intent'))
    speech(scene['narration'],src,settings['voice'],settings['speed'])
    with Session.begin() as s:s.get(Operation,key).state='done'
   length=float(probe(src)['format']['duration'])
   if length>8: raise ValueError(f'Scene {i+1} narration exceeds 8 seconds; shorten script or increase speaking speed')
   inputs=['-i',str(src)]
  else: inputs=['-f','lavfi','-i','anullsrc=r=44100:cl=stereo']
  run(['ffmpeg','-y',*inputs,'-af','apad','-t','8','-ar','44100','-ac','2',str(folder/f'voice-{i}.wav')])
 (folder/'audio.txt').write_text(''.join(f"file 'voice-{i}.wav'\n" for i in range(len(scenes))))
 if (folder/'uploaded-narration').exists():
  run(['ffmpeg','-y','-i',str(folder/'uploaded-narration'),'-af','apad','-t',str(settings['duration']),'-ar','44100','-ac','2',str(folder/'narration.wav')])
 else:
  run(['ffmpeg','-y','-f','concat','-safe','1','-i',str(folder/'audio.txt'),'-c:a','pcm_s16le',str(folder/'narration.wav')])
 if settings.get('music'):
  # Original locally synthesized ambient tone; no third-party music licensing dependency.
  run(['ffmpeg','-y','-i',str(folder/'narration.wav'),'-f','lavfi','-i','sine=frequency=220:sample_rate=44100','-filter_complex','[1:a]volume=0.015[m];[0:a][m]amix=inputs=2:duration=first','-t',str(settings['duration']),str(folder/'mixed.wav')])
  os.replace(folder/'mixed.wav',folder/'narration.wav')
def export(folder,product,job):
 brief=job['brief']
 (folder/'caption.txt').write_text(brief['caption'],encoding='utf-8')
 (folder/'hashtags.txt').write_text(' '.join(brief['hashtags']),encoding='utf-8')
 (folder/'product_link.txt').write_text(product.get('url',''),encoding='utf-8')
 (folder/'project_metadata.json').write_text(json.dumps(job,ensure_ascii=False,indent=2),encoding='utf-8')
 with zipfile.ZipFile(folder/'export.zip','w',zipfile.ZIP_DEFLATED) as z:
  for name in ['final_video.mp4','thumbnail.jpg','caption.txt','hashtags.txt','product_link.txt','project_metadata.json','subtitles.ass','narration.wav']: z.write(folder/name,name)
