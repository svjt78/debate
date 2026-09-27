"""Store the hosted-search credential locally without echoing or logging it."""
import getpass, os, tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]/'.data'/'secrets'
root.mkdir(parents=True,exist_ok=True,mode=0o700)
os.chmod(root,0o700)
key=getpass.getpass('Ollama hosted-search API key (hidden): ').strip()
if not key or any(c.isspace() for c in key): raise SystemExit('Key must be nonempty and contain no whitespace.')
fd,name=tempfile.mkstemp(dir=root,prefix='.key-')
try:
    with os.fdopen(fd,'w') as f:
        os.fchmod(f.fileno(),0o600);f.write(key+'\n');f.flush();os.fsync(f.fileno())
    os.replace(name,root/'ollama-search-key')
finally:
    if os.path.exists(name): os.unlink(name)
print('Hosted-search credential saved with owner-only permissions. Value was not printed.')
