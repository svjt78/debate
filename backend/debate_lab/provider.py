import asyncio, codecs, json, time
import httpx

def compact_schema(value):
    """Remove display titles without changing JSON validation constraints."""
    if isinstance(value, list): return [compact_schema(item) for item in value]
    if isinstance(value, dict):
        return {key: ({name: compact_schema(child) for name, child in item.items()}
                      if key in {'properties', '$defs'} else compact_schema(item))
                for key, item in value.items() if key != 'title'}
    return value


class ProviderError(Exception): pass
class GenerationLength(ProviderError): pass
class CancellationUnconfirmed(ProviderError): pass
class PublicString:
    """Decode only the JSON public_text field during streaming, including split escapes."""
    def __init__(self,field='public_text'): self.raw=''; self.emitted=''; self.field=field
    def feed(self,chunk):
        self.raw+=chunk
        import re
        m=re.search(r'"'+self.field+r'"\s*:\s*"',self.raw)
        if not m: return ''
        raw=self.raw[m.end():]; out=''; i=0
        while i<len(raw):
            ch=raw[i]
            if ch=='"': break
            if ch=='\\':
                if i+1>=len(raw): break
                n=6 if raw[i+1]=='u' else 2
                if i+n>len(raw): break
                try: out+=json.loads('"'+raw[i:i+n]+'"')
                except (ValueError,UnicodeError): break
                i+=n
            else: out+=ch; i+=1
        delta=out[len(self.emitted):]; self.emitted=out
        return delta

class Ollama:
    def __init__(self,endpoint='http://127.0.0.1:11434'):
        self.endpoint=endpoint.rstrip('/'); self.response=None; self.model=None; self.inflight=False
        self.prompt_json_models={'gemma4:31b-mlx'}  # Live probe 2026-09-21: native schema unsupported.
    async def models(self):
        async with httpx.AsyncClient(timeout=10,trust_env=False) as c:
            r=await c.get(self.endpoint+'/api/tags'); r.raise_for_status(); return r.json()['models']
    async def model_details(self,model):
        async with httpx.AsyncClient(timeout=10,trust_env=False) as c:
            r=await c.post(self.endpoint+'/api/show',json={'model':model}); r.raise_for_status(); return r.json()
    async def runtime_identity(self):
        async with httpx.AsyncClient(timeout=5,trust_env=False) as c:
            r=await c.get(self.endpoint+'/api/version'); r.raise_for_status()
            return r.json()
    async def resident(self):
        async with httpx.AsyncClient(timeout=5,trust_env=False) as c:
            r=await c.get(self.endpoint+'/api/ps'); r.raise_for_status(); return r.json().get('models',[])
    async def wait_idle(self,timeout=20):
        # keep_alive=0 belongs only to this request. Never unload arbitrary resident jobs.
        until=time.monotonic()+timeout
        while time.monotonic()<until:
            residents=await self.resident()
            if not any(m.get('name',m.get('model'))==self.model for m in residents):
                self.inflight=False; return
            await asyncio.sleep(.3)
        raise CancellationUnconfirmed('The request closed, but model residency/computation cessation could not be confirmed. New inference is blocked. Wait for the runtime to finish, then retry. No service was killed.')
    async def ensure_idle(self):
        residents=await self.resident()
        if residents: raise ProviderError('A model is already resident in the runtime. To avoid disturbing another application, wait until its work and residency finish, then retry.')
        self.inflight=False
    async def generate(self,model,messages,schema,options,on_public,on_usage,images=None):
        await self.ensure_idle()
        self.model=model; self.inflight=True
        decoder=PublicString(); raw=''; done=None
        body=dict(model=model,messages=messages,format=schema,stream=True,keep_alive=0,options=options)
        if model in self.prompt_json_models:
            body.pop('format')
            body['messages']=[dict(m) for m in messages]
            body['messages'][0]['content']+='\nReturn a JSON INSTANCE, not a schema. Put actual values at the TOP LEVEL; never wrap them in properties. Match this schema: '+json.dumps(schema,separators=(',',':'))
            if 'summary' in schema.get('properties',{}): body['messages'][0]['content']+='\nExact response shape example (replace values): {"summary":"Your direct observation here","uncertainty":[],"blocking_question":""}'
        if images: body['messages'][-1]['images']=images
        # Thinking is consumed only for accounting by server, never retained or emitted.
        async with httpx.AsyncClient(timeout=httpx.Timeout(600,connect=10),trust_env=False) as c:
            try:
                async with c.stream('POST',self.endpoint+'/api/chat',json=body) as r:
                    self.response=r; r.raise_for_status()
                    lines=r.aiter_lines().__aiter__()
                    while True:
                        try: line=await asyncio.wait_for(anext(lines),180)
                        except StopAsyncIteration: break
                        if not line: continue
                        part=json.loads(line)
                        if part.get('error'): raise ProviderError(part['error'])
                        content=part.get('message',{}).get('content','')
                        if content:
                            raw+=content
                            if len(raw)>150000: raise ProviderError('Model output exceeded safe size.')
                            if any(tag in raw.lower() for tag in ['<think>','<analysis>']): raise ProviderError('Private-thinking markup in public output; response rejected.')
                            delta=decoder.feed(content)
                            if delta: await on_public(delta)
                        if part.get('done'):
                            done=part
                            await on_usage(part.get('prompt_eval_count'),part.get('eval_count'))
            finally: self.response=None
        if done is None: raise ProviderError('Stream ended without final usage/completion marker.')
        await self.wait_idle()
        if done.get('done_reason')=='length': raise GenerationLength('Generation allowance exhausted before a complete structured response. Increase output limit in a new debate.')
        clean=raw.strip()
        if clean.startswith('```json\n') and clean.endswith('```'): clean=clean[8:-3].strip()
        elif clean.startswith('```\n') and clean.endswith('```'): clean=clean[4:-3].strip()
        try: return json.loads(clean)
        except ValueError as e: raise ProviderError('Model did not produce valid structured output; no turn/verdict committed.') from e
    async def cancel(self):
        if self.response: await self.response.aclose()
        if self.inflight: await self.wait_idle()
