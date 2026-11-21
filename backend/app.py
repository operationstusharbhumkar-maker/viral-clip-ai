from pathlib import Path
import sqlite3, hashlib, secrets, threading, uuid, traceback
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Header, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.services.youtube import download_video
from backend.services.transcript import transcribe
from backend.services.highlights import find_highlights
from backend.services.video import create_clip

BASE=Path(__file__).resolve().parent
DB=BASE/'app.db'; DOWNLOADS=BASE/'downloads'; OUTPUT=BASE/'output'; FRONTEND=BASE.parent/'frontend'
for p in (DOWNLOADS,OUTPUT): p.mkdir(exist_ok=True)
app=FastAPI(title='Viral Clip AI')
app.add_middleware(CORSMiddleware,allow_origins=['*'],allow_credentials=True,allow_methods=['*'],allow_headers=['*'])
app.mount('/output',StaticFiles(directory=str(OUTPUT)),name='output')

def db():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c

def init_db():
    c=db(); c.executescript('''CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT,email TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,name TEXT,plan TEXT DEFAULT 'free',clips_used INTEGER DEFAULT 0,created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,user_id INTEGER NOT NULL,status TEXT NOT NULL,progress INTEGER DEFAULT 0,message TEXT,result_json TEXT,created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS clips(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,job_id TEXT NOT NULL,title TEXT,score REAL,start REAL,end REAL,video_url TEXT,caption TEXT,thumbnail_text TEXT,created_at TEXT NOT NULL);'''); c.commit(); c.close()
init_db()

def now(): return datetime.now(timezone.utc).isoformat()
def ph(p): return hashlib.sha256(p.encode()).hexdigest()
def user_from_token(token):
    if not token:return None
    c=db(); r=c.execute('SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=?',(token.replace('Bearer ',''),)).fetchone(); c.close(); return dict(r) if r else None

def auth(authorization):
    u=user_from_token(authorization or '')
    if not u: raise HTTPException(401,'Login required')
    return u
class AuthBody(BaseModel): email:str; password:str; name:str|None=None
class GenerateBody(BaseModel): url:str

@app.get('/api/health')
def health(): return {'ok':True}
@app.post('/api/register')
def register(b:AuthBody):
    if len(b.password)<6: raise HTTPException(400,'Password must be at least 6 characters.')
    c=db()
    try:
        cur=c.execute('INSERT INTO users(email,password_hash,name,created_at) VALUES(?,?,?,?)',(b.email.lower().strip(),ph(b.password),b.name or '',now())); c.commit(); uid=cur.lastrowid
    except sqlite3.IntegrityError: c.close(); raise HTTPException(409,'Email already registered.')
    token=secrets.token_urlsafe(32); c.execute('INSERT INTO sessions(token,user_id) VALUES(?,?)',(token,uid)); c.commit(); c.close(); return {'token':token}
@app.post('/api/login')
def login(b:AuthBody):
    c=db(); r=c.execute('SELECT * FROM users WHERE email=? AND password_hash=?',(b.email.lower().strip(),ph(b.password))).fetchone()
    if not r: c.close(); raise HTTPException(401,'Invalid email or password.')
    token=secrets.token_urlsafe(32); c.execute('INSERT INTO sessions(token,user_id) VALUES(?,?)',(token,r['id'])); c.commit(); c.close(); return {'token':token}
@app.post('/api/logout')
def logout(authorization:str|None=Header(default=None)):
    token=(authorization or '').replace('Bearer ',''); c=db(); c.execute('DELETE FROM sessions WHERE token=?',(token,)); c.commit(); c.close(); return {'ok':True}
@app.get('/api/me')
def me(authorization:str|None=Header(default=None)):
    u=auth(authorization); return {k:u[k] for k in ('id','email','name','plan','clips_used','created_at')}
@app.get('/api/clips')
def clips(authorization:str|None=Header(default=None)):
    u=auth(authorization); c=db(); rows=c.execute('SELECT * FROM clips WHERE user_id=? ORDER BY id DESC',(u['id'],)).fetchall(); c.close(); return [dict(r) for r in rows]
