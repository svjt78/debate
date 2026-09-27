import asyncio,json,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from debate_lab.evidence import public_get
async def main():
    start=time.monotonic()
    try:
        data,metadata=await public_get('https://example.com')
        report={'passed':b'Example Domain' in data,'bytes':len(data),'metadata':metadata}
    except Exception as e: report={'passed':False,'error':str(e)}
    report['elapsed_seconds']=round(time.monotonic()-start,2)
    (Path(__file__).resolve().parents[1]/'docs/live-url.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
asyncio.run(main())
