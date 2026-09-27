"""Versioned SQLite snapshot/event store; all public completion is transactional."""
import copy, json, os, time, uuid
from pathlib import Path
from sqlalchemy import create_engine, text, event
from .domain import NewSession, schedule, ACTIVE, DebateBrief

PROTECTED=Path('/Users/suvojitdutta/Documents/local_models').resolve()
def safe_root(path):
    p=Path(path).expanduser().resolve()
    if p==PROTECTED or PROTECTED in p.parents: raise ValueError('Protected model directory cannot hold application data.')
    p.mkdir(parents=True,exist_ok=True)
    return p

def uid(): return uuid.uuid4().hex
class Conflict(Exception): pass
class Store:
    def __init__(self,root):
        self.root=safe_root(root); self.artifacts=safe_root(self.root/'artifacts')
        self.engine=create_engine(f'sqlite:///{self.root / "debate.sqlite3"}',connect_args={'check_same_thread':False,'timeout':5})
        @event.listens_for(self.engine,'connect')
        def setup(c,_):
            c.execute('PRAGMA foreign_keys=ON'); c.execute('PRAGMA journal_mode=WAL'); c.execute('PRAGMA synchronous=FULL')
        with self.engine.begin() as c:
            c.execute(text('CREATE TABLE IF NOT EXISTS schema_versions (version INTEGER PRIMARY KEY, applied REAL NOT NULL)'))
            version=c.execute(text('SELECT MAX(version) FROM schema_versions')).scalar() or 0
            if version>1: raise RuntimeError('Database created by a newer application.')
            if version<1:
                for sql in [
                  'CREATE TABLE runs (id TEXT PRIMARY KEY, revision INTEGER NOT NULL, updated REAL NOT NULL, body TEXT NOT NULL)',
                  'CREATE TABLE events (seq INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE, kind TEXT NOT NULL, body TEXT NOT NULL, created REAL NOT NULL)',
                  'CREATE TABLE commands (run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE, key TEXT NOT NULL, result TEXT NOT NULL, PRIMARY KEY(run_id,key))',
                  'CREATE TABLE preferences (key TEXT PRIMARY KEY, body TEXT NOT NULL)',
                  'CREATE INDEX events_run_seq ON events(run_id,seq)']:
                    c.execute(text(sql))
                c.execute(text('INSERT INTO schema_versions VALUES (1,:t)'),{'t':time.time()})
    def create(self,new:NewSession,parent=None,pinned=None):
        now=time.time()
        s=dict(id=uid(),parent_id=parent,proposition=new.proposition,alpha_position=new.alpha_position or 'Support the proposition',bravo_position=new.bravo_position or 'Oppose the proposition',settings=new.settings.model_dump(),pinned=pinned or {},revision=0,state='DRAFT',phase='ingestion',activity='Ready for evidence',created=now,updated=now,turns=[],schedule=schedule(new.settings.turn_limit),sources=[],instructions=[],evidence_version=0,instruction_version=0,claims=[],requests=[],searches=[],attempts=[],usage={'ingestion':0,'debate':0,'judgment':0},usage_unknown=False,active_seconds=0.,clock_uncertain=False,closing_started=False,job=None,judgment_snapshot=None,verdict=None,error=None,ending_reason=None)
        if new.preparation_mode:
            s['preparation']=dict(version=1, mode=new.preparation_mode,status='draft',messages=[],brief=DebateBrief(question=new.proposition,alpha_position=new.alpha_position,bravo_position=new.bravo_position).model_dump(),history=[],approval=None,output=None,integrated=[],pending_message=None,search=None)
            s['usage']['preparation']=0
            s['phase']='preparation'; s['activity']='Prepare your subject with Charlie'
        with self.engine.begin() as c:
            c.execute(text('INSERT INTO runs VALUES (:id,0,:t,:body)'),{'id':s['id'],'t':now,'body':json.dumps(s)})
            self._event(c,s,'checkpoint-saved',{'reason':'created','revision':0})
        return s
    def _event(self,c,s,kind,payload):
        c.execute(text('INSERT INTO events(run_id,kind,body,created) VALUES (:id,:kind,:body,:t)'),{'id':s['id'],'kind':kind,'body':json.dumps(payload),'t':time.time()})
    def get(self,id):
        with self.engine.connect() as c: row=c.execute(text('SELECT body FROM runs WHERE id=:id'),{'id':id}).scalar()
        if row is None: raise KeyError(id)
        return json.loads(row)
    def all(self):
        with self.engine.connect() as c: rows=c.execute(text('SELECT body FROM runs ORDER BY updated DESC')).scalars().all()
        return [json.loads(r) for r in rows]
    def save(self,s,kind='checkpoint-saved',payload=None,command=None):
        s=copy.deepcopy(s); previous=s['revision']; s['revision']+=1; s['updated']=time.time()
        with self.engine.begin() as c:
            n=c.execute(text('UPDATE runs SET revision=:rev,updated=:t,body=:body WHERE id=:id AND revision=:old'),{'rev':s['revision'],'t':s['updated'],'body':json.dumps(s),'id':s['id'],'old':previous}).rowcount
            if n!=1: raise Conflict('State changed; reload and retry.')
            self._event(c,s,kind,dict(payload or {},revision=s['revision']))
            if command:
                key,result=command
                c.execute(text('INSERT INTO commands VALUES (:id,:key,:result)'),{'id':s['id'],'key':key,'result':json.dumps(result)})
        return s
    def command_result(self,id,key):
        with self.engine.connect() as c: result=c.execute(text('SELECT result FROM commands WHERE run_id=:id AND key=:key'),{'id':id,'key':key}).scalar()
        return json.loads(result) if result else None
    def events(self,id,after):
        with self.engine.connect() as c: rows=c.execute(text('SELECT seq,kind,body FROM events WHERE run_id=:id AND seq>:seq ORDER BY seq LIMIT 200'),{'id':id,'seq':after}).all()
        return [dict(seq=r[0],kind=r[1],data=json.loads(r[2])) for r in rows]
    def recover(self):
        for s in self.all():
            if s['state'] in ACTIVE or s['job']:
                if s['job']:
                    s['attempts'].append(dict(s['job'],status='interrupted',input_tokens=None,output_tokens=None))
                    s['usage_unknown']=True; s['clock_uncertain']=True
                    s['recovery_model']=s['job'].get('model')
                s.update(state='FAILED_RECOVERABLE',job=None,activity='Recovered; manual retry required',error='Interrupted by backend shutdown. Last committed state restored. Recent usage/time may be incomplete.')
                self.save(s,'recoverable-error')
    def preference(self,key,default=None):
        with self.engine.connect() as c: raw=c.execute(text('SELECT body FROM preferences WHERE key=:key'),{'key':key}).scalar()
        return json.loads(raw) if raw else default
    def set_preference(self,key,value):
        with self.engine.begin() as c: c.execute(text('INSERT INTO preferences VALUES (:key,:body) ON CONFLICT(key) DO UPDATE SET body=excluded.body'),{'key':key,'body':json.dumps(value)})
    def delete(self,id):
        with self.engine.begin() as c: c.execute(text('DELETE FROM runs WHERE id=:id'),{'id':id})
