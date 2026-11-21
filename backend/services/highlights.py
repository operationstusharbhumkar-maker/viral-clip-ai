import re

HOOK_WORDS = {'wow','crazy','insane','secret','never','best','worst','why','how','actually','truth','mistake','amazing','shocking','finally','impossible','first','last','love','hate','remember'}

def _score(text: str) -> float:
    words = re.findall(r"[A-Za-z']+", text.lower())
    if not words: return 0.0
    hook = sum(w in HOOK_WORDS for w in words)
    excitement = sum(text.count(c) for c in '!?')
    density = min(len(words) / 45, 1.0)
    return min(100.0, 35 + hook * 7 + excitement * 2 + density * 25)

def find_highlights(segments, count=3, min_len=25, max_len=45):
    if not segments: return []
    candidates=[]
    n=len(segments)
    for i,s in enumerate(segments):
        start=max(0, float(s.get('start',0)) - 4)
        text_parts=[]; end=start
        for j in range(i,n):
            sj=segments[j]; end=float(sj.get('end', end)); text_parts.append(sj.get('text','').strip())
            dur=end-start
            if dur >= min_len:
                if dur > max_len: break
                text=' '.join(text_parts).strip()
                # Prefer moments whose strongest line is near the end of the window.
                payoff=_score(text_parts[-1] if text_parts else text)
                total=min(100, _score(text)*0.65 + payoff*0.35)
                candidates.append({'start':start,'end':end,'text':text,'score':round(total,1)})
                if dur >= max_len-2: break
    candidates.sort(key=lambda x:x['score'], reverse=True)
    selected=[]
    for c in candidates:
        overlap=False
        for s in selected:
            if max(c['start'],s['start']) < min(c['end'],s['end']): overlap=True; break
        if not overlap:
            selected.append(c)
            if len(selected)>=count: break
    selected.sort(key=lambda x:x['start'])
    for idx,c in enumerate(selected,1):
        c['rank']=idx
        words=re.findall(r"[A-Za-z0-9']+",c['text'])
        c['caption']=(' '.join(words[:12]) + ('…' if len(words)>12 else '')).strip()
        c['thumbnail_text']=(' '.join(words[-5:]) if words else 'WATCH THIS')[:42]
    return selected
