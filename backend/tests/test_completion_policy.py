import copy
import pytest
from debate_lab.domain import Settings,NewSession,Command
from debate_lab.storage import Store,Conflict
from debate_lab.controller import Controller
from debate_lab.context import profile_key
from debate_lab.provider import GenerationLength,ProviderError
from fakes import FakeProvider

async def command(c,s,name,key):
 return await c.command(s['id'],Command(command=name,expected_revision=c.get(s['id'])['revision'],idempotency_key=key))

async def test_completion_ignores_legacy_time_and_extends_budget(tmp_path):
 c=Controller(Store(tmp_path),FakeProvider())
 s=c.store.create(NewSession(proposition='Twelve turn completion fixture',settings=Settings(active_minutes=.001,debate_tokens=1024)))
 await command(c,s,'start','start-completion');await c.task
 end=c.get(s['id'])
 assert end['state']=='COMPLETED' and len(end['turns'])==12
 assert [t['speaker'] for t in end['turns']].count('Alpha')==6
 assert end['budget_adjustments'] and end['verdict']
 assert all(a['options']['num_predict']==8192 for a in end['attempts'])

async def test_length_retry_doubles_once_and_keeps_accounting(tmp_path):
 class Length(FakeProvider):
  async def generate(self,model,messages,schema,options,public,usage,images=None):
   if options['num_predict']==8192:
    await usage(100,8192);raise GenerationLength('length')
   return await super().generate(model,messages,schema,options,public,usage,images)
 c=Controller(Store(tmp_path),Length());s=c.store.create(NewSession(proposition='Retry fixture',settings=Settings(context_tokens=32768)))
 s=await c.pin(s);s=c.store.save(s);c.store.set_preference('context_profiles',{profile_key(p,c.runtime):{'tested_contexts':[32768]} for p in s['pinned'].values()})
 await command(c,s,'start','start-retry');await c.task
 end=c.get(s['id']);assert end['state']=='COMPLETED'
 assert sum(a['status']=='length_exhausted' for a in end['attempts'])==13
 assert end['usage']['debate']>12*8192

async def test_second_length_exhaustion_stops_recoverably(tmp_path):
 class AlwaysLength(FakeProvider):
  async def generate(self,*args,**kwargs):raise GenerationLength('length')
 c=Controller(Store(tmp_path),AlwaysLength());s=c.store.create(NewSession(proposition='Bounded failure',settings=Settings(context_tokens=32768)))
 s=await c.pin(s);s=c.store.save(s);c.store.set_preference('context_profiles',{profile_key(p,c.runtime):{'tested_contexts':[32768]} for p in s['pinned'].values()})
 await command(c,s,'start','start-failure');await c.task
 end=c.get(s['id']);assert end['state']=='FAILED_RECOVERABLE' and len(end['attempts'])==2 and not end['turns']

async def test_upgrade_is_idempotent_preserves_turns_and_legacy_policy(tmp_path):
 c=Controller(Store(tmp_path),FakeProvider());s=c.store.create(NewSession(proposition='Saved session',settings=Settings(execution_policy='fixed',output_tokens=3072)))
 s['state']='PAUSED';s['settings'].pop('execution_policy');s=c.store.save(s)
 before=copy.deepcopy(s['turns']);old=copy.deepcopy(s['settings'])
 upgraded=await command(c,s,'upgrade-resume','upgrade-saved');await c.task
 duplicate=await command(c,s,'upgrade-resume','upgrade-saved')
 assert duplicate['id']==s['id'] and len(duplicate['policy_upgrades'])==1
 assert duplicate['policy_upgrades'][0]['previous']==old
 assert duplicate['turns'][:len(before)]==before and len(duplicate['turns'])==12
 assert duplicate['state']=='COMPLETED'
 with pytest.raises(Conflict):await command(c,s,'upgrade-resume','another-upgrade')

async def test_upgrade_keeps_seven_completed_turns_exactly(tmp_path):
 c=Controller(Store(tmp_path),FakeProvider());s=c.store.create(NewSession(proposition='Preserve seven arguments',settings=Settings(execution_policy='fixed',output_tokens=3072)))
 s['turns']=[{'id':f'T{i+1}','speaker':'Alpha' if i%2==0 else 'Bravo','phase':'opening' if i<2 else 'rebuttal','ordinal':i+1,'text':f'Original argument {i+1}.','claims':[],'concessions':[],'action':'argument','evidence_version':0,'instruction_version':0} for i in range(7)]
 s['state']='FAILED_RECOVERABLE';originals=copy.deepcopy(s['turns']);s=c.store.save(s)
 await command(c,s,'upgrade-resume','seven-turn-upgrade');await c.task
 end=c.get(s['id']);assert end['state']=='COMPLETED' and len(end['turns'])==12
 assert end['turns'][:7]==originals and end['turns'][7]['speaker']=='Bravo'

async def test_auxiliary_retrieval_loop_stops_after_four_actions(tmp_path):
 class Retrieval(FakeProvider):
  async def generate(self,model,messages,schema,options,public,usage,images=None):
   await usage(100,10)
   return {'action':'retrieve','public_text':'Inspect original evidence.','requested_ids':['S1:P1']}
 c=Controller(Store(tmp_path),Retrieval());s=c.store.create(NewSession(proposition='Bounded retrieval fixture'))
 s['sources']=[{'id':'S1','name':'fixture','summary':'Fact','uncertainty':[],'status':'admitted','passages':[{'id':'S1:P1','text':'Fact','locator':{'line':1}}]}];s=c.store.save(s)
 await command(c,s,'start','retrieval-loop');await c.task
 end=c.get(s['id']);assert end['state']=='FAILED_RECOVERABLE' and 'Four auxiliary' in end['error']
 assert end['auxiliary_actions']['1']==4 and not end['turns']