@app.get('/api/jobs/{job_id}')
def job(job_id:str,authorization:str|None=Header(default=None)):
    u=auth(authorization); c=db(); r=c.execute('SELECT * FROM jobs WHERE id=? AND user_id=?',(job_id,u['id'])).fetchone(); c.close()
    if not r: raise HTTPException(404,'Job not found')
    d=dict(r); import json; d['result']=json.loads(d.pop('result_json')) if d.get('result_json') else None; return d

def set_job(jid,**fields):
    c=db(); sets=[]; vals=[]
    for k,v in fields.items(): sets.append(f'{k}=?'); vals.append(v)
    vals.append(jid); c.execute(f'UPDATE jobs SET {",".join(sets)} WHERE id=?',vals); c.commit(); c.close()

def run_pipeline(jid,uid,url):
    work=DOWNLOADS/f'{uid}_{jid}'; out=OUTPUT/str(uid)/jid; work.mkdir(parents=True,exist_ok=True); out.mkdir(parents=True,exist_ok=True)
    try:
        set_job(jid,status='downloading',progress=10,message='Downloading video from YouTube…')
        video=download_video(url,work)
        set_job(jid,status='transcribing',progress=38,message='Transcribing audio with Whisper…')
        segments,_=transcribe(video,'base')
        set_job(jid,status='finding_highlights',progress=60,message='Finding the strongest moments…')
        highlights=find_highlights(segments,3,25,45)
        if not highlights: raise RuntimeError('No suitable highlights were found in this video.')
        set_job(jid,status='creating_clips',progress=72,message='Creating vertical 9:16 clips…')
        results=[]
        for i,h in enumerate(highlights,1):
            op=out/f'clip_{i}.mp4'; create_clip(video,h['start'],h['end'],op)
            results.append({'rank':i,'score':h['score'],'start':h['start'],'end':h['end'],'video_url':f'/output/{uid}/{jid}/clip_{i}.mp4','caption':h['caption'],'thumbnail_text':h['thumbnail_text'],'title':f"Viral Clip #{i}"})
            set_job(jid,progress=72+int(i*8),message=f'Created clip {i} of {len(highlights)}…')
        c=db(); c.execute('UPDATE users SET clips_used=clips_used+? WHERE id=?',(len(results),uid))
        for r in results:
            c.execute('INSERT INTO clips(user_id,job_id,title,score,start,end,video_url,caption,thumbnail_text,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(uid,jid,r['title'],r['score'],r['start'],r['end'],r['video_url'],r['caption'],r['thumbnail_text'],now()))
        c.commit(); c.close()
        import json; set_job(jid,status='completed',progress=100,message='Completed ✓',result_json=json.dumps(results))
    except Exception as e:
        traceback.print_exc(); set_job(jid,status='failed',progress=100,message=str(e))

@app.post('/api/generate')
def generate(b:GenerateBody,background_tasks:BackgroundTasks,authorization:str|None=Header(default=None)):
    u=auth(authorization)
    if not b.url.strip().startswith(('http://','https://')): raise HTTPException(400,'Enter a valid YouTube URL.')
    # Free plan means the first 3 generated clips total. A 3-clip generation consumes all 3.
    if u['plan']=='free' and u['clips_used']>=3: raise HTTPException(402,'FREE_LIMIT_REACHED')
    jid=uuid.uuid4().hex
    c=db(); c.execute('INSERT INTO jobs(id,user_id,status,progress,message,created_at) VALUES(?,?,?,?,?,?)',(jid,u['id'],'queued',0,'Waiting to start…',now())); c.commit(); c.close()
    background_tasks.add_task(run_pipeline,jid,u['id'],b.url.strip())
    return {'job_id':jid}

# Keep this LAST so /api/* routes are not shadowed by StaticFiles.
app.mount('/',StaticFiles(directory=str(FRONTEND),html=True),name='frontend')
