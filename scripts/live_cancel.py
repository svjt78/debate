"""Run separately after smoke test; bounded request cancellation for each model."""
import asyncio,json,time
from pathlib import Path
import httpx

async def main():
    records=[]; root=Path(__file__).resolve().parents[1]
    async with httpx.AsyncClient(timeout=120,trust_env=False) as c:
        if (await c.get('http://127.0.0.1:11434/api/ps')).json()['models']: raise RuntimeError('Runtime occupied; probe deferred.')
        for model in ['gpt-oss:20b','qwen3:30b-a3b-thinking-2507-q4_K_M','gemma4:31b-mlx']:
            started=time.monotonic(); received=False
            async with c.stream('POST','http://127.0.0.1:11434/api/chat',json={'model':model,'messages':[{'role':'user','content':'Explain the tradeoffs of a four-day workweek in substantial detail, at least 1500 words.'}],'stream':True,'keep_alive':0,'options':{'num_ctx':4096,'num_predict':4096}}) as r:
                r.raise_for_status()
                async for line in r.aiter_lines():
                    if not line: continue
                    item=json.loads(line)
                    if item.get('error'): raise RuntimeError(item['error'])
                    # Observe existence only. Never print or save private thinking.
                    if item.get('message',{}).get('content') or item.get('message',{}).get('thinking'):
                        received=True; break
            closed=time.monotonic(); cleared=False
            while time.monotonic()-closed<30:
                residents=(await c.get('http://127.0.0.1:11434/api/ps')).json()['models']
                if not residents: cleared=True; break
                await asyncio.sleep(.25)
            record={'model':model,'received_inference_before_close':received,'residency_cleared':cleared,'seconds_to_first_token':round(closed-started,3),'seconds_from_close_to_empty_ps':round(time.monotonic()-closed,3),'evidence_limit':'API-level cessation/residency evidence; no independent GPU instrumentation'}
            records.append(record); (root/'docs/live-cancellation.json').write_text(json.dumps(records,indent=2)); print(json.dumps(record),flush=True)
            if not cleared: break
asyncio.run(main())
