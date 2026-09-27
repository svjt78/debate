"""Bounded source storage, DNS-pinned public fetching and cancellable extraction."""
import asyncio, base64, hashlib, ipaddress, json, os, socket, sys, time
from pathlib import Path
from urllib.parse import urlsplit, urljoin
import httpx
from .storage import uid

MAX_BYTES=int(os.getenv("DEBATE_MAX_SOURCE_MIB","25"))*1024*1024
MAX_MEDIA_SECONDS=int(os.getenv("DEBATE_MAX_MEDIA_SECONDS","600"))
PROCESS_SECONDS=int(os.getenv("DEBATE_PROCESS_SECONDS","180"))
SUFFIXES={'.txt','.md','.docx','.pdf','.png','.jpg','.jpeg','.webp','.wav','.mp3','.m4a','.ogg','.flac','.mp4','.mov','.webm'}
class EvidenceError(Exception): pass

def validate_url(url):
    p=urlsplit(url)
    if p.scheme not in {'http','https'} or not p.hostname or p.username or p.password or p.port not in {None,80,443}: raise EvidenceError('Only public HTTP(S) URLs on standard ports are supported.')
    return p
async def public_get(url,max_bytes=MAX_BYTES):
    requested=url
    async with httpx.AsyncClient(timeout=20,trust_env=False,follow_redirects=False) as client:
        for _ in range(6):
            p=validate_url(url); port=p.port or (443 if p.scheme=='https' else 80)
            records=await asyncio.wait_for(asyncio.get_running_loop().getaddrinfo(p.hostname,port,type=socket.SOCK_STREAM),5)
            ips=list({r[4][0] for r in records})
            if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips): raise EvidenceError('Local, private or reserved destinations are blocked.')
            ip=ips[0]; host='['+ip+']' if ':' in ip else ip
            target=httpx.URL(url).copy_with(host=ip)
            # Connect to the already validated IP; preserve HTTP Host and TLS SNI.
            async with client.stream('GET',target,headers={'Host':p.netloc,'User-Agent':'DebateLab/0.1 local evidence reader','Accept-Encoding':'identity'},extensions={'sni_hostname':p.hostname}) as r:
                if r.status_code in {301,302,303,307,308}:
                    location=r.headers.get('location')
                    if not location: raise EvidenceError('Redirect has no destination.')
                    url=urljoin(url,location); continue
                r.raise_for_status(); data=bytearray()
                async for chunk in r.aiter_bytes():
                    data.extend(chunk)
                    if len(data)>max_bytes: raise EvidenceError('URL response exceeds size limit.')
                return bytes(data),dict(requested_url=requested,final_url=url,retrieved_at=time.time(),content_type=r.headers.get('content-type',''))
    raise EvidenceError('Too many redirects.')

