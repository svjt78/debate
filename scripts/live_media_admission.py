"""Verify real local transcription plus Charlie's shared video admission. No debate started."""
import asyncio,json,os,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'backend'))
os.environ.update(DEBATE_WHISPER_MODEL=str(ROOT/'.data/auxiliary-models/whisper-small-mlx'),HF_HUB_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1')
from debate_lab.controller import Controller
from debate_lab.storage import Store
from debate_lab.provider import Ollama
from debate_lab.domain import NewSession,Settings
async def main():
    store=Store(ROOT/'.data/live-verification');c=Controller(store,Ollama());await c.provider.ensure_idle()
    s=store.create(NewSession(proposition='Synthetic audio/video ingestion verification',settings=Settings(turn_limit=4)))
    path=ROOT/'.data/media-fixtures/synthetic-video.mp4';s['sources']=[c.evidence.stage(path.name,path.read_bytes())]
    s=await c.pin(s);s.update(state='INGESTING',phase='ingestion');store.save(s)
    started=time.monotonic()
    try:
        await asyncio.wait_for(c.ingest(s['id']),180)
        s=store.get(s['id']);s.update(state='PAUSED',activity='Synthetic media verification; no debate started');store.save(s)
        src=s['sources'][0]
        report={'run_id':s['id'],'passed':src['status']=='admitted' and bool(src['passages']) and bool(src.get('images')),'source_status':src['status'],'passages':src['passages'],'summary':src['summary'],'uncertainty':src['uncertainty'],'metadata':src['metadata'],'usage':s['usage']}
    except Exception as ex:
        await c.provider.cancel();s=store.get(s['id']);s.update(state='FAILED_RECOVERABLE',error=str(ex));store.save(s);report={'passed':False,'error':str(ex),'run_id':s['id']}
    report['elapsed_seconds']=round(time.monotonic()-started,2);(ROOT/'docs/live-media-admission.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
asyncio.run(main())
