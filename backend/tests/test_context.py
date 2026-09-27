import copy,json
import pytest
from debate_lab.context import estimate,choose_context,profile_key
from debate_lab.domain import NewSession,Settings,HistorySummary,Verdict
# These tests exercise the pre-upgrade fixed policy. Completion mode has separate coverage.
_OriginalNewSession=NewSession
def NewSession(**kwargs):
 kwargs.setdefault('settings',Settings(execution_policy='fixed',output_tokens=3072,max_context_tokens=32768))
 return _OriginalNewSession(**kwargs)
from debate_lab.controller import Controller
from debate_lab.storage import Store
from debate_lab.provider import ProviderError
from fakes import FakeProvider

def test_capacity_and_estimator_boundaries():
 s=Settings().model_dump();p={'tested_contexts':[16384,24576,32768],'bytes_to_tokens':.4,'max_bytes':10000}
 assert choose_context(s,17000,p)==24576
 assert choose_context(dict(s,max_context_tokens=16384),17000,p) is None
 assert choose_context(s,17000,None) is None
 assert estimate([{'content':'text'*100}],{},p)[1]=='calibrated estimate'
 assert estimate([{'content':'中文'*100}],{},p)[1]=='conservative byte bound'
 assert estimate([{'content':'x'*10001}],{},p)[1]=='conservative byte bound'
 assert profile_key({'model':'a','digest':'1','endpoint':'x'},'v1')!=profile_key({'model':'a','digest':'1','endpoint':'x'},'v2')

class HistoryProvider(FakeProvider):
 async def generate(self,model,messages,schema,options,on_public,on_usage,images=None):
  if 'items' in schema.get('properties',{}):
   self.calls.append((model,messages));await on_usage(100,80)
   t=json.loads(messages[-1]['content'])['turn']
   return {'items':[{'turn_id':t['id'],'speaker':t['speaker'],'position':'Preserved position','objections':['Counterargument'], 'unresolved':['Unresolved issue'],'covered_claims':list(range(len(t['claims']))),'covered_concessions':list(range(len(t['concessions'])))}]}
  return await super().generate(model,messages,schema,options,on_public,on_usage,images)

async def test_summaries_preserve_records_reuse_cache_and_keep_last_each_side(tmp_path):
 store=Store(tmp_path);p=HistoryProvider();c=Controller(store,p);s=store.create(NewSession(proposition='Synthetic summary coverage'))
 s=await c.pin(s);s['state']='RUNNING'
 s['turns']=[{'id':f'T{i+1}','speaker':'Alpha' if i%2==0 else 'Bravo','text':'Original '*200,'claims':[{'text':'Claim','references':[],'status':'challenged'}],'concessions':['Concession'],'evidence_version':0,'instruction_version':0} for i in range(4)]
 s=store.save(s);original=copy.deepcopy(s['turns']);payload=c.context(s)
 result=await c.summarized_context(s['id'],payload,'debate')
 assert [t['id'] for t in result['turns']]==['T3','T4']
 assert result['older_turns'][0]['claims']==original[0]['claims']
 assert result['older_turns'][0]['concessions']==original[0]['concessions']
 assert c.get(s['id'])['turns']==original
 assert c.get(s['id'])['usage']['debate']==360
 await c.summarized_context(s['id'],payload,'debate')
 assert len(p.calls)==2
 assert len(c.get(s['id'])['history_summaries'])==2

async def test_expansion_records_effective_options_and_stale_profile_is_ignored(tmp_path):
 store=Store(tmp_path);p=FakeProvider();c=Controller(store,p);s=store.create(NewSession(proposition='Synthetic context expansion'))
 s=await c.pin(s);s['state']='JUDGING';s=store.save(s)
 key=profile_key(s['pinned']['Judge'],c.runtime)
 store.set_preference('context_profiles',{key:{'tested_contexts':[24576,32768]}})
 await c.inference(s['id'],'Judge',{'padding':'x'*15000},Verdict,'judgment')
 current=c.get(s['id']);assert current['job']['options']['num_ctx']==24576
 assert current['pinned']['Judge']['options']['num_ctx']==16384
 assert current['request_context']['expanded']
 store.set_preference('context_profiles',{'stale':{'tested_contexts':[32768]}})
 with pytest.raises(ProviderError,match='context allowance'):
  await c.inference(s['id'],'Judge',{'padding':'x'*15000},Verdict,'judgment')

