"""Auditable request sizing and per-runtime calibration profiles."""
import hashlib,json,math
TIERS=(16384,24576,32768,65536,131072)
def encoded(value): return json.dumps(value,ensure_ascii=False,separators=(',',':'))
def fingerprint(value): return hashlib.sha256(encoded(value).encode()).hexdigest()
def profile_key(pinned,runtime): return fingerprint({'model':pinned['model'],'digest':pinned['digest'],'endpoint':pinned['endpoint'],'runtime':runtime})
def estimate(messages,schema,profile=None):
    wire='\n'.join(m['content'] for m in messages)+'\n'+encoded(schema)
    size=len(wire.encode())
    # Calibration is for text requests only. Non-ASCII inputs retain the byte bound.
    ascii_size=sum(ord(ch)<128 for ch in wire)
    usable=profile and ascii_size>=size*.9 and profile.get('bytes_to_tokens') and size<=profile.get('max_bytes',0)
    return math.ceil(ascii_size*profile['bytes_to_tokens']+(size-ascii_size) if usable else size)+512, 'calibrated estimate' if usable else 'conservative byte bound'
def choose_context(settings,required,profile):
    base=settings['context_tokens']; maximum=settings.get('max_context_tokens',32768)
    baseline=min(base,16384) if settings.get('execution_policy')=='completion' else base
    candidates=[baseline]+[n for n in (profile or {}).get('tested_contexts',[]) if baseline<n<=maximum]
    return next((n for n in sorted(set(candidates)) if required<=n),None)
