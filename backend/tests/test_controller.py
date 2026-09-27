import asyncio, json
import pytest
from debate_lab.storage import Store, Conflict
from debate_lab.domain import NewSession, Settings, Command, change_turns, schedule
from debate_lab.controller import Controller
from debate_lab.provider import PublicString, ProviderError
from debate_lab.evidence import public_get, validate_url, EvidenceError
from debate_lab.app import create_app
from fastapi.testclient import TestClient
from fakes import FakeProvider

def create(tmp_path,**settings):
    store=Store(tmp_path); fake=FakeProvider(); ctrl=Controller(store,fake)
    s=store.create(NewSession(proposition='Synthetic policy proposition',settings=Settings(turn_limit=4,**{'execution_policy':'fixed','output_tokens':3072,'max_context_tokens':32768,**settings})))
    return ctrl,fake,s
async def cmd(ctrl,s,command,key=None):
    cur=ctrl.get(s['id']); return await ctrl.command(s['id'],Command(command=command,expected_revision=cur['revision'],idempotency_key=key or command+'-unique-key'))
async def done(ctrl):
    if ctrl.task: await asyncio.wait_for(ctrl.task,5)

async def test_complete_debate_and_structured_judgment(tmp_path):
    c,p,s=create(tmp_path); await cmd(c,s,'start'); await done(c); s=c.get(s['id'])
    assert s['state']=='COMPLETED' and len(s['turns'])==4
    assert [t['speaker'] for t in s['turns']]==['Alpha','Bravo','Alpha','Bravo']
    assert s['verdict']['outcome']=='tie' and len(s['pinned'])==4
    assert all('thinking' not in t for t in s['turns'])

async def test_pause_resume_excludes_partial_and_keeps_next_speaker(tmp_path):
    c,p,s=create(tmp_path); p.delay=.5
    await cmd(c,s,'start'); await asyncio.sleep(.03); paused=await cmd(c,s,'pause')
    assert paused['state']=='PAUSED' and paused['turns']==[] and paused['usage_unknown']
    assert paused['attempts'][0]['status']=='interrupted' and p.cancelled
    used=paused['usage']['debate']; p.delay=.01
    await cmd(c,paused,'resume'); await done(c); end=c.get(s['id'])
    assert len(end['turns'])==4 and end['turns'][0]['speaker']=='Alpha' and end['usage']['debate']>=used

async def test_duplicate_start_and_single_active_session(tmp_path):
    c,p,s=create(tmp_path); p.delay=.5
    first=await cmd(c,s,'start',key='duplicate-start'); second=await cmd(c,s,'start',key='duplicate-start')
    assert first['id']==second['id']
    other=c.store.create(NewSession(proposition='Another proposition'))
    with pytest.raises(Conflict): await cmd(c,other,'start')
    await cmd(c,s,'cancel'); assert len(p.calls)<=1

async def test_restart_preserves_old_run_and_pins(tmp_path):
    c,p,s=create(tmp_path); p.delay=.5
    await cmd(c,s,'start'); await asyncio.sleep(.03); new=await cmd(c,s,'restart')
    assert new['id']!=s['id'] and new['parent_id']==s['id']
    assert c.get(s['id'])['state']=='CANCELED' and new['turns']==[] and new['pinned']==c.get(s['id'])['pinned']
    again=await cmd(c,s,'restart'); assert again['id']==new['id']

async def test_stop_before_any_turn_is_inconclusive(tmp_path):
    c,p,s=create(tmp_path); await cmd(c,s,'stop-and-judge'); await done(c)
    assert c.get(s['id'])['verdict']['reason']=='insufficient_debate' and not p.calls

async def test_cancellation_failure_blocks_new_work(tmp_path):
    c,p,s=create(tmp_path); p.delay=.5; p.fail_cancel=True
    await cmd(c,s,'start'); await asyncio.sleep(.02)
    with pytest.raises(Conflict): await cmd(c,s,'pause')
    assert c.blocked and c.get(s['id'])['state']=='FAILED_RECOVERABLE'

