"""Offline speech and video extraction verification using synthetic local fixtures."""
import asyncio, hashlib, json, os, subprocess, sys, time
from pathlib import Path
import imageio_ffmpeg
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from debate_lab.storage import Store
from debate_lab.evidence import Evidence

async def main():
    model=ROOT/'.data/auxiliary-models/whisper-small-mlx'
    os.environ.update(DEBATE_WHISPER_MODEL=str(model),HF_HUB_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',HF_HOME=str(ROOT/'.data/auxiliary-cache'),XDG_CACHE_HOME=str(ROOT/'.data/cache'))
    ffmpeg=imageio_ffmpeg.get_ffmpeg_exe();fixtures=ROOT/'.data/media-fixtures'
    wav=fixtures/'synthetic-speech.wav';video=fixtures/'synthetic-video.mp4'
    subprocess.run([ffmpeg,'-nostdin','-v','error','-i',str(fixtures/'synthetic-speech.aiff'),'-ar','16000','-ac','1','-y',str(wav)],check=True)
    im=Image.new('RGB',(640,360),'white');draw=ImageDraw.Draw(im);font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',28)
    draw.text((30,70),'SYNTHETIC MEDIA TEST',fill='black',font=font);draw.text((30,145),'40 visitors / 24 requests',fill='black',font=font);draw.rectangle((30,220,110,300),fill='red');im.save(fixtures/'card.png')
    subprocess.run([ffmpeg,'-nostdin','-v','error','-loop','1','-i',str(fixtures/'card.png'),'-i',str(wav),'-c:v','libx264','-tune','stillimage','-c:a','aac','-pix_fmt','yuv420p','-shortest','-y',str(video)],check=True,timeout=30)
    store=Store(ROOT/'.data/media-verification');e=Evidence(store);reports=[]
    for path in [wav,video]:
        start=time.monotonic();src=e.stage(path.name,path.read_bytes())
        try:
            result=await e.process_source(src)
            text=' '.join(p['text'] for p in result['passages']);normalized=text.lower()
            facts={label:any(w in normalized for w in spellings) for label,spellings in {'40':['forty','40'],'24':['twenty four','twenty-four','24'],'60':['sixty','60']}.items()}
            times=all(p['locator'].get('start',-1)>=0 and p['locator'].get('end',-1)>p['locator'].get('start',-1) for p in result['passages'])
            report={'file':path.name,'transcript':text,'fact_checks':facts,'timestamps_valid':times,'passages':result['passages'],'frames':result.get('images',[]),'uncertainty':result['uncertainty'],'passed':all(facts.values()) and times and bool(result['passages']) and (path.suffix!='.mp4' or bool(result.get('images')))}
        except Exception as ex: report={'file':path.name,'passed':False,'error':str(ex)}
        report['elapsed_seconds']=round(time.monotonic()-start,2);reports.append(report);print(json.dumps(report),flush=True)
    model_info={'repository':'mlx-community/whisper-small-mlx','revision':'45f3915','local_path':str(model),'weights_bytes':(model/'weights.npz').stat().st_size,'weights_sha256':hashlib.sha256((model/'weights.npz').read_bytes()).hexdigest(),'network_mode':'HF_HUB_OFFLINE=1'}
    (ROOT/'docs/live-media.json').write_text(json.dumps({'model':model_info,'tests':reports},indent=2))
asyncio.run(main())
