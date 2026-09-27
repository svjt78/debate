"""Explicit isolated Charlie preparation probe. Never starts a debate or changes models."""
import asyncio, io, json, sqlite3, sys, time
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from debate_lab.controller import Controller
from debate_lab.storage import Store
from debate_lab.domain import NewSession,Settings
from debate_lab.provider import Ollama
from debate_lab.app import PreparationBody
ROOT=Path(__file__).resolve().parents[1]
async def main():
    store=Store(ROOT/'.data/preparation-verification')
    main_db=ROOT/'.data/debate.sqlite3'
    if main_db.exists():
        with sqlite3.connect(f'file:{main_db}?mode=ro',uri=True) as db:
            row=db.execute("SELECT body FROM preferences WHERE key='context_profiles'").fetchone()
        if row:store.set_preference('context_profiles',json.loads(row[0]))
    c=Controller(store,Ollama());s=store.create(NewSession(proposition='A fictional library is considering a four-week weekend-hours trial. Help me frame the decision.' if '--text' in sys.argv else '',preparation_mode='guided',settings=Settings(turn_limit=4)))
    im=Image.new('RGB',(640,320),'white');draw=ImageDraw.Draw(im)
    draw.rectangle((30,50,220,240),fill='red')
    font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',32)
    draw.text((270,80),'42 requests',fill='black',font=font);draw.text((270,140),'Weekend hours?',fill='black',font=font)
    data=io.BytesIO();im.save(data,format='PNG')
    if '--text' not in sys.argv: await c.add_source(s['id'],c.evidence.stage('synthetic-library.png',data.getvalue()))
    await c.prepare_action(s['id'],PreparationBody(action='analyze',expected_revision=c.get(s['id'])['revision']))
    start=time.monotonic();last=None
    while c.task and not c.task.done():
        await asyncio.sleep(2);cur=c.get(s['id']);mark=(cur['state'],len(cur['attempts']),cur['activity'])
        if mark!=last:print(json.dumps({'progress':mark,'seconds':round(time.monotonic()-start)}),flush=True);last=mark
        if time.monotonic()-start>1000:await c.shutdown();break
    cur=c.get(s['id']);src=cur['sources'][0] if cur['sources'] else {'status':'not supplied','passages':[]};report={'session_id':s['id'],'state':cur['state'],'error':cur['error'],'seconds':round(time.monotonic()-start),'source_status':src['status'],'source_summary':src.get('summary'),'visual_observations':[p for p in src['passages'] if p.get('derived')],'preparation_output':cur['preparation'].get('output'),'turns':len(cur['turns']),'approval':cur['preparation'].get('approval'),'active_seconds':cur['active_seconds'],'attempts':[{k:a.get(k) for k in ('status','role','bucket','context')} for a in cur['attempts']]}
    report['passed']=cur['state']=='DRAFT' and src['status'] in {'admitted','not supplied'} and bool(report['preparation_output']) and not cur['turns'] and not report['approval']
    (ROOT/('docs/live-preparation-text.json' if '--text' in sys.argv else 'docs/live-preparation.json')).write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
asyncio.run(main())