async def test_information_request_and_new_shared_evidence(tmp_path):
    c,p,s=create(tmp_path); p.next_action={'action':'request_information','question':'What is the measured baseline?','reason':'Needed for comparison'}
    await cmd(c,s,'start'); await done(c); s=c.get(s['id'])
    assert s['state']=='AWAITING_USER' and not s['turns']
    await c.respond(s['id'],s['requests'][0]['id'],'answer','The synthetic baseline is 10.')
    await cmd(c,s,'resume'); await done(c); s=c.get(s['id'])
    assert s['sources'][0]['status']=='admitted' and s['turns'][0]['evidence_version']==1

@pytest.mark.parametrize('choice',['decline','continue'])
async def test_information_request_other_paths(tmp_path,choice):
    c,p,s=create(tmp_path); p.next_action={'action':'request_information','question':'Baseline?'}
    await cmd(c,s,'start'); await done(c); s=c.get(s['id'])
    await c.respond(s['id'],s['requests'][0]['id'],choice,''); await cmd(c,s,'resume'); await done(c)
    assert c.get(s['id'])['state']=='COMPLETED'

async def test_invalid_verdict_never_committed(tmp_path):
    c,p,s=create(tmp_path); p.bad_verdict=True
    await cmd(c,s,'start'); await done(c); s=c.get(s['id'])
    assert s['state']=='FAILED_RECOVERABLE' and s['verdict'] is None and len(s['turns'])==4

def test_recovery_and_cas_atomicity(tmp_path):
    c,p,s=create(tmp_path); s.update(state='RUNNING',job={'id':'a','model':'test'},active_seconds=1.2)
    saved=c.store.save(s); c.store.recover(); recovered=c.get(s['id'])
    assert recovered['state']=='FAILED_RECOVERABLE' and recovered['clock_uncertain'] and recovered['active_seconds']==1.2
    with pytest.raises(Conflict): c.store.save(saved)
    assert c.get(s['id'])==recovered

def test_turn_count_edit_preserves_format_and_closings(tmp_path):
    c,p,s=create(tmp_path); change_turns(s,8); assert len(s['schedule'])==8
    s.update(state='PAUSED',turns=[{}]*3); change_turns(s,6)
    with pytest.raises(ValueError): change_turns(s,4)
    s['closing_started']=True
    with pytest.raises(ValueError): change_turns(s,8)
    with pytest.raises(ValueError): schedule(5)

async def test_mid_response_time_limit_and_separate_judgment(tmp_path):
    c,p,s=create(tmp_path,active_minutes=.001); p.delay=.2
    await cmd(c,s,'start'); await done(c); s=c.get(s['id'])
    assert s['state']=='COMPLETED' and not s['turns'] and s['verdict']['reason']=='insufficient_debate'
    assert s['usage_unknown'] and s['usage']['debate']>0

async def test_token_reservation_limit(tmp_path):
    c,p,s=create(tmp_path,debate_tokens=1024)
    await cmd(c,s,'start'); await done(c); s=c.get(s['id'])
    assert s['state']=='COMPLETED' and s['ending_reason']=='token_limit'

def test_public_json_stream_split_escapes():
    decoder=PublicString(); result=''
    for ch in json.dumps({'action':'argument','public_text':'Hello "world"\nline two ☀','claims':[]}): result+=decoder.feed(ch)
    assert result=='Hello "world"\nline two ☀'

@pytest.mark.parametrize('url',['file:///etc/passwd','ftp://example.com','http://user:pass@example.com','http://example.com:11434'])
def test_unsafe_url_syntax(url):
    with pytest.raises(EvidenceError): validate_url(url)
async def test_private_destination_blocked():
    with pytest.raises(EvidenceError): await public_get('http://127.0.0.1')