class Evidence:
    def __init__(self,store): self.store=store; self.process=None
    def stage_path(self,value):
        import stat
        path=Path(value).expanduser()
        if not path.is_absolute(): raise EvidenceError('Provide an absolute local file path.')
        path=path.resolve(strict=True)
        # Never open devices, pipes, or directories; only explicitly selected files.
        fd=os.open(path,os.O_RDONLY|os.O_NONBLOCK)
        with os.fdopen(fd,'rb') as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode): raise EvidenceError('Select a regular file, not a directory or device.')
            data=stream.read(MAX_BYTES+1)
        return self.stage(path.name,data,metadata={'import_method':'local-path','original_path':str(path)})

    async def process_batch(self,source):
        path=self.store.root/source['path']
        if source['kind']=='url' and not source['metadata'].get('retrieved_at'):
            host=urlsplit(source['metadata']['requested_url']).hostname or ''
            if any(host==x or host.endswith('.'+x) for x in ('youtube.com','youtu.be','vimeo.com')):
                raise EvidenceError('Hosted-video interpretation is deferred. Supply text or a supported document/image.')
            data,metadata=await public_get(source['metadata']['requested_url'])
            final_host=urlsplit(metadata['final_url']).hostname or ''
            if any(final_host==x or final_host.endswith('.'+x) for x in ('youtube.com','youtu.be','vimeo.com')):
                raise EvidenceError('This URL redirects to hosted video. Video interpretation is deferred.')
            content_type=metadata['content_type'].split(';')[0].lower()
            kind={'application/pdf':'pdf','application/vnd.openxmlformats-officedocument.wordprocessingml.document':'docx','image/png':'png','image/jpeg':'jpg','image/webp':'webp','text/plain':'txt','text/markdown':'md'}.get(content_type)
            if not kind and content_type not in {'text/html','application/xhtml+xml'}:
                raise EvidenceError('This URL does not return a supported webpage, document or image. Media interpretation is deferred.')
            temp=path.with_suffix('.download'); temp.write_bytes(data); temp.replace(path)
            source['metadata'].update(metadata); source['hash']=hashlib.sha256(data).hexdigest()
            if kind: source['kind']=kind
        checkpoint=source.setdefault('extraction',{'cursor':0,'total':None,'done':False})
        out=path.parent/'batch.json'
        env=os.environ.copy(); env.pop('OLLAMA_API_KEY',None); env.pop('DEBATE_SEARCH_KEY_FILE',None)
        env['PYTHONPATH']=str(Path(__file__).resolve().parents[1])
        proc=await asyncio.create_subprocess_exec(sys.executable,'-m','debate_lab.preparation_extract',str(path),source['kind'],str(out),str(checkpoint['cursor']),stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,env=env,start_new_session=True)
        self.process=proc
        try:
            _,stderr=await asyncio.wait_for(proc.communicate(),PROCESS_SECONDS)
            if proc.returncode: raise EvidenceError(stderr.decode(errors='replace')[-1500:] or 'Extraction batch failed.')
            result=json.loads(out.read_text())
            for item in result['passages']:
                item['id']=f"{source['id']}:P{len(source['passages'])+1}"; source['passages'].append(item)
            source.setdefault('images',[]).extend(result['images'])
            source['uncertainty']=list(dict.fromkeys(source['uncertainty']+result['uncertainty']))
            source['extraction']=dict(cursor=result['next_cursor'],total=result['total'],done=result['done'])
            source['extractor']='preparation-batch-v1'
            return source
        finally: await self.cancel(); self.process=None
    def stage(self,name,data,kind=None,metadata=None):
        if len(data)>MAX_BYTES: raise EvidenceError(f'Source exceeds {MAX_BYTES//1024//1024} MiB limit.')
        suffix=Path(name).suffix.lower()
        if kind not in {'text','url'} and suffix not in SUFFIXES: raise EvidenceError('Unsupported file type.')
        id='S'+uid()[:12]; folder=self.store.artifacts/id; folder.mkdir(mode=0o700)
        path=folder/('original'+(suffix if kind!='url' else '.html'))
        tmp=folder/'upload.tmp'
        with tmp.open('wb') as f: f.write(data); f.flush(); os.fsync(f.fileno())
        tmp.replace(path)
        return dict(id=id,name=Path(name).name,kind=kind or suffix[1:],path=str(path.relative_to(self.store.root)),hash=hashlib.sha256(data).hexdigest(),status='staged',version=1,created=time.time(),metadata=metadata or {},passages=[],summary=None,uncertainty=[],error=None,extractor='debate-lab-extract-v1')
    def stage_url(self,url):
        validate_url(url)
        return self.stage('supplied-url',url.encode(),'url',{'requested_url':url})
    async def process_source(self,source):
        path=self.store.root/source['path']
        if source['kind']=='url':
            data,metadata=await public_get(source['metadata']['requested_url'])
            source['metadata'].update(metadata)
            temp=path.with_suffix('.tmp'); temp.write_bytes(data); temp.replace(path)
            source['hash']=hashlib.sha256(data).hexdigest()
        out=path.parent/'extracted.json'
        env=os.environ.copy(); env.pop('OLLAMA_API_KEY',None); env.pop('DEBATE_SEARCH_KEY_FILE',None); env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]); env['HF_HUB_OFFLINE']='1'; env['HF_HOME']=str(self.store.root/'auxiliary-cache'); env['XDG_CACHE_HOME']=str(self.store.root/'cache')
        proc=await asyncio.create_subprocess_exec(sys.executable,'-m','debate_lab.extract',str(path),source['kind'],str(out),stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,env=env,start_new_session=True)
        self.process=proc
        try:
            stdout,stderr=await asyncio.wait_for(proc.communicate(),PROCESS_SECONDS)
            if proc.returncode: raise EvidenceError(stderr.decode(errors='replace')[-1500:] or 'Extraction failed.')
            result=json.loads(out.read_text())
            for n,item in enumerate(result['passages']): item['id']=f"{source['id']}:P{n+1}"
            source.update(result)
            if result.get('transcription'): source['metadata']['transcription']=result['transcription']
            source['extracted_at']=time.time(); source['extraction_version']=1
            return source
        finally:
            await self.cancel(); self.process=None
    async def cancel(self):
        p=self.process
        if p and p.returncode is None:
            import signal
            try: os.killpg(p.pid,signal.SIGTERM)
            except ProcessLookupError: pass
            try: await asyncio.wait_for(p.wait(),3)
            except asyncio.TimeoutError:
                try: os.killpg(p.pid,signal.SIGKILL)
                except ProcessLookupError: pass
                await asyncio.wait_for(p.wait(),3)
    def search_key(self):
        key=os.getenv('OLLAMA_API_KEY','').strip()
        if key: return key
        path=Path(os.getenv('DEBATE_SEARCH_KEY_FILE',str(self.store.root/'secrets'/'ollama-search-key')))
        if not path.is_file(): return ''
        if path.stat().st_mode & 0o077: raise EvidenceError('Search credential file must have owner-only permissions (chmod 600).')
        return path.read_text().strip()
    async def search(self,query):
        key=self.search_key()
        if not key: raise EvidenceError('Optional hosted search needs a configured app-local credential or server-side OLLAMA_API_KEY. Local inference needs no key. Supply evidence or continue without search.')
        async with httpx.AsyncClient(timeout=20,trust_env=False) as c:
            r=await c.post('https://ollama.com/api/web_search',headers={'Authorization':f'Bearer {key}'},json={'query':query,'max_results':3})
            if r.status_code in {401,403,429}: raise EvidenceError('Search credentials or free quota unavailable. Supply evidence or continue without search.')
            r.raise_for_status(); return r.json().get('results',[])[:3]
