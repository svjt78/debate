"""Sequential local capacity probes. Never alters Ollama service configuration."""
import asyncio,json,sys,time,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import psutil
from debate_lab.provider import Ollama,compact_schema
from debate_lab.domain import DEFAULT_MODELS
from debate_lab.context import profile_key,encoded
from debate_lab.storage import Store
from pydantic import BaseModel
class Answer(BaseModel):
    first: str
    last: str
async def main():
    root=Path(__file__).resolve().parents[1];store=Store(root/'.data');provider=Ollama()
    runtime=await provider.runtime_identity();models={x['name']:x for x in await provider.models()}
    profiles=store.preference('context_profiles',{});reports=list(profiles.values())
    for name in (sys.argv[1:] or list(dict.fromkeys(DEFAULT_MODELS.values()))):
        pin={'model':name,'digest':models[name]['digest'],'endpoint':provider.endpoint}
        samples=[];passed=[];ratios=[];maximum=0
        for tier in (16384,24576,32768):
            # Dense mixed JSON, prose and punctuation; long enough to exercise capacity.
            unit='{"claim":"Test evidence remains unverified; preserve objections and concessions.","values":[17,29,43]}\n'
            body='FIRST_MARKER=cedar872\n'+unit*int(tier*2.3/len(unit))+'\nLAST_MARKER=amber619'
            messages=[{'role':'system','content':'Return JSON with first and last containing the exact FIRST_MARKER and LAST_MARKER values. Ignore repetitive records.'},{'role':'user','content':body}]
            usage={};minimum=psutil.virtual_memory().available;began=time.monotonic()
            async def public(_):pass
            async def used(i,o):usage.update(input=i,output=o)
            async def monitor():
                nonlocal minimum
                while True:
                    minimum=min(minimum,psutil.virtual_memory().available)
                    if minimum<4*1024**3:raise RuntimeError('Memory headroom below 4 GiB')
                    await asyncio.sleep(.5)
            task=asyncio.create_task(provider.generate(name,messages,compact_schema(Answer.model_json_schema()),{'num_ctx':tier,'num_predict':3072,'temperature':0},public,used))
            watch=asyncio.create_task(monitor());error=None
            try:
                done,_=await asyncio.wait([task,watch],timeout=240,return_when=asyncio.FIRST_COMPLETED)
                if watch in done:await watch
                if task not in done:raise TimeoutError('Probe timeout')
                answer=await task
                if answer!={'first':'cedar872','last':'amber619'}:raise ValueError('Boundary markers missing')
                if not usage.get('input'):raise ValueError('Missing prompt count')
                if usage['input']+3072>tier:raise ValueError('Reported usage exceeds requested capacity')
                size=len(('\n'.join(m['content'] for m in messages)+'\n'+encoded(compact_schema(Answer.model_json_schema()))).encode())
                ratios.append(usage['input']/size);maximum=max(maximum,size);passed.append(tier)
            except Exception as e:error=f'{type(e).__name__}: {e}'
            finally:
                watch.cancel();task.cancel()
                await asyncio.gather(watch,task,return_exceptions=True)
                await provider.cancel()
            sample={'model':name,'context':tier,'usage':usage,'minimum_available_gib':round(minimum/1024**3,2),'seconds':round(time.monotonic()-began,2),'error':error};samples.append(sample);print(json.dumps(sample),flush=True)
        # Cancellation/residency was exercised by every request cleanup. Explicit midstream cancel probe follows.
        cancel_ok=False
        try:
            task=asyncio.create_task(provider.generate(name,[{'role':'user','content':'Write a very long detailed story as JSON.'}],{'type':'object'}, {'num_ctx':16384,'num_predict':3072},public,used))
            await asyncio.sleep(2);task.cancel();await asyncio.gather(task,return_exceptions=True);await provider.cancel();cancel_ok=True
        except Exception as e:print('Cancellation verification failed: '+str(e),flush=True)
        profile={'tested_contexts':passed if cancel_ok else [],'bytes_to_tokens':min(1,max(ratios)*1.5) if ratios else 1,'max_bytes':maximum,'runtime':runtime,'model':pin,'samples':samples,'cancellation_verified':cancel_ok,'created':time.time(),'limitation':'Sample-based text calibration, not a proof against every truncation or memory workload.'}
        profiles[profile_key(pin,runtime)]=profile;store.set_preference('context_profiles',profiles);reports.append(profile)
        (root/'docs/context-calibration.json').write_text(json.dumps(reports,indent=2))
asyncio.run(main())