def test_api_exports_host_boundary_and_model_defaults(tmp_path):
    with TestClient(create_app(tmp_path,FakeProvider())) as client:
        s=client.post('/api/sessions',json={'proposition':'A test proposition'}).json()
        assert client.get(f'/api/sessions/{s["id"]}/export?format=json').json()['export_version']==1
        assert client.get('/api/sessions',headers={'host':'evil.example'}).status_code==400
        assert client.post('/api/sessions',headers={'origin':'https://evil.example'},json={'proposition':'Another'}).status_code==403
        defaults=client.get('/api/defaults').json(); defaults['models']['Alpha']='new-model'
        client.put('/api/defaults',json=defaults)
        assert client.get(f'/api/sessions/{s["id"]}').json()['settings']['models']['Alpha']!='new-model'

async def test_late_provider_result_cannot_commit_after_pause(tmp_path):
    c,p,s=create(tmp_path); original=p.generate
    async def late(*args,**kwargs):
        try: await asyncio.sleep(10)
        except asyncio.CancelledError: return await original(*args,**kwargs)
    p.generate=late
    await cmd(c,s,'start'); await asyncio.sleep(.02); await cmd(c,s,'pause')
    assert c.get(s['id'])['turns']==[] and c.get(s['id'])['state']=='PAUSED'

@pytest.mark.parametrize('phase',['INGESTING','JUDGING'])
async def test_pause_cancel_non_debate_phases(tmp_path,phase):
    c,p,s=create(tmp_path); p.delay=.2
    if phase=='INGESTING': await c.add_source(s['id'],c.evidence.stage('fixture.txt',b'Brief synthetic evidence.','text'))
    else:
        s.update(turns=[{'id':'T1','speaker':'Alpha','text':'One argument','evidence_version':0},{'id':'T2','speaker':'Bravo','text':'Another argument','evidence_version':0}],state='PAUSED');c.freeze(s);c.store.save(s)
    await cmd(c,s,'start' if phase=='INGESTING' else 'resume');await asyncio.sleep(.03)
    paused=await cmd(c,s,'pause'); assert paused['state']=='PAUSED' and paused['verdict'] is None
    await cmd(c,s,'resume');await asyncio.sleep(.03);await cmd(c,s,'cancel')
    assert c.get(s['id'])['state']=='CANCELED' and c.get(s['id'])['verdict'] is None

def test_actual_process_exit_at_transaction_boundary(tmp_path):
    import subprocess,sys,os
    for point in ['before_commit','after_commit']:
        root=tmp_path/point;store=Store(root);s=store.create(NewSession(proposition='Crash boundary fixture'))
        program="""
import os,sys
from debate_lab.storage import Store
store=Store(sys.argv[1]);s=store.get(sys.argv[2])
s['turns']=[{'id':'T1'}];s['usage']['debate']=123
if sys.argv[3]=='before_commit':
    def crash(*a,**k): os._exit(73)
    store._event=crash
store.save(s,'turn-committed')
os._exit(73)
"""
        result=subprocess.run([sys.executable,'-c',program,str(root),s['id'],point],env=dict(os.environ,PYTHONPATH=str(__import__('pathlib').Path('backend').resolve())))
        assert result.returncode==73
        recovered=Store(root).get(s['id'])
        assert (len(recovered['turns']),recovered['usage']['debate'])==((0,0) if point=='before_commit' else (1,123))
        events=store.events(s['id'],0)
        assert any(e['kind']=='turn-committed' for e in events)==(point=='after_commit')

async def test_changed_model_digest_is_recoverable_without_substitution(tmp_path):
    c,p,s=create(tmp_path);p.delay=.2;await cmd(c,s,'start');await asyncio.sleep(.01);await cmd(c,s,'pause')
    original=p.models
    async def changed(): return [dict(m,digest='changed') for m in await original()]
    p.models=changed
    with pytest.raises(ProviderError,match='digest changed'): await cmd(c,s,'resume')
    assert c.get(s['id'])['state']=='PAUSED'

async def test_search_disabled_cannot_issue_external_request(tmp_path):
    c,p,s=create(tmp_path);p.next_action={'action':'search','query':'synthetic query'}
    async def forbidden(*a): raise AssertionError('Search should never be called')
    c.evidence.search=forbidden
    await cmd(c,s,'start');await done(c)
    assert c.get(s['id'])['state']=='FAILED_RECOVERABLE' and not c.get(s['id'])['searches']

