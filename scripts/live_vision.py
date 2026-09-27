import asyncio,base64,io,json,sys,time
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from debate_lab.provider import Ollama
from debate_lab.domain import EvidenceOutput
async def main():
    im=Image.new('RGB',(500,240),'white'); draw=ImageDraw.Draw(im)
    draw.rectangle((20,20,180,180),fill='red'); draw.text((220,70),'42',fill='black',font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',60))
    b=io.BytesIO();im.save(b,format='PNG');p=Ollama();start=time.monotonic();report={}
    async def noop(*args): pass
    try:
        result=await p.generate('gemma4:31b-mlx',[{'role':'system','content':'Describe the image accurately using JSON with summary, uncertainty (list), blocking_question (string). No markdown.'},{'role':'user','content':'What color is the square and what number is shown?'}],EvidenceOutput.model_json_schema(),{'num_ctx':4096,'num_predict':1024,'temperature':0},noop,noop,[base64.b64encode(b.getvalue()).decode()])
        validated=EvidenceOutput.model_validate(result);report={'result':validated.model_dump(),'passed_color_and_number':'red' in validated.summary.lower() and '42' in validated.summary}
    except Exception as e: report={'error':str(e)}
    report['elapsed_seconds']=round(time.monotonic()-start,2);(Path(__file__).resolve().parents[1]/'docs/live-vision.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
asyncio.run(main())
