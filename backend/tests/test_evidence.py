import asyncio, json
from pathlib import Path
import pytest
from PIL import Image, ImageDraw
from debate_lab.storage import Store
from debate_lab.evidence import Evidence, EvidenceError

async def test_text_and_markdown_preserve_original_hash_and_lines(tmp_path):
    e=Evidence(Store(tmp_path)); src=e.stage('source.md',b'# Synthetic\nA first passage.\n\nA second passage.')
    processed=await e.process_source(src)
    assert (tmp_path/src['path']).read_bytes()==b'# Synthetic\nA first passage.\n\nA second passage.'
    assert processed['passages'][-1]['locator']['line']==4
    assert all(p['id'].startswith(src['id']) for p in processed['passages'])
async def test_image_and_scanned_pdf_keep_locators(tmp_path):
    e=Evidence(Store(tmp_path)); im=Image.new('RGB',(500,220),'white'); ImageDraw.Draw(im).text((20,30),'Synthetic scanned fixture: 42 visitors',fill='black')
    import io
    data=io.BytesIO(); im.save(data,format='PNG'); src=e.stage('image.png',data.getvalue()); result=await e.process_source(src)
    assert result['images'][0]['locator']=={'image':1}
    data=io.BytesIO(); im.save(data,format='PDF'); src=e.stage('scan.pdf',data.getvalue()); result=await e.process_source(src)
    assert result['images'][0]['locator']=={'page':1} and result['uncertainty']
async def test_corrupt_file_fails_without_fake_extraction(tmp_path):
    e=Evidence(Store(tmp_path)); src=e.stage('broken.pdf',b'not a PDF')
    with pytest.raises(EvidenceError): await e.process_source(src)
async def test_search_missing_credentials_explicit(tmp_path,monkeypatch):
    monkeypatch.delenv('OLLAMA_API_KEY',raising=False)
    with pytest.raises(EvidenceError,match='API_KEY'): await Evidence(Store(tmp_path)).search('test query')

def test_protected_model_path_rejected():
    with pytest.raises(ValueError): Store('/Users/suvojitdutta/Documents/local_models/debate-data')

async def test_media_without_model_fails_honestly(tmp_path,monkeypatch):
    import io,wave
    monkeypatch.delenv('DEBATE_WHISPER_MODEL',raising=False)
    data=io.BytesIO()
    with wave.open(data,'wb') as wav:
        wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(16000);wav.writeframes(b'\0\0'*16000)
    e=Evidence(Store(tmp_path));src=e.stage('synthetic-silence.wav',data.getvalue())
    with pytest.raises(EvidenceError,match='transcription model unavailable'): await e.process_source(src)

def test_private_search_key_file_and_environment_precedence(tmp_path,monkeypatch):
    monkeypatch.delenv('OLLAMA_API_KEY',raising=False);monkeypatch.delenv('DEBATE_SEARCH_KEY_FILE',raising=False)
    e=Evidence(Store(tmp_path));assert e.search_key()==''
    secrets=tmp_path/'secrets';secrets.mkdir();keyfile=secrets/'ollama-search-key';keyfile.write_text('synthetic-test-key\n');keyfile.chmod(0o600)
    assert e.search_key()=='synthetic-test-key'
    monkeypatch.setenv('OLLAMA_API_KEY','synthetic-env-key');assert e.search_key()=='synthetic-env-key'
    monkeypatch.delenv('OLLAMA_API_KEY');keyfile.chmod(0o644)
    with pytest.raises(EvidenceError,match='owner-only'):e.search_key()

@pytest.mark.parametrize('status',[401,403,429])
async def test_search_auth_and_quota_errors_do_not_expose_key(tmp_path,monkeypatch,status):
    import httpx
    monkeypatch.setenv('OLLAMA_API_KEY','synthetic-sensitive-key')
    original=httpx.AsyncClient
    def handler(request):
        assert request.url=='https://ollama.com/api/web_search'
        assert request.headers['authorization']=='Bearer synthetic-sensitive-key'
        return httpx.Response(status,json={'error':'Unavailable'})
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(handler),**kwargs))
    with pytest.raises(EvidenceError) as exc:await Evidence(Store(tmp_path)).search('synthetic query')
    assert 'synthetic-sensitive-key' not in str(exc.value) and 'free quota' in str(exc.value)
