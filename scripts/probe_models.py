"""Bounded live probes; no model installation or service configuration."""
import asyncio, json, os, platform, time
from pathlib import Path
import httpx, psutil

async def main():
    root=Path(__file__).resolve().parents[1]; out=root/'docs'/'live-probes.json'
    results=json.loads(out.read_text()) if out.exists() else []; base='http://127.0.0.1:11434'
    async with httpx.AsyncClient(timeout=httpx.Timeout(180,connect=5),trust_env=False) as c:
        resident=(await c.get(base+'/api/ps')).json()['models']
        if resident: raise RuntimeError('Existing residency detected; no inference started.')
        models=(await c.get(base+'/api/tags')).json()['models']
        for name in ['gemma4:31b-mlx']:
            start=time.monotonic(); public=''; thinking=0; done=None
            result={'model':name,'started_at':time.time(),'available_memory_before':psutil.virtual_memory().available,'context_tokens':4096,'output_limit':512}
            body={'model':name,'messages':[{'role':'system','content':'Return only the requested JSON. No explanation.'},{'role':'user','content':'Set public_text to Ready.'}],'stream':True,'keep_alive':0,'format':{'type':'object','properties':{'public_text':{'type':'string'}},'required':['public_text']},'options':{'num_ctx':4096,'num_predict':512,'temperature':0}}
            body.pop('format')
            body['messages'][0]['content']='Return only JSON matching {"public_text": string}. No explanation or markdown.'
            result['framing']='prompt JSON; strict application validation'
            try:
                async with c.stream('POST',base+'/api/chat',json=body) as r:
                    r.raise_for_status()
                    async for line in r.aiter_lines():
                        if not line: continue
                        item=json.loads(line)
                        if item.get('error'): raise RuntimeError(item['error'])
                        public+=item.get('message',{}).get('content','')
                        thinking+=len(item.get('message',{}).get('thinking',''))
                        if item.get('done'): done={k:item.get(k) for k in ['done_reason','prompt_eval_count','eval_count','total_duration','load_duration']}
                result.update(public_result=public,private_thinking_char_count=thinking,completion=done,elapsed_seconds=round(time.monotonic()-start,3),available_memory_after=psutil.virtual_memory().available)
                try: result['json_valid']=isinstance(json.loads(public).get('public_text'),str)
                except Exception: result['json_valid']=False
                deadline=time.monotonic()+20
                while time.monotonic()<deadline:
                    resident=(await c.get(base+'/api/ps')).json()['models']
                    if not resident: break
                    await asyncio.sleep(.5)
                result['residency_cleared']=not resident
            except Exception as e: result['error']=str(e)
            results.append(result); out.write_text(json.dumps(results,indent=2)); print(json.dumps(result),flush=True)
            if not result.get('residency_cleared'): break
asyncio.run(main())
