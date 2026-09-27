"""Runs in an app-owned process so Pause can stop CPU extraction and descendants."""
import json, os, re, shutil, subprocess, sys
from pathlib import Path
from PIL import Image

def extract(path,kind):
    passages=[]; warnings=[]; images=[]; transcription=None
    def add(text,**locator): passages.append(dict(text=text,locator=locator))
    def image(file,**locator):
        im=Image.open(file); im.thumbnail((1400,1400)); dest=path.parent/f'view-{len(images)}.png'; im.convert('RGB').save(dest)
        images.append(dict(path=dest.name,locator=locator))
    if kind in {'text','txt','md'}:
        text=path.read_text(encoding='utf-8-sig')
        for i,line in enumerate(text.splitlines(),1):
            if line.strip(): add(line,line=i)
    elif kind=='url':
        from bs4 import BeautifulSoup
        soup=BeautifulSoup(path.read_bytes(),'html.parser')
        for t in soup(['script','style','nav','noscript','iframe','form']): t.decompose()
        for i,t in enumerate(soup.get_text('\n',strip=True).splitlines(),1):
            if t.strip(): add(t,passage=i)
    elif kind=='pdf':
        import pypdfium2 as pdfium
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            if len(pdf.pages)>int(os.getenv('DEBATE_MAX_PDF_PAGES','100')): raise ValueError('PDF exceeds configured page limit.')
            render=None
            for i,page in enumerate(pdf.pages):
                text=page.extract_text() or ''
                if len(text.strip())>=30: add(text,page=i+1)
                else:
                    if render is None: render=pdfium.PdfDocument(path)
                    file=path.parent/f'page-{i+1}.png'; render[i].render(scale=1.5).to_pil().save(file); image(file,page=i+1)
                    warnings.append(f'Page {i+1} requires vision; descriptions are derived, not verbatim OCR.')
    elif kind in {'png','jpg','jpeg','webp'}: image(path,image=1)
    elif kind in {'wav','mp3','m4a','ogg','flac','mp4','mov','webm'}:
        ffmpeg=os.getenv('DEBATE_FFMPEG') or shutil.which('ffmpeg')
        if not ffmpeg:
            try:
                import imageio_ffmpeg
                ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
            except ImportError: raise ValueError('FFmpeg is unavailable. Configure DEBATE_FFMPEG or install the optional media dependency.')
        probe=subprocess.run([ffmpeg,'-i',str(path)],capture_output=True,text=True,timeout=15)
        m=re.search(r'Duration: (\d+):(\d+):(\d+(?:\.\d+)?)',probe.stderr)
        if not m: raise ValueError('Media duration could not be established.')
        h,mi,se=map(float,m.groups()); duration=h*3600+mi*60+se
        if duration>int(os.getenv('DEBATE_MAX_MEDIA_SECONDS','600')): raise ValueError('Media exceeds configured duration limit.')
        model=os.getenv('DEBATE_WHISPER_MODEL')
        if not model or not Path(model).is_dir(): raise ValueError('Local transcription model unavailable. Set DEBATE_WHISPER_MODEL to an explicitly installed MLX Whisper directory. No automatic downloads are allowed.')
        wav=path.parent/'audio.wav'
        subprocess.run([ffmpeg,'-nostdin','-v','error','-i',str(path),'-vn','-ar','16000','-ac','1','-y',str(wav)],check=True,timeout=90)
        import mlx_whisper
        import wave, numpy as np
        with wave.open(str(wav)) as audio:
            samples=np.frombuffer(audio.readframes(audio.getnframes()),dtype=np.int16).astype(np.float32)/32768.0
        result=mlx_whisper.transcribe(samples,path_or_hf_repo=str(Path(model).resolve()),word_timestamps=True)
        import hashlib, importlib.metadata
        weights=Path(model)/'weights.safetensors'
        if not weights.exists(): weights=Path(model)/'weights.npz'
        with weights.open('rb') as f: digest=hashlib.file_digest(f,'sha256').hexdigest()
        transcription={'engine':'mlx-whisper','version':importlib.metadata.version('mlx-whisper'),'model_path':str(Path(model).resolve()),'weights_sha256':digest,'network_mode':'offline','speaker_labels':'not inferred'}
        for seg in result.get('segments',[]):
            add(seg['text'],start=seg['start'],end=seg['end'])
            if seg.get('avg_logprob',0)<-1 or seg.get('no_speech_prob',0)>.6: warnings.append(f"Low-confidence speech at {seg['start']:.1f}–{seg['end']:.1f}s; verify against the original audio.")
        warnings.append('Automatic local speech transcription; speaker identity is not verified. Low confidence or unintelligible speech may be mistranscribed.')
        if kind in {'mp4','mov','webm'}:
            subprocess.run([ffmpeg,'-nostdin','-v','error','-i',str(path),'-vf',r'select=isnan(prev_selected_t)+gte(t-prev_selected_t\,30),scale=960:-1','-fps_mode','vfr','-y',str(path.parent/'frame-%04d.jpg')],check=True,timeout=90)
            for i,file in enumerate(sorted(path.parent.glob('frame-*.jpg'))): image(file,start=i*30)
            warnings.append('Video sampled every 30 seconds. Events between frames are not visually inspected; timestamps are approximate sampling positions.')
    else: raise ValueError('Unsupported source type.')
    if len(images)>30: raise ValueError('Source needs over 30 visual pages/frames; split it into smaller files.')
    return dict(passages=passages,images=images,uncertainty=warnings,transcription=transcription)
if __name__=='__main__':
    path=Path(sys.argv[1]); result=extract(path,sys.argv[2]); Path(sys.argv[3]).write_text(json.dumps(result))