def test_context_settings_revision_and_existing_runs(tmp_path):
 from debate_lab.app import create_app
 from fastapi.testclient import TestClient
 with TestClient(create_app(tmp_path,FakeProvider())) as client:
  s=client.post('/api/sessions',json={'proposition':'Synthetic context settings'}).json()
  path=f"/api/sessions/{s['id']}/context-settings"
  r=client.patch(path,json={'expected_revision':s['revision'],'max_context_tokens':24576})
  assert r.status_code==200 and r.json()['settings']['max_context_tokens']==24576
  assert client.patch(path,json={'expected_revision':s['revision'],'max_context_tokens':32768}).status_code==409
  assert r.json()['turns']==[] and r.json()['usage']==s['usage']

async def test_summary_bad_coverage_and_budget_failure_do_not_commit_summary(tmp_path):
 class BadHistory(HistoryProvider):
  async def generate(self,*args,**kwargs):
   result=await super().generate(*args,**kwargs)
   if 'items' in result:result['items'][0]['covered_claims']=[]
   return result
 store=Store(tmp_path);c=Controller(store,BadHistory());s=store.create(NewSession(proposition='Synthetic invalid summary'))
 s=await c.pin(s);s['state']='RUNNING';s['turns']=[{'id':f'T{i}','speaker':'Alpha' if i%2 else 'Bravo','text':'Original','claims':[{'text':'Important claim','references':[]}],'concessions':[],'evidence_version':0,'instruction_version':0} for i in range(3)];s=store.save(s)
 with pytest.raises(ProviderError,match='coverage'):
  await c.summarized_context(s['id'],c.context(s),'debate')
 assert not store.get(s['id']).get('history_summaries')
 current=store.get(s['id']);current['usage']['debate']=current['settings']['debate_tokens'];store.save(current)
 with pytest.raises(ProviderError,match='token allowance'):
  await c.summarized_context(s['id'],c.context(s),'debate')
 assert store.get(s['id'])['turns']==s['turns']

async def test_oversized_retrieval_cannot_bypass_context_guard(tmp_path):
 c=Controller(Store(tmp_path),FakeProvider());s=c.store.create(NewSession(proposition='Synthetic retrieval bounds'));s=await c.pin(s);s['state']='JUDGING';s=c.store.save(s)
 with pytest.raises(ProviderError,match='context allowance'):
  await c.inference(s['id'],'Judge',{'inspected_original_material':[{'id':'T1','text':'x'*40000}]},Verdict,'judgment')
 assert not c.provider.calls

async def test_pause_during_summary_preserves_originals_and_resumes(tmp_path):
 import asyncio
 from debate_lab.domain import Command
 class SlowHistory(HistoryProvider):
  async def generate(self,*args,**kwargs):
   await asyncio.sleep(.15)
   return await super().generate(*args,**kwargs)
 store=Store(tmp_path);c=Controller(store,SlowHistory());s=store.create(NewSession(proposition='Synthetic summary interruption'))
 s=await c.pin(s)
 s['turns']=[{'id':f'T{i+1}','speaker':'Alpha' if i%2==0 else 'Bravo','text':'Original record. '*190,'claims':[],'concessions':[],'evidence_version':0,'instruction_version':0} for i in range(8)]
 originals=copy.deepcopy(s['turns']);s['ending_reason']='user_stop_and_judge';c.freeze(s);s['state']='JUDGING';s=store.save(s);c.launch(s['id'])
 await asyncio.sleep(.03);current=c.get(s['id'])
 paused=await c.command(s['id'],Command(command='pause',expected_revision=current['revision'],idempotency_key='pause-summary-test'))
 assert paused['state']=='PAUSED' and paused['turns']==originals
 assert not paused.get('history_summaries')
 assert paused['attempts'][-1]['status']=='interrupted'
 await c.command(s['id'],Command(command='resume',expected_revision=paused['revision'],idempotency_key='resume-summary-test'))
 await asyncio.wait_for(c.task,5)
 end=c.get(s['id']);assert end['state']=='COMPLETED' and end['turns']==originals
 assert len(end['history_summaries'])==6
