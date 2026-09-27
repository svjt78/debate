"""Deterministic provider exclusively for tests. Never imported by production."""
import asyncio
from debate_lab.domain import DEFAULT_MODELS
class FakeProvider:
    endpoint='test://deterministic'
    def __init__(self): self.calls=[]; self.delay=.01; self.cancelled=0; self.fail_cancel=False; self.next_action=None; self.bad_verdict=False
    async def models(self): return [{'name':m,'digest':'test-digest','capabilities':['completion','vision']} for m in set(DEFAULT_MODELS.values())]
    async def ensure_idle(self): pass
    async def cancel(self):
        self.cancelled+=1
        if self.fail_cancel: raise RuntimeError('Cancellation not confirmed')
    async def generate(self,model,messages,schema,options,on_public,on_usage,images=None):
        self.calls.append((model,messages)); await on_public('A public argument.'); await asyncio.sleep(self.delay); await on_usage(100,50)
        if 'outcome' in schema.get('properties',{}):
            return dict(outcome='tie',reason='balanced',justification='Both sides raised valid points.',scores={r:dict(evidence=2,logic=3,relevance=4,engagement=3) for r in ['Alpha','Bravo']},references=['T999'] if self.bad_verdict else ['T1','T2'],supported_claims=[],unsupported_claims=['General assertions'],decisive_objections=[],concessions=[],limitations=['Synthetic test'],surrender_confirmed=True)
        if 'summary' in schema.get('properties',{}): return dict(summary='A supplied synthetic source.',uncertainty=[],blocking_question='')
        result=dict(action='argument',public_text='A public argument with unverified assumptions.',claims=[dict(text='An assertion',references=[],status='unverified')],concessions=[],question='',reason='',query='')
        if self.next_action: result.update(self.next_action); self.next_action=None
        return result
