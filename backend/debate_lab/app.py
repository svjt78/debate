from __future__ import annotations
import asyncio, fcntl, json, mimetypes, os, time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit
from fastapi import FastAPI, Request, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from .domain import *
from .storage import Store, Conflict
from .provider import Ollama, ProviderError
from .controller import Controller
from .evidence import MAX_BYTES, MAX_MEDIA_SECONDS, PROCESS_SECONDS, EvidenceError
from .preparation import invalidate, limitations

ROOT=Path(__file__).resolve().parents[2]
class TextBody(BaseModel): text: str=Field(max_length=100000)
class UrlBody(BaseModel): url: str=Field(max_length=4000)
class PathBody(BaseModel): path: str=Field(min_length=1,max_length=4096)
class CreateSessionBody(NewSession):
    preparation_mode: Literal['guided','prepared'] = 'guided'
class PreparationBody(BaseModel):
    action: Literal['analyze','message','edit','approve','research','fork']
    expected_revision: int
    text: str=Field('',max_length=4000)
    brief: DebateBrief | None = None
    accept_limitations: bool = False
class TurnsBody(BaseModel): total:int; expected_revision:int
class ContextBody(BaseModel):
    expected_revision:int
    max_context_tokens:int=Field(ge=2048,le=131072)
class Answer(BaseModel): choice:Literal['answer','decline','continue']; text:str=Field('',max_length=20000)

