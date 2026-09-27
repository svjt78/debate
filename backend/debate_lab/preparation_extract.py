"""One restartable extraction unit per process. Originals are never rewritten."""
import io, json, os, sys, zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
from PIL import Image

NS={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
def batch(path,kind,cursor):
    passages=[]; images=[]; warnings=[]
    def add(text,**locator):
        if text.strip(): passages.append({'text':text,'locator':locator})
    def visual(data,**locator):
        name=f'batch-{cursor}-view-{len(images)}.png'
        try:
            im=Image.open(io.BytesIO(data)) if isinstance(data,bytes) else data
            im.thumbnail((1400,1400)); im.convert('RGB').save(path.parent/name)
            images.append({'path':name,'locator':locator})
        except Exception as e: warnings.append(f'Unreadable visual {locator}: {type(e).__name__}. Provide a PNG or PDF rendering.')
    if kind=='pdf':
        import pypdfium2 as pdfium
        doc=pdfium.PdfDocument(path); total=len(doc)
        limit=int(os.getenv('DEBATE_MAX_PDF_PAGES','100'))
        if total>limit: raise ValueError(f'PDF has {total} pages; configured limit is {limit}. Raise DEBATE_MAX_PDF_PAGES or split the file; no pages were silently omitted.')
        if cursor<total:
            page=doc[cursor]; add(page.get_textpage().get_text_range(),page=cursor+1)
            visual(page.render(scale=1.5).to_pil(),page=cursor+1)
        warnings.append('Page text and rendered visuals are processed separately; visual descriptions are derived, not verified quotations.')
    elif kind=='docx':
        with zipfile.ZipFile(path) as doc:
            if sum(i.file_size for i in doc.infolist())>int(os.getenv('DEBATE_MAX_DOCX_EXPANDED_MIB','100'))*1024**2:
                raise ValueError('DOCX expanded contents exceed the configured safety limit. Split the document.')
            members=doc.namelist()
            parts=['word/document.xml']+sorted(n for n in members if n.startswith(('word/header','word/footer','word/footnotes','word/endnotes')) and n.endswith('.xml'))
            units=[]
            for part in parts:
                tree=ET.fromstring(doc.read(part)); body=tree.find('w:body',NS) if part=='word/document.xml' else tree
                for index,node in enumerate(list(body) if body is not None else []): units.append(('text',part,index,node))
            units += [('image',name,0,None) for name in members if name.startswith('word/media/')]
            units += [('chart',name,0,None) for name in members if name.startswith('word/charts/chart') and name.endswith('.xml')]
            total=len(units)
            if cursor<total:
                type_,part,index,node=units[cursor]
                if type_=='text':
                    if node.tag.endswith('}tbl'):
                        for rownum,row in enumerate(node.findall('w:tr',NS),1):
                            add(' | '.join(' '.join(t.text or '' for t in cell.iter() if t.tag.endswith('}t')) for cell in row.findall('w:tc',NS)),part=part,table=index+1,row=rownum)
                    else: add(' '.join(t.text or '' for t in node.iter() if t.tag.endswith('}t')),part=part,paragraph=index+1)
                elif type_=='image': visual(doc.read(part),part=part,image=cursor+1)
                else:
                    tree=ET.fromstring(doc.read(part))
                    add('Chart labels and cached values: '+' | '.join(t.text for t in tree.iter() if t.text and t.tag.split('}')[-1] in {'v','t'}),part=part,chart=cursor+1)
                    warnings.append(f'{part}: chart data extracted; native chart layout is not rendered. Supply a PDF or screenshot for visual interpretation.')
            if cursor==0:
                warnings.append('DOCX locators use XML parts, paragraphs, tables and images, not rendered page numbers. Floating shapes and native chart layout may require a PDF rendering.')
    elif kind in {'png','jpg','jpeg','webp'}:
        total=1
        if cursor==0: visual(path.read_bytes(),image=1)
    elif kind in {'text','txt','md','url'}:
        if kind=='url':
            from bs4 import BeautifulSoup
            soup=BeautifulSoup(path.read_bytes(),'html.parser')
            for node in soup(['script','style','nav','noscript','iframe','form']): node.decompose()
            lines=soup.get_text('\n',strip=True).splitlines()
        else: lines=path.read_text(encoding='utf-8-sig').splitlines()
        total=max(1,(len(lines)+99)//100)
        for index,line in enumerate(lines[cursor*100:(cursor+1)*100],cursor*100+1): add(line,**({'passage':index} if kind=='url' else {'line':index}))
        if kind=='url': warnings.append('Public webpage text only. Images, scripts, embedded media and login-protected content are not interpreted.')
    else: raise ValueError('Audio, video and hosted-video interpretation are deferred. Supply text, an image, Markdown, DOCX or PDF.')
    return dict(passages=passages,images=images,uncertainty=warnings,next_cursor=cursor+1,total=total,done=cursor+1>=total)

if __name__=='__main__':
    path=Path(sys.argv[1]); result=batch(path,sys.argv[2],int(sys.argv[4])); output=Path(sys.argv[3]); temp=output.with_suffix('.tmp'); temp.write_text(json.dumps(result)); temp.replace(output)
