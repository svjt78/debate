"""Isolated live long-debate, evidence, and forced-summary verification."""
import asyncio,json,sys,time,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from debate_lab.controller import Controller
from debate_lab.storage import Store
from debate_lab.provider import Ollama
from debate_lab.domain import NewSession,Settings,Command,Verdict
ROOT=Path(__file__).resolve().parents[1]
async def main():
 store=Store(ROOT/'.data/context-verification');main_store=Store(ROOT/'.data')
 store.set_preference('context_profiles',main_store.preference('context_profiles',{}))
 reports=json.loads((ROOT/'docs/context-scenarios.json').read_text()) if (ROOT/'docs/context-scenarios.json').exists() else []
 for label in (sys.argv[1:] or ['long','evidence','summary']):
  c=Controller(store,Ollama());settings=Settings(turn_limit=12 if label in {'long','long_evidence'} else 4,active_minutes=15)
  if label=='summary': settings.max_context_tokens=16384
  s=store.create(NewSession(proposition='A fictional library should trial an extra Saturday opening hour for four weeks.',settings=settings))
  if label in {'evidence','long_evidence'}:
   for i in range(3):
    data=(f'Fictional evidence source {i+1}. '+['Survey: 24 of 40 visitors requested later Saturday hours. The survey excluded nonvisitors. Staffing the extra hour costs 60 dollars weekly.','Operations: two librarians are needed. Volunteers cannot replace trained staff. Demand during exam periods may differ from summer.','Budget: the four-week trial would cost 240 dollars. No resulting attendance increase is yet measured. A permanent extension has not been costed.'][i]+' These facts are synthetic. No study validates demand or public benefit.\n')*6
    await c.add_source(s['id'],c.evidence.stage(f'synthetic-{i}.txt',data.encode(),'text'))
  started=time.monotonic();before=None
  if label=='summary':
   s=await c.pin(s)
   s['turns']=[{'id':f'T{i+1}','speaker':'Alpha' if i%2==0 else 'Bravo','phase':'rebuttal','ordinal':i+1,'text':('A trial is reversible, but costs must be monitored. Attendance and staffing feasibility remain uncertain. '*50),'claims':[],'concessions':['Attendance has not been measured.'],'action':'argument','evidence_version':0,'instruction_version':0} for i in range(8)]
   s['ending_reason']='user_stop_and_judge';c.freeze(s);s['state']='JUDGING';s=store.save(s);before=copy.deepcopy(s['turns']);c.launch(s['id'])
  else:await c.command(s['id'],Command(command='start',expected_revision=c.get(s['id'])['revision'],idempotency_key='context-'+s['id']))
  previous=None
  while c.task and not c.task.done():
   await asyncio.sleep(2);cur=c.get(s['id']);marker=(cur['state'],len(cur['turns']),cur['activity'],len(cur.get('history_summaries',[])))
   if marker!=previous:print(json.dumps({'scenario':label,'progress':marker,'seconds':round(time.monotonic()-started)}),flush=True);previous=marker
   if time.monotonic()-started>1200:
    await c.shutdown();break
  end=c.get(s['id']);result={'scenario':label,'id':s['id'],'state':end['state'],'turns':len(end['turns']),'summary_count':len(end.get('history_summaries',[])),'originals_unchanged':end['turns']==before if before else None,'outcome':(end.get('verdict') or {}).get('outcome'),'error':end['error'],'seconds':round(time.monotonic()-started),'capacities':sorted(set(a.get('options',{}).get('num_ctx',0) for a in end['attempts']))}
  result['passed']=end['state']=='COMPLETED' and (label!='summary' or bool(end.get('history_summaries')) and end['turns']==before)
  reports.append(result);print(json.dumps(result),flush=True);(ROOT/'docs/context-scenarios.json').write_text(json.dumps(reports,indent=2))
asyncio.run(main())
