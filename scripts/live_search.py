"""One authenticated hosted-search query; never prints credentials or headers."""
import asyncio,json,os,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'backend'))
os.environ['DEBATE_SEARCH_KEY_FILE']=str(ROOT/'.data/secrets/ollama-search-key')
from debate_lab.evidence import Evidence,public_get
from debate_lab.storage import Store

async def main():
    e=Evidence(Store(ROOT/'.data/search-verification'))
    query='site:docs.ollama.com web search API authentication'
    report={'provider':'Ollama hosted web search','query':query,'max_results':3,'started_at':time.time()}
    try:
        results=await e.search(query)
        report.update(authenticated_request_succeeded=True,result_count=len(results),results=results)
        if results:
            data,metadata=await public_get(results[0]['url'])
            report['first_result_fetch']={'bytes':len(data),'metadata':metadata}
        report['passed']=bool(results)
    except Exception as ex:
        report.update(passed=False,error_type=type(ex).__name__,error=str(ex))
    (ROOT/'docs/live-search.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k!='results'}),flush=True)
asyncio.run(main())