def create_app(root=None,provider=None):
    store=Store(root or os.getenv('DEBATE_DATA_DIR',str(ROOT/'.data')))
    engine=Controller(store,provider or Ollama())
    @asynccontextmanager
    async def lifespan(app):
        lock=(store.root/'controller.lock').open('a+')
        try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: raise RuntimeError('Another Debate Lab backend owns this data directory. Use one worker.')
        store.recover()
        try: yield
        finally:
            try: await engine.shutdown()
            finally: fcntl.flock(lock,fcntl.LOCK_UN); lock.close()
    app=FastAPI(title='Debate Lab',lifespan=lifespan)
    app.state.controller=engine; app.state.store=store
    @app.middleware('http')
    async def local_boundary(request,call_next):
        host=request.url.hostname
        if host not in {'127.0.0.1','localhost','testserver'}: return JSONResponse({'detail':'Invalid local host.'},400)
        origin=request.headers.get('origin')
        if origin and origin not in {str(request.base_url).rstrip('/'),'http://127.0.0.1:8787','http://localhost:8787','http://127.0.0.1:5173','http://localhost:5173'}: return JSONResponse({'detail':'Cross-origin access denied.'},403)
        if request.method not in {'GET','HEAD','OPTIONS'} and request.headers.get('sec-fetch-site')=='cross-site': return JSONResponse({'detail':'Cross-site command denied.'},403)
        length=request.headers.get('content-length')
        if length and int(length)>MAX_BYTES+1024*1024: return JSONResponse({'detail':'Request exceeds source size limit.'},413)
        response=await call_next(request)
        response.headers['X-Content-Type-Options']='nosniff'; response.headers['Referrer-Policy']='no-referrer'
        response.headers['Content-Security-Policy']="default-src 'self'; img-src 'self' data:; media-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-src 'self'; object-src 'none'; frame-ancestors 'none'"
        return response
    @app.exception_handler(Conflict)
    async def conflict(request,e):
        id=request.path_params.get('id'); state=None
        if id:
            try: state=store.get(id)
            except KeyError: pass
        return JSONResponse({'detail':str(e),'current':state},409)
    @app.exception_handler(KeyError)
    async def missing(request,e): return JSONResponse({'detail':'Session or artifact not found.'},404)
    @app.exception_handler(ValueError)
    async def invalid(request,e): return JSONResponse({'detail':str(e)},422)
    @app.exception_handler(ProviderError)
    @app.exception_handler(EvidenceError)
    async def integration(request,e): return JSONResponse({'detail':str(e)},503)
    @app.get('/api/health')
    async def health(): return {'status':'ok','version':'0.1.0','token_defaults':'provisional, not calibrated','limits':{'source_mib':MAX_BYTES//1024//1024,'media_minutes':MAX_MEDIA_SECONDS/60,'pdf_pages':int(os.getenv('DEBATE_MAX_PDF_PAGES','100')),'processing_seconds':PROCESS_SECONDS},'search_credentials_configured':bool(engine.evidence.search_key()),'transcription_configured':bool(os.getenv('DEBATE_WHISPER_MODEL'))}
    @app.get('/api/models')
    async def models():
        try: return {'models':await engine.provider.models()}
        except Exception as e: raise HTTPException(503,'Local model API unavailable. Check the existing service; the app will not start or reconfigure it.') from e
    @app.get('/api/defaults')
    async def defaults():
        values=store.preference('settings',{})
        if 'execution_policy' not in values: values={**values,'execution_policy':'completion','output_tokens':8192,'max_context_tokens':131072}
        return Settings(**values).model_dump()
    @app.put('/api/defaults')
    async def defaults_put(settings:Settings): store.set_preference('settings',settings.model_dump()); return settings
    @app.get('/api/sessions')
    async def sessions(): return [dict(id=s['id'],proposition=s['proposition'],state=s['state'],updated=s['updated'],turn_count=len(s['turns']),outcome=(s['verdict'] or {}).get('outcome'),parent_id=s['parent_id']) for s in store.all()]
    @app.post('/api/sessions')
    async def create(new:CreateSessionBody): return store.create(new)
    @app.get('/api/sessions/{id}')
    async def read(id:str):
        s=store.get(id)
        if s.get('preparation'): s['preparation']['current_limitations']=limitations(s)
        return s
    @app.post('/api/sessions/{id}/preparation')
    async def preparation(id:str,body:PreparationBody): return await engine.prepare_action(id,body)
    @app.post('/api/sessions/{id}/evidence/path')
    async def path_evidence(id:str,body:PathBody):
        try: source=engine.evidence.stage_path(body.path)
        except OSError as e: raise ValueError(f'Cannot read the selected local file: {e.strerror}')
        return await engine.add_source(id,source)
    @app.post('/api/sessions/{id}/commands')
    async def command(id:str,cmd:Command): return await engine.command(id,cmd)
    @app.patch('/api/sessions/{id}/context-settings')
    async def context_settings(id:str,body:ContextBody):
        async with engine.lock:
            s=store.get(id)
            if s['revision']!=body.expected_revision: raise Conflict('State changed; reload and retry.')
            if s['state'] not in {'DRAFT','PAUSED','FAILED_RECOVERABLE'} or s['job']: raise Conflict('Change context settings only while idle in draft, paused or recoverable failure.')
            settings=Settings(**{**{'execution_policy':'fixed'},**s['settings'],'max_context_tokens':body.max_context_tokens})
            s.setdefault('context_setting_changes',[]).append({'previous':s['settings'].get('max_context_tokens',32768),'maximum':body.max_context_tokens,'time':time.time()})
            s['settings']=settings.model_dump();return store.save(s,'context-settings-changed')
    @app.patch('/api/sessions/{id}/turn-limit')
    async def turn_limit(id:str,body:TurnsBody):
        async with engine.lock:
            s=store.get(id)
            if s['revision']!=body.expected_revision: raise Conflict('State changed; reload and retry.')
            change_turns(s,body.total); return store.save(s,'turn-limit-changed')
    @app.post('/api/sessions/{id}/evidence/text')
    async def text_evidence(id:str,body:TextBody):
        if not body.text.strip(): raise ValueError('Evidence cannot be empty.')
        return await engine.add_source(id,engine.evidence.stage('pasted-text.txt',body.text.encode(),'text'))
    @app.post('/api/sessions/{id}/evidence/url')
    async def url_evidence(id:str,body:UrlBody): return await engine.add_source(id,engine.evidence.stage_url(body.url))
    @app.post('/api/sessions/{id}/evidence')
    async def file_evidence(id:str,file:UploadFile=File(...)):
        data=await file.read(MAX_BYTES+1); return await engine.add_source(id,engine.evidence.stage(file.filename or 'source',data))
    @app.post('/api/sessions/{id}/evidence/{source_id}/exclude')
    async def exclude(id:str,source_id:str):
        async with engine.lock:
            s=store.get(id)
            if s['state'] not in {'DRAFT','PAUSED','AWAITING_USER','FAILED_RECOVERABLE'} or s['judgment_snapshot'] is not None: raise Conflict('Pause before excluding pending evidence.')
            src=next(x for x in s['sources'] if x['id']==source_id)
            if src['status']=='admitted': raise Conflict('Admitted evidence is immutable; start a new debate to change the evidence set.')
            src['status']='excluded'
            invalidate(s)
            for req in s['requests']:
                if req.get('source_id')==source_id and req['status']=='pending': req['status']='decline'
            if s['state']=='AWAITING_USER': s['state']='PAUSED'
            return store.save(s,'evidence-excluded')
    @app.post('/api/sessions/{id}/instructions')
    async def instructions(id:str,body:TextBody): return await engine.instruction(id,body.text)
    @app.post('/api/sessions/{id}/information-requests/{rid}/response')
    async def answer(id:str,rid:str,body:Answer): return await engine.respond(id,rid,body.choice,body.text)
    @app.get('/api/sessions/{id}/events')
    async def events(id:str,request:Request,after:int=0):
        store.get(id)
        try: after=max(after,int(request.headers.get('last-event-id','0')))
        except ValueError: raise HTTPException(400,'Invalid event sequence')
        async def stream():
            seq=after; live_before=None
            while not await request.is_disconnected():
                try:
                    rows=store.events(id,seq)
                    for event in rows:
                        seq=event['seq']; yield f'id: {seq}\nevent: state\ndata: {json.dumps(event)}\n\n'
                    live=engine.live.get(id)
                    snapshot=json.dumps(live)
                    if snapshot!=live_before:
                        yield f'event: public\ndata: {snapshot}\n\n'; live_before=snapshot
                    if not rows: yield ': heartbeat\n\n'
                except KeyError: return
                await asyncio.sleep(.25)
        return StreamingResponse(stream(),media_type='text/event-stream',headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'})
    @app.get('/api/sessions/{id}/sources/{sid}/original')
    async def original(id:str,sid:str):
        s=store.get(id); src=next((x for x in s['sources'] if x['id']==sid),None)
        if not src: raise KeyError(sid)
        path=(store.root/src['path']).resolve()
        if store.artifacts not in path.parents: raise HTTPException(403)
        kind=src['kind']; mime=mimetypes.guess_type('source.'+kind)[0] or 'application/octet-stream'
        if kind=='url' or mime in {'text/html','image/svg+xml'}: return FileResponse(path,media_type='application/octet-stream',filename=src['name'])
        return FileResponse(path,media_type=mime,content_disposition_type='inline')
    @app.get('/api/sessions/{id}/sources/{sid}/images/{name}')
    async def source_image(id:str,sid:str,name:str):
        s=store.get(id); src=next((x for x in s['sources'] if x['id']==sid),None)
        if not src or not any(x['path']==name for x in src.get('images',[])): raise KeyError(name)
        return FileResponse((store.root/src['path']).parent/name,media_type='image/png')
    @app.get('/api/sessions/{id}/export')
    async def export(id:str,format:Literal['markdown','json']='markdown'):
        s=store.get(id)
        if format=='json': return Response(json.dumps({'export_version':1,'limitations':['Media files are not embedded. Model claims are not independently verified.'],'run':s},indent=2),media_type='application/json',headers={'Content-Disposition':f'attachment; filename="debate-{id[:8]}.json"'})
        lines=[f'# {s["proposition"]}',f'State: {s["state"]}',f'Outcome: {(s["verdict"] or {}).get("outcome","No verdict")}', 'Model claims and source content are not independently verified. This export does not embed media files.']
        if s.get('preparation'):
            lines+=['## Debate preparation','### Brief',json.dumps(s['preparation']['brief'],ensure_ascii=False,indent=2),'### Approval and accepted limitations',json.dumps(s['preparation'].get('approval'),ensure_ascii=False,indent=2),'### Preparation conversation']
            for message in s['preparation']['messages']:
                lines += [f"**{message['role']}**",message['text']]
                if message.get('output'): lines.append(json.dumps(message['output'],ensure_ascii=False,indent=2))
        for t in s['turns']: lines += [f'## {t["id"]} · {t["speaker"]} · {t["phase"]}',f'Evidence version {t["evidence_version"]}; instruction version {t["instruction_version"]}',t['text']]
        lines+=['## Evidence']
        for x in s['sources']:
            lines+=[f'### {x["id"]}: {x["name"]} ({x["status"]})',f'SHA-256: {x["hash"]}',x.get('summary') or '',json.dumps(x['metadata'])]
            for p in x['passages']: lines += [f'{p["id"]} {json.dumps(p["locator"])}: {p["text"]}']
        lines+=['## Judgment',json.dumps(s['verdict'],indent=2),'## Usage',json.dumps({'accounted':s['usage'],'unknown_portions':s['usage_unknown'],'active_seconds':s['active_seconds'],'clock_uncertain':s['clock_uncertain']})]
        lines+=['## Context and summary provenance',json.dumps({k:s.get(k) for k in ['settings','request_context','context_setting_changes','context_versions','history_summaries','attempts','policy_upgrades','budget_adjustments','auxiliary_actions']},indent=2)]
        return Response('\n\n'.join(lines),media_type='text/markdown',headers={'Content-Disposition':f'attachment; filename="debate-{id[:8]}.md"'})
    @app.delete('/api/sessions/{id}')
    async def delete(id:str):
        async with engine.lock:
            s=store.get(id)
            if s['state'] in ACTIVE or s['job']: raise Conflict('Stop active work before deleting the session.')
            store.delete(id)
            import shutil
            shared={src['path'] for run in store.all() for src in run['sources']}
            for src in s['sources']:
                path=(store.root/src['path']).resolve()
                if src['path'] not in shared and store.artifacts in path.parents: shutil.rmtree(path.parent,ignore_errors=True)
        return {'deleted':id}
    dist=ROOT/'frontend/dist'
    if dist.exists(): app.mount('/',StaticFiles(directory=dist,html=True),name='frontend')
    return app

def factory(): return create_app()
