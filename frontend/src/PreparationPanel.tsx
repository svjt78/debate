import React,{useState,useEffect} from 'react';
const fields:Record<string,string>={question:'Debate question',background:'Background',scope:'Scope',definitions:'Definitions',assumptions:'Assumptions',intended_resolution:'What the debate should resolve',alpha_position:'Alpha’s position',bravo_position:'Bravo’s position',position_rationale:'Why these positions',evidence_coverage:'Evidence coverage'};
export function PreparationPanel({run,busy,act}:{run:any;busy:boolean;act:(action:string,extra?:any)=>Promise<boolean>}){
 const p=run.preparation;
 const [answer,setAnswer]=useState(''),[query,setQuery]=useState(''),[accepted,setAccepted]=useState(false),[draft,setDraft]=useState<any>(null);
 useEffect(()=>{setAccepted(false)},[p.version]);
 const working=['PREPARING','PAUSING','STOPPING'].includes(run.state);
 const locked=busy||working||run.state==='CANCELED';
 const b=draft||p.brief;
 const gaps=p.output?.evidence_gaps||[], questions=p.output?.questions||[];
 const missing=p.current_limitations||[];
 return <section className="preparation-panel">
  <div className="eyebrow">PREPARE WITH CHARLIE</div><h2>Your subject, made clear.</h2>
  <p>Combine text, images, documents and public webpages in the evidence panel. Charlie helps interpret them and frame the question. Audio and video are deferred.</p>
  <div className="preparation-actions"><button className="secondary" disabled={locked} onClick={()=>act('analyze')}>{p.output?'Review inputs again':'Analyze inputs with Charlie'}</button>{p.approval&&<span className="status">Brief approved</span>}</div>
  {p.messages.length>0&&<div className="preparation-conversation">{p.messages.map((m:any,i:number)=><article key={i}><strong>{m.role==='Charlie'?'Charlie':m.role==='user'?'You':'Processing note'}</strong><p>{m.text}</p></article>)}</div>}
  {!!p.output?.suggested_questions?.length&&<div><h3>Possible debate questions</h3>{p.output.suggested_questions.map((q:string,i:number)=><button key={i} className="suggested-question" disabled={locked} onClick={()=>setAnswer(`Use this debate question: ${q}`)}>{q}</button>)}</div>}
  {!!questions.length&&<div className="preparation-questions"><h3>Questions for you</h3>{questions.map((q:any,i:number)=><div key={i}><p><strong>{i+1}. {q.question}</strong></p>{q.options.map((o:string,j:number)=><p key={j}>{String.fromCharCode(65+j)}. {o}</p>)}{q.recommendation&&<p>Recommendation: {q.recommendation}</p>}</div>)}</div>}
  <form onSubmit={async e=>{e.preventDefault();if(await act('message',{text:answer}))setAnswer('')}}><label>Your answer or correction<textarea aria-label="Answer Charlie" maxLength={4000} value={answer} onChange={e=>setAnswer(e.target.value)} placeholder="Answer the questions, clarify what an image means, or change the intended subject…" required/></label><button className="secondary" disabled={locked}>Send to Charlie</button></form>
  {!!gaps.length&&<div><h3>Evidence to collect</h3>{gaps.map((g:any,i:number)=><article className="evidence-gap" key={i}><strong>{g.needed}</strong><p>{g.reason}</p><p><b>Where to look:</b> {g.where_to_find}</p><p><b>What makes it useful:</b> {g.usefulness}</p></article>)}<p>You can supply evidence, narrow the question, or accept the remaining uncertainty before starting.</p></div>}
  <details><summary>Request public-web research</summary><p>Only runs when you request it. The query leaves this computer through the configured search service. Inaccessible sources remain disclosed.</p><form onSubmit={async e=>{e.preventDefault();await act('research',{text:query})}}><label>Search query<input value={query} onChange={e=>setQuery(e.target.value)} maxLength={4000} required/></label><button className="secondary" disabled={locked}>Search public sources</button></form></details>
  <h3>Review the debate brief</h3><p>Edit any field, including both positions. Save edits before approving.</p>
  <form onSubmit={async e=>{e.preventDefault();if(await act('edit',{brief:b})){setDraft(null);setAccepted(false)}}}>
   {Object.entries(fields).map(([key,label])=><label key={key}>{label}<textarea aria-label={label} rows={key==='question'?2:3} value={b[key]||''} maxLength={['background','question','alpha_position','bravo_position','evidence_coverage'].includes(key)?2000:1500} disabled={locked} onChange={e=>{setDraft({...b,[key]:e.target.value});setAccepted(false)}}/></label>)}
   <label>Brief limitations (one per line)<textarea value={(b.limitations||[]).join('\n')} disabled={locked} onChange={e=>setDraft({...b,limitations:e.target.value.split('\n').filter(Boolean)})}/></label>
   <button className="secondary" disabled={locked||!draft}>Save brief edits</button>
  </form>
  <h3>Coverage and remaining limitations</h3>
  {run.sources.map((s:any)=><p key={s.id}><strong>{s.name}</strong> · {s.status}{s.extraction?` · extracted ${s.extraction.cursor}/${s.extraction.total??'?'} units`:''}{s.interpretation?` · interpreted ${s.interpretation.images}/${s.images?.length||0} images, ${s.interpretation.chunks}/${s.interpretation.total_chunks??'?'} text chunks`:''}</p>)}
  {missing.length?<ul>{missing.map((x:string,i:number)=><li key={i}>{x}</li>)}</ul>:<p>No recorded gaps. This is not an independent verification of the evidence.</p>}
  <label className="checkbox-label"><input type="checkbox" checked={accepted} onChange={e=>setAccepted(e.target.checked)}/><span>I accept the listed gaps and coverage limitations. Unfinished sources will be excluded from debate evidence.</span></label>
  <button className="primary" disabled={locked||!!draft||(!accepted&&missing.length>0)} onClick={()=>act('approve',{accept_limitations:accepted})}>Approve debate brief</button>
  <p className="form-hint">Approval does not start the debate. Use Start when ready. Changing inputs or the brief requires approval again.</p>
 </section>
}