async def test_search_failure_pauses_for_user_without_paid_fallback(tmp_path):
    c,p,s=create(tmp_path,search_enabled=True);p.next_action={'action':'search','query':'synthetic query'}
    async def unavailable(*a): raise EvidenceError('Free quota unavailable')
    c.evidence.search=unavailable
    await cmd(c,s,'start');await done(c);s=c.get(s['id'])
    assert s['state']=='AWAITING_USER' and s['searches'][0]['status']=='failed'
    assert s['requests'][0]['status']=='pending'

async def test_local_retrieval_is_shared_and_bounded(tmp_path):
    c,p,s=create(tmp_path);source=c.evidence.stage('fixture.txt',b'A fact and a contrary caveat.','text')
    await c.add_source(s['id'],source);p.next_action={'action':'retrieve','requested_ids':[source['id']]}
    await cmd(c,s,'start');await done(c);s=c.get(s['id'])
    assert s['retrievals'][0]['items'][0]['text']=='A fact and a contrary caveat.' and s['state']=='COMPLETED'

async def test_successful_search_is_bounded_and_shared_with_both_roles(tmp_path):
    c,p,s=create(tmp_path,search_enabled=True,search_limit=1)
    p.next_action={'action':'search','query':'synthetic public evidence'}
    queries=[]
    async def search(query):
        queries.append(query);return [{'url':'https://example.com','title':'Synthetic fixture','content':'Example result'}]
    async def extract(source):
        source.update(passages=[{'id':source['id']+':P1','text':'A synthetic finding with a contrary caveat.','locator':{'passage':1}}],images=[],uncertainty=[])
        return source
    c.evidence.search=search;c.evidence.process_source=extract
    await cmd(c,s,'start');await done(c);s=c.get(s['id'])
    assert s['state']=='COMPLETED' and queries==['synthetic public evidence']
    assert s['sources'][0]['status']=='admitted' and len(s['searches'])==1
    assert all(t['evidence_version']==1 for t in s['turns'])
    for role in ['Alpha','Bravo']:
        calls=[json.loads(messages[-1]['content']) for model,messages in p.calls if model==s['settings']['models'][role]]
        assert any(payload.get('evidence_version')==1 and payload.get('sources') for payload in calls)

async def test_compact_judge_context_fits_without_relaxing_context_limit(tmp_path):
    from debate_lab.provider import compact_schema
    from debate_lab.domain import Verdict
    c,p,s=create(tmp_path)
    s=await c.pin(s);s['state']='JUDGING';s=c.store.save(s)
    schema=compact_schema(Verdict.model_json_schema())
    payload={'sources':[], 'turns':[], 'padding':''}
    # Input fits after removing JSON whitespace and schema display titles,
    # including the new framing allowance. The previous encoding rejects it.
    budget=s['settings']['context_tokens']-s['settings']['output_tokens']
    prompt=s['pinned']['Judge']['prompt_text']
    overhead=len(prompt.encode())+len(json.dumps(schema,separators=(',',':')).encode())+514
    # Whitespace savings grow with structural fields rather than source text.
    payload['records']=[{'id':str(i),'value':'synthetic'} for i in range(100)]
    base=len(json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode())
    payload['padding']='x'*(budget-overhead-base)
    old=len(prompt.encode())+len(json.dumps(payload).encode())+len(json.dumps(Verdict.model_json_schema()))
    assert old>budget
    await c.inference(s['id'],'Judge',payload,Verdict,'judgment')
    assert len(p.calls)==1
    sent=json.loads(p.calls[0][1][-1]['content'])
    assert sent==payload
    c.finish_job(c.get(s['id']))
    payload['padding']+='x'*2000
    with pytest.raises(ProviderError,match='context allowance'):
        await c.inference(s['id'],'Judge',payload,Verdict,'judgment')


def test_compact_schema_keeps_fields_named_title():
    from debate_lab.provider import compact_schema
    assert compact_schema({'title':'Display','properties':{'title':{'title':'Field','type':'string'}}})=={'properties':{'title':{'type':'string'}}}
