"""Real-model four-turn integration test; isolated database and synthetic evidence."""
import asyncio, json, sys, time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from debate_lab.storage import Store
from debate_lab.controller import Controller
from debate_lab.provider import Ollama
from debate_lab.domain import NewSession, Settings, Command

async def main():
    root=Path(__file__).resolve().parents[1]; store=Store(root/'.data'/'live-verification')
    c=Controller(store,Ollama()); s=store.create(NewSession(proposition='A small library should trial one extra hour on Saturday for four weeks.',settings=Settings(turn_limit=4,context_tokens=16384,output_tokens=3072)))
    source=c.evidence.stage('synthetic-library-survey.txt',b'Synthetic test evidence, not real research. A fictional library surveyed 40 visitors. 24 requested a later Saturday closing. Staffing the extra hour costs 60 dollars per week. No attendance trial has been conducted.','text')
    await c.add_source(s['id'],source)
    s=c.get(s['id']); await c.command(s['id'],Command(command='start',expected_revision=s['revision'],idempotency_key='live-smoke-start-'+s['id']))
    prev=None; start=time.monotonic()
    while c.task and not c.task.done():
        await asyncio.sleep(2)
        cur=c.get(s['id']); marker=(cur['state'],len(cur['turns']),cur['activity'])
        if marker!=prev: print(json.dumps({'state':cur['state'],'turns':len(cur['turns']),'activity':cur['activity'],'elapsed':round(time.monotonic()-start)}),flush=True); prev=marker
        if time.monotonic()-start>600:
            await c.command(cur['id'],Command(command='cancel',expected_revision=cur['revision'],idempotency_key='smoke-timeout-'+s['id'])); break
    end=c.get(s['id']); report={'run_id':end['id'],'state':end['state'],'completed_turns':len(end['turns']),'source_status':[x['status'] for x in end['sources']],'error':end['error'],'verdict':end['verdict'],'usage':end['usage'],'attempts':end['attempts'],'elapsed_seconds':round(time.monotonic()-start,2)}
    (root/'docs'/'live-smoke.json').write_text(json.dumps(report,indent=2)); print(json.dumps(report),flush=True)
asyncio.run(main())
