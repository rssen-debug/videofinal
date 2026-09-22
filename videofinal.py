#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VIDEOFINAL 2026 — single-file autonomous creator studio.

Interactive: max 3 selections: MODE -> NICHE -> QUALITY.
Then the orchestrator owns the pipeline: scout -> research -> story -> source hunt
-> transcript/ASR -> moment selection -> script -> TTS -> timeline -> render -> mix -> QC.

Real footage only for source shots. Original source audio is preserved on source shots.
Source captions follow the actual speaker via VTT or Whisper word timestamps.
Documentary and Shorts share the same acquisition/audio/QC core but use different policies.
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import hashlib
import html
import json
import math
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

try:
    import numpy as np
    from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageFilter
except Exception as exc:
    raise SystemExit(f"Core Python packages missing: {exc}. Run python -m pip install -r requirements.txt")

try:
    import cv2
except Exception:
    cv2 = None

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / '.cache'
PROJECTS = ROOT / 'projects'
ASSET_CLIPS = ROOT / 'assets' / 'clips'
OUTPUTS = ROOT / 'outputs'
for p in (CACHE, PROJECTS, ASSET_CLIPS, OUTPUTS):
    p.mkdir(parents=True, exist_ok=True)

FPS = 30
SR = 44100
RES = {
    '320p': {'short': (320, 568), 'doc': (568, 320)},
    '720p': {'short': (720, 1280), 'doc': (1280, 720)},
    '1080p': {'short': (1080, 1920), 'doc': (1920, 1080)},
}
NICHES = {
    'streamers': ['streamer drama','Kai Cenat','Twitch streamer','Kick streamer','creator controversy'],
    'gaming': ['gaming controversy','esports drama','game controversy','gaming creator'],
    'internet': ['internet controversy','viral creator story','creator news','internet mystery'],
    'tech': ['AI news','tech controversy','startup story','technology creator'],
    'business': ['company controversy','CEO story','startup news','business drama'],
    'sports': ['sports controversy','boxing drama','football controversy','athlete story'],
    'science': ['space news','science breakthrough','NASA story','weird science'],
    'history': ['history mystery','historical event','history explained','forgotten history'],
    'movies_music': ['movie controversy','music industry story','artist controversy','film news'],
    'weird': ['weird news','strange story','unexpected discovery','unusual event'],
}
VOICE = os.environ.get('VIDEOFINAL_VOICE','en-GB-RyanNeural')
LLM_MODEL = os.environ.get('CEREBRAS_MODEL','gpt-oss-120b')
_ASR = None

# ---------------------------------------------------------------------------
# BOOTSTRAP

def has_module(name: str) -> bool:
    try:
        __import__(name); return True
    except Exception:
        return False

def ensure_dependencies() -> None:
    packages = {
        'requests':'requests>=2.31',
        'yt_dlp':'yt-dlp>=2026.1.1',
        'edge_tts':'edge-tts>=6.1.9',
        'faster_whisper':'faster-whisper>=1.0',
    }
    missing = [pkg for mod,pkg in packages.items() if not has_module(mod)]
    if missing:
        print('[BOOTSTRAP] Installing:', ', '.join(missing))
        subprocess.run([sys.executable,'-m','pip','install','--disable-pip-version-check',*missing],check=True,timeout=1800)

def exe(name: str) -> str:
    p = shutil.which(name)
    if not p: raise RuntimeError(f'{name} saknas i PATH.')
    return p

def run(cmd: list[str], timeout=900, check=True, cwd: Optional[Path]=None):
    p = subprocess.run(cmd,capture_output=True,text=True,timeout=timeout,cwd=str(cwd) if cwd else None)
    if check and p.returncode:
        raise RuntimeError(f"command failed ({p.returncode}): {' '.join(cmd[:10])}\n{(p.stderr or p.stdout)[-3500:]}")
    return p

# ---------------------------------------------------------------------------
# LLM ROUTER — Cerebras first

def llm_provider() -> str:
    if os.environ.get('CEREBRAS_API_KEY','').strip(): return 'cerebras'
    if os.environ.get('OPENAI_API_KEY','').strip(): return 'openai'
    if os.environ.get('GROQ_API_KEY','').strip(): return 'groq'
    if os.environ.get('SUNNY_LLM_KEY','').strip() and os.environ.get('SUNNY_LLM_URL','').strip(): return 'custom'
    return 'none'

def llm_model() -> str:
    if llm_provider() == 'cerebras': return os.environ.get('CEREBRAS_MODEL',LLM_MODEL)
    return os.environ.get('SUNNY_LLM_MODEL','gpt-4o-mini')

def llm_url() -> str:
    p=llm_provider()
    if p=='cerebras': return 'https://api.cerebras.ai/v1/chat/completions'
    if p=='groq': return 'https://api.groq.com/openai/v1/chat/completions'
    if p=='custom': return os.environ['SUNNY_LLM_URL'].rstrip('/')+'/chat/completions'
    return (os.environ.get('OPENAI_BASE_URL') or 'https://api.openai.com/v1').rstrip('/')+'/chat/completions'

def llm_key() -> str:
    p=llm_provider()
    return {'cerebras':os.environ.get('CEREBRAS_API_KEY',''),'openai':os.environ.get('OPENAI_API_KEY',''),'groq':os.environ.get('GROQ_API_KEY',''),'custom':os.environ.get('SUNNY_LLM_KEY','')}.get(p,'').strip()

def llm_status() -> dict[str,Any]:
    p=llm_provider(); return {'provider':p,'model':llm_model() if p!='none' else None,'configured':p!='none'}

def llm_text(prompt: str, system='You are a senior showrunner.', max_tokens=2500) -> str:
    key=llm_key()
    if not key: raise RuntimeError('no LLM provider')
    import requests
    body={'model':llm_model(),'messages':[{'role':'system','content':system},{'role':'user','content':prompt}],'max_completion_tokens':max_tokens,'temperature':0.2}
    if llm_provider()=='cerebras': body['reasoning_effort']=os.environ.get('CEREBRAS_REASONING_EFFORT','high')
    r=requests.post(llm_url(),json=body,headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},timeout=180)
    if r.status_code!=200: raise RuntimeError(f'{llm_provider()} HTTP {r.status_code}: {r.text[:800]}')
    return r.json()['choices'][0]['message']['content']

def parse_json(s: str) -> Any:
    s=(s or '').strip()
    if s.startswith('```'): s=re.sub(r'^```[A-Za-z0-9_-]*','',s).strip(); s=re.sub(r'```$','',s).strip()
    try: return json.loads(s)
    except Exception: pass
    for op,cl in [('{','}'),('[',']')]:
        st=s.find(op)
        if st<0: continue
        depth=0; ins=False; esc=False
        for i,ch in enumerate(s[st:],st):
            if esc: esc=False; continue
            if ch=='\\': esc=True; continue
            if ch=='"': ins=not ins; continue
            if ins: continue
            if ch==op: depth+=1
            elif ch==cl:
                depth-=1
                if depth==0:
                    try:return json.loads(s[st:i+1])
                    except Exception: break
    return None

def llm_json(prompt: str, system='Return JSON only.', max_tokens=2500):
    obj=parse_json(llm_text(prompt,system,max_tokens))
    if obj is None: raise RuntimeError('LLM did not return JSON')
    return obj

def test_llm():
    return {'provider':llm_provider(),'model':llm_model(),'reply':llm_text('Reply exactly VIDEOFINAL_LLM_OK.', 'Return only the requested token.',40).strip()}

# ---------------------------------------------------------------------------
# DISCOVERY / SCORING

def clean(s:str)->str:return re.sub(r'\s+',' ',(s or '').strip())
def slug(s:str)->str:return re.sub(r'[^a-z0-9]+','-',(s or 'project').lower()).strip('-')[:90] or 'project'

def news(q:str, n=10):
    url='https://news.google.com/rss/search?'+urllib.parse.urlencode({'q':q,'hl':'en-US','gl':'US','ceid':'US:en'})
    try: raw=urllib.request.urlopen(url,timeout=20).read().decode('utf-8','ignore')
    except Exception:return []
    out=[]
    for m in re.finditer(r'<item>(.*?)</item>',raw,re.S):
        b=m.group(1); tm=re.search(r'<title>(.*?)</title>',b,re.S); lm=re.search(r'<link>(.*?)</link>',b,re.S)
        title=html.unescape(tm.group(1).strip()) if tm else ''; link=lm.group(1).strip() if lm else ''
        if title: out.append({'title':title,'url':link,'signal':'news'})
        if len(out)>=n:break
    return out

def yt_search(q:str,n=12):
    for client in ('android','web'):
        p=run([sys.executable,'-m','yt_dlp','--flat-playlist','--dump-single-json','--skip-download','--extractor-args',f'youtube:player_client={client}',f'ytsearch{max(n*2,10)}:{q}'],timeout=180,check=False)
        if p.returncode: continue
        try:o=json.loads(p.stdout)
        except Exception:continue
        rows=[]
        for e in o.get('entries',[]) if isinstance(o,dict) else []:
            if not isinstance(e,dict):continue
            vid=e.get('id'); u=e.get('webpage_url') or e.get('url') or (f'https://www.youtube.com/watch?v={vid}' if vid else '')
            if not u:continue
            rows.append({'id':vid or '','url':u,'title':clean(e.get('title','')),'uploader':clean(e.get('uploader') or e.get('channel') or ''),'channel_url':e.get('channel_url') or '','client':client})
            if len(rows)>=n:return rows
        if rows:return rows
    return []

def score_story(title:str, mode:str)->dict[str,Any]:
    t=title.lower(); hook=5+sum(k in t for k in ('why','how','controversy','vs','banned','quit','return','secret','exposed'))
    fresh=6+sum(k in t for k in ('today','latest','breaking','new','announced','update','returns'))
    visual=6+sum(k in t for k in ('stream','live','fight','game','interview','trailer','record','launch'))
    depth=5+sum(k in t for k in ('lawsuit','rise','fall','mystery','scandal','empire','history'))
    raw=min(hook,10)*.30+min(fresh,10)*.24+min(visual,10)*.24+min(depth,10)*.22
    return {'score':round(raw*10,1),'score_10':round(raw,1),'hook':min(hook,10),'freshness':min(fresh,10),'visual':min(visual,10),'depth':min(depth,10)}

def niche_candidates(niche:str,mode:str,limit=10):
    seeds=NICHES.get(niche,NICHES['internet']); rows=[]
    for q in seeds:
        rows += news(q,6); rows += yt_search(q,6)
    if niche=='streamers':
        rows += news('streamer drama',10)
    seen=set(); unique=[]
    for r in rows:
        k=re.sub(r'\W+','',r.get('title','').lower())[:160]
        if len(k)<12 or k in seen:continue
        seen.add(k); r.update(score_story(r['title'],mode)); r['niche']=niche; unique.append(r)
    unique.sort(key=lambda x:x['score'],reverse=True)
    if llm_provider()!='none' and unique:
        try:
            sample=[{'i':i+1,'title':r['title'],'signal':r.get('signal'),'url':r.get('url')} for i,r in enumerate(unique[:24])]
            obj=llm_json(f'Rank production opportunities for a {mode} in niche {niche}. Reject generic listicles and vague updates. Prefer a concrete event, strong visual evidence, a turn, and research depth. Give 0-100 scores. Return {{"items":[{{"i":1,"score":92,"reason":"..."}}]}}.\n'+json.dumps(sample,ensure_ascii=False),max_tokens=2200)
            by={int(x.get('i')):x for x in obj.get('items',[]) if isinstance(x,dict)}
            for i,r in enumerate(unique[:24],1):
                if i in by:r['score']=max(0,min(100,float(by[i].get('score',r['score']))));r['reason']=clean(str(by[i].get('reason','')))
            unique[:24]=sorted(unique[:24],key=lambda x:x['score'],reverse=True)
        except Exception:pass
    for r in unique:r['score_10']=round(r['score']/10,1)
    return unique[:limit]

# ---------------------------------------------------------------------------
# STATE / RESEARCH

@dataclass
class Shot:
    kind:str
    dur:float
    clip:Optional[Path]=None
    cut:float=0.0
    text:str=''
    source_words:Optional[list[dict[str,Any]]]=None
    start:float=0.0

def project_for(topic,mode,res):
    root=PROJECTS/slug(topic);root.mkdir(parents=True,exist_ok=True)
    state={'schema':'videofinal/2026-autopilot','topic':topic,'mode':mode,'resolution':res,'status':'running','events':[],'errors':[],'stages':[],'artifacts':{}}
    (root/'state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
    return root,state

def stage(root,state,name,**data):
    state['stage']=name;state['stages'].append({'name':name,'at':dt.datetime.now(dt.timezone.utc).isoformat(),**data})
    (root/'state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')

def research(topic:str)->dict[str,Any]:
    rows=news(topic,12)
    entities=[]; queries=[topic]
    if llm_provider()!='none':
        try:
            obj=llm_json('Extract entities and follow-up queries for this story. Do not invent facts. Return {"entities":[],"queries":[]}.\n'+topic+'\n'+json.dumps(rows,ensure_ascii=False),max_tokens=800)
            entities=[clean(x) for x in obj.get('entities',[]) if clean(str(x))];queries += [clean(x) for x in obj.get('queries',[]) if clean(str(x))][:5]
        except Exception:pass
    claims=[{'text':r['title'],'source_url':r['url'],'kind':'reported'} for r in rows]
    for q in queries[1:]:
        for r in news(q,6):
            claims.append({'text':r['title'],'source_url':r['url'],'kind':'reported'})
    return {'claims':claims[:60],'entities':entities,'queries':queries[:6],'news':rows}

# ---------------------------------------------------------------------------
# SOURCE TRANSCRIPTS / ASR / MOMENTS

def parse_vtt(path:Path):
    if not path.exists():return []
    t=path.read_text(encoding='utf-8',errors='ignore');out=[]
    rx=re.compile(r'(\d{2}:\d{2}:\d{2}\.\d{3})\s+-->\s+(\d{2}:\d{2}:\d{2}\.\d{3}).*?\n(.*?)(?=\n\n|\Z)',re.S)
    def ts(x):
        h,m,s=x.split(':');return int(h)*3600+int(m)*60+float(s)
    for m in rx.finditer(t):
        body=clean(re.sub(r'<[^>]+>','',m.group(3)).replace('\n',' '))
        body=re.sub(r'\b(?:music|applause|laughs?)\b','',body,flags=re.I).strip()
        if body:out.append({'start':ts(m.group(1)),'end':ts(m.group(2)),'text':body})
    return out

def whisper_words(path:Path):
    global _ASR
    try:
        from faster_whisper import WhisperModel
    except Exception:return []
    try:
        if _ASR is None:_ASR=WhisperModel(os.environ.get('VIDEOFINAL_ASR_MODEL','base'),device=os.environ.get('VIDEOFINAL_ASR_DEVICE','cpu'),compute_type=os.environ.get('VIDEOFINAL_ASR_COMPUTE','int8'))
        segs,_=_ASR.transcribe(str(path),word_timestamps=True)
        return [{'text':clean(w.word),'start':float(w.start),'end':float(w.end)} for seg in segs for w in (seg.words or []) if clean(w.word)]
    except Exception:return []

def source_subs(url:str, tag:str):
    d=CACHE/'subs';d.mkdir(parents=True,exist_ok=True);pref=d/tag
    for client in ('android','web'):
        run([sys.executable,'-m','yt_dlp','--skip-download','--write-auto-subs','--write-subs','--sub-langs','en.*,en','--sub-format','vtt','--extractor-args',f'youtube:player_client={client}','-o',str(pref)+'.%(ext)s',url],timeout=240,check=False)
        v=list(d.glob(tag+'*.vtt'))
        for p in v:
            cues=parse_vtt(p)
            if cues:return cues
    return []

def source_info(url:str):
    for client in ('android','web'):
        p=run([sys.executable,'-m','yt_dlp','--dump-single-json','--skip-download','--extractor-args',f'youtube:player_client={client}',url],timeout=180,check=False)
        if p.returncode:continue
        try:o=json.loads(p.stdout);return {'duration':float(o.get('duration') or 0),'title':o.get('title',''),'uploader':o.get('uploader') or o.get('channel',''),'id':o.get('id','')} 
        except Exception:continue
    return {'duration':0}

def vtt_moments(cues,wanted=3):
    windows=[]
    for i,c in enumerate(cues):
        start=c['start'];parts=[];end=start
        for j in range(i,min(len(cues),i+10)):
            if cues[j]['start']-start>8:break
            parts.append(cues[j]['text']);end=cues[j]['end'];dur=end-start
            text=clean(' '.join(parts))
            if 4<=dur<=8 and len(text.split())>=6:windows.append({'cut':max(0,start-.18),'dur':min(8,end-max(0,start-.18)+.32),'quote':text})
    seen=set();out=[]
    for w in sorted(windows,key=lambda x:len(x['quote']),reverse=True):
        k=re.sub(r'\W+','',w['quote'].lower())[:120]
        if k not in seen:seen.add(k);out.append(w)
    return out[:wanted]

def asr_moments(source,root,wanted=3):
    dur=float(source.get('duration') or 0)
    if dur<5 or not has_module('faster_whisper'):return []
    length=min(9,max(5.5,dur*.16));positions=[0,max(0,dur*.28-length/2),max(0,dur*.55-length/2),max(0,dur*.80-length/2)]
    out=[]
    for cut in sorted(set(round(max(0,min(float(x),max(0,dur-length))),2) for x in positions)):
        key=hashlib.sha1((source['url']+f'|{cut}').encode()).hexdigest()[:12];p=ASSET_CLIPS/f'probe_{key}.mp4'
        try:
            if not p.exists():download_segment(source['url'],cut,length,p)
            words=whisper_words(p)
            if not words:continue
            absw=[{'text':w['text'],'start':w['start']+cut,'end':w['end']+cut} for w in words]
            wins=[]
            for i,w in enumerate(absw):
                st=w['start'];buf=[];en=st
                for z in absw[i:i+45]:
                    if z['start']-st>8:break
                    buf.append(z);en=z['end'];d=en-st;t=clean(' '.join(a['text'] for a in buf))
                    if 4<=d<=8 and len(t.split())>=6:wins.append({'cut':max(0,st-.18),'dur':min(8,en-max(0,st-.18)+.32),'quote':t,'asr_words':absw})
            out+=sorted(wins,key=lambda x:len(x['quote'].split()),reverse=True)[:2]
        except Exception:pass
        if len(out)>=wanted:break
    return out[:wanted]

def choose_sources(topic,research,count=7):
    ents=research.get('entities',[]);queries=[topic]+ents[:3]+research.get('queries',[])[1:4]
    cand=[];seen=set()
    for q in queries:
        for r in yt_search(q,10):
            if r['url'] in seen:continue
            seen.add(r['url']);blob=(r['title']+' '+r['uploader']).lower();score=.30
            for e in ents:
                if e.lower() in blob:score+=.18
            if 'official' in blob or any(k in blob for k in ('tv','live','interview','podcast','channel')):score+=.08
            if any(k in blob for k in ('reaction','fan','edit','compilation','highlights','shorts')):score-=.20
            r['party_score']=round(max(0,min(.99,score)),3);cand.append(r)
    cand.sort(key=lambda x:x['party_score'],reverse=True)
    if llm_provider()!='none' and cand:
        try:
            sample=[{'i':i+1,'title':r['title'],'uploader':r['uploader'],'url':r['url'],'party_score':r['party_score']} for i,r in enumerate(cand[:35])]
            obj=llm_json('Select original/first-party audiovisual sources for this story. Prefer the speaker, creator, company, event, network, or original interview. Reject commentary/reuploads/fan edits. Return {"pick":[1,2,3,4,5,6,7]}.\n'+json.dumps(sample,ensure_ascii=False),max_tokens=1300)
            picks=[]
            for i in obj.get('pick',[])[:count]:
                try:picks.append(cand[int(i)-1])
                except Exception:pass
            if picks:cand=picks
        except Exception:pass
    return cand[:count]

def download_segment(url:str,cut:float,dur:float,out:Path):
    out.parent.mkdir(parents=True,exist_ok=True)
    base=[sys.executable,'-m','yt_dlp','--no-progress','--force-keyframes-at-cuts','--merge-output-format','mp4','-f','bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]/best','--download-sections',f'*{cut:.2f}-{cut+dur:.2f}','-o',str(out)]
    for client in ('android','web'):
        p=run(base[:-2]+['--extractor-args',f'youtube:player_client={client}']+base[-2:]+[url],timeout=700,check=False)
        if p.returncode==0 and out.exists():return out
        if out.exists():out.unlink()
    temp=out.with_suffix('.source.mp4')
    run([sys.executable,'-m','yt_dlp','--no-progress','--merge-output-format','mp4','--extractor-args','youtube:player_client=android','-f','bestvideo[height<=720]+bestaudio/best[height<=720]/best','-o',str(temp),url],timeout=1200)
    run([exe('ffmpeg'),'-y','-v','error','-ss',str(cut),'-t',str(dur),'-i',str(temp),'-vf','scale=-2:720,fps=30,setsar=1','-c:v','libx264','-crf','20','-pix_fmt','yuv420p','-c:a','aac','-b:a','128k',str(out)],timeout=1000)
    return out

# ---------------------------------------------------------------------------
# SCRIPTING / TTS

def tts(text:str,out:Path):
    import edge_tts
    async def go():await edge_tts.Communicate(text,VOICE).save(str(out))
    asyncio.run(go());return out

def audio_duration(path:Path)->float:
    p=run([exe('ffprobe'),'-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',str(path)],timeout=120)
    return float(p.stdout.strip() or 0)

def proportional_words(text,start,dur):
    ws=text.split();weights=[max(1,len(w)) for w in ws];tot=sum(weights) or 1;t=start;out=[]
    for i,w in enumerate(ws):
        d=dur*weights[i]/tot;out.append({'text':w,'start':t,'end':t+d});t+=d
    return out

def cap_groups(words,max_words=4,max_chars=24):
    out=[];buf=[]
    for w in words:
        cand=' '.join(x['text'] for x in buf+[w])
        if buf and (len(buf)>=max_words or len(cand)>max_chars or w['start']-buf[-1]['end']>.45):
            out.append({'start':buf[0]['start'],'end':buf[-1]['end'],'text':' '.join(x['text'] for x in buf)});buf=[]
        buf.append(w)
    if buf:out.append({'start':buf[0]['start'],'end':buf[-1]['end'],'text':' '.join(x['text'] for x in buf)})
    return out

def block_words(text,dur):return cap_groups(proportional_words(text,0,dur))

def build_script_short(topic,research,moments):
    if llm_provider()!='none':
        try:
            obj=llm_json('Write an original 45-59 second Short. Start with a real source moment, then concise context, another real source moment, consequence/payoff, and a specific question. Never invent quotes or unsupported claims. Return {"narration":["..."],"order":[1,2,3],"title":"..."}.\nTOPIC:'+topic+'\nRESEARCH:'+json.dumps(research,ensure_ascii=False)[:9000]+'\nMOMENTS:'+json.dumps([{'i':i+1,'quote':m.get('quote',''),'source':m.get('source_title','')} for i,m in enumerate(moments[:8])],ensure_ascii=False),max_tokens=2200)
            if obj.get('narration'):return obj
        except Exception:pass
    lead=(research.get('claims') or [{'text':'The story has moved back into focus.'}])[0]['text']
    return {'title':topic,'narration':[f'Here is what changed around {topic}.',f'The clearest reported detail is this: {lead}.','That matters because the original reaction and the later context are not the same thing.','And that is where the story gets more interesting than the headline.','The real question is what happens next.'],'order':list(range(min(3,len(moments))))}

def build_script_doc(topic,research,moments,duration):
    if llm_provider()!='none':
        try:
            obj=llm_json('Write a research-led internet documentary using a five-act arc: hook/ascent, blindspot/context, breaking point with real source audio, escalation/reaction, aftermath/payoff. Return {"title":"...","blocks":[{"kind":"narration|source","text":"...","moment":0}]}. Use only supplied evidence. Keep visual change 3-6s and let original speakers finish thoughts.\nTOPIC:'+topic+'\nRESEARCH:'+json.dumps(research,ensure_ascii=False)[:12000]+'\nMOMENTS:'+json.dumps([{'i':i,'quote':m.get('quote',''),'source':m.get('source_title','')} for i,m in enumerate(moments)],ensure_ascii=False)[:12000],max_tokens=5000)
            if obj.get('blocks'):return obj
        except Exception:pass
    return {'title':topic,'blocks':[
        {'kind':'source','moment':0,'text':''},
        {'kind':'narration','moment':0,'text':f'This is the documented story behind {topic}.'},
        {'kind':'source','moment':1,'text':''},
        {'kind':'narration','moment':0,'text':'Then the timeline changed, and the reaction became impossible to ignore.'},
        {'kind':'source','moment':2,'text':''},
        {'kind':'narration','moment':0,'text':'The important distinction is between what the original source says and what later commentary adds.'},
        {'kind':'source','moment':3,'text':''},
        {'kind':'narration','moment':0,'text':'That leaves the bigger question: what happens next?'}]}

# ---------------------------------------------------------------------------
# VISUALS / AUDIO

def font_path():
    c=[os.environ.get('VIDEOFINAL_FONT'),str(ROOT/'assets'/'fonts'/'Anton-Regular.ttf'),str(ROOT/'assets'/'fonts'/'DejaVuSans-Bold.ttf'),os.path.join(os.environ.get('WINDIR',r'C:\\Windows'),'Fonts','arialbd.ttf'),'/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf']
    return next((x for x in c if x and Path(x).exists()),None)

def F(size):
    p=font_path();return ImageFont.truetype(str(p),size) if p else ImageFont.load_default()

def fit_cover(im,w,h,focus=(.5,.5)):
    iw,ih=im.size;s=max(w/iw,h/ih);im=im.resize((int(iw*s),int(ih*s)),Image.Resampling.LANCZOS);nw,nh=im.size
    x=int(max(0,(nw-w)*focus[0]));y=int(max(0,(nh-h)*focus[1]));return im.crop((x,y,x+w,y+h))

def grade(im):
    return ImageEnhance.Contrast(ImageEnhance.Color(ImageEnhance.Brightness(im).enhance(.98)).enhance(.82)).enhance(1.08)

def caption_draw(im,text,w,h):
    ov=Image.new('RGBA',(w,h),(0,0,0,0));d=ImageDraw.Draw(ov);f=F(max(20,round(w*52/720)));maxw=int(w*.77);line='';lines=[]
    for word in text.split():
        q=(line+' '+word).strip()
        if line and d.textlength(q,font=f)>maxw:lines.append(line);line=word
        else:line=q
    if line:lines.append(line)
    y=int(h*.74 if h>900 else h*.73)
    for ln in lines[:2]:
        x=(w-d.textlength(ln,font=f))/2;d.text((x,y),ln,font=f,fill='white',stroke_width=max(2,round(w*5/720)),stroke_fill='black');y+=int(h*61/1280)
    return Image.alpha_composite(im.convert('RGBA'),ov).convert('RGB')

def render_shot(shot:Shot,project:Path,mode,res,cap_groups):
    if cv2 is None:raise RuntimeError('opencv-python required')
    w,h=RES[res][mode];out=project/'shots'/f'{shot.start:08.2f}.mp4';out.parent.mkdir(parents=True,exist_ok=True)
    writer=cv2.VideoWriter(str(out),cv2.VideoWriter_fourcc(*'mp4v'),FPS,(w,h));cap=cv2.VideoCapture(str(shot.clip)) if shot.clip else None
    if cap and not cap.isOpened():raise RuntimeError('cannot open source clip '+str(shot.clip))
    n=int(math.ceil(shot.dur*FPS));srcfps=(cap.get(cv2.CAP_PROP_FPS) or FPS) if cap else FPS;idx=-1;frame=None
    for i in range(n):
        t=i/FPS
        if cap:
            target=int((shot.cut+t)*srcfps)
            if target<idx or target>idx+6:cap.set(cv2.CAP_PROP_POS_FRAMES,target);idx=target-1
            while idx<target:
                ok,bgr=cap.read();idx+=1
                if not ok:cap.release();writer.release();raise RuntimeError(f'source ended early at {t:.2f}s')
                frame=bgr
            im=grade(fit_cover(Image.fromarray(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)),w,h))
        else:
            im=Image.new('RGB',(w,h),(10,12,16));d=ImageDraw.Draw(im);d.text((w/2,h/2-20),shot.text.upper(),font=F(max(34,w//18)),fill=(240,240,238),anchor='mm');d.rectangle((w*.43,h*.64,w*.57,h*.645),fill=(195,35,40))
            if shot.text: d.text((w/2,h*.69),'DOCUMENTARY',font=F(max(18,w//55)),fill=(195,35,40),anchor='mm')
        if i<3:
            a=i/3;arr=np.asarray(im,dtype=np.float32);im=Image.fromarray(np.clip(arr*a+255*(1-a)*.06,0,255).astype(np.uint8))
        active=next((g for g in cap_groups if g['start']<=shot.start+t<g['end']+.08),None)
        if active:im=caption_draw(im,active['text'],w,h)
        writer.write(cv2.cvtColor(np.asarray(im),cv2.COLOR_RGB2BGR))
    writer.release();
    if cap:cap.release()
    return out

def midi(m):return 440*2**((m-69)/12)
def synth_music(total,seed=17):
    n=int(math.ceil(total)*SR);t=np.arange(n)/SR;out=np.zeros(n,dtype=np.float32);rng=np.random.default_rng(seed);beat=60/70
    progression=[[45,52,57,60],[41,48,53,57],[43,50,55,58],[40,47,52,55]]
    for bar,st in enumerate(np.arange(0,total,beat*8)):
        chord=progression[bar%4];L=min(n-int(st*SR),int(beat*10*SR));tt=np.arange(max(0,L))/SR;pad=np.zeros(len(tt),dtype=np.float32)
        for m in chord:pad+=(np.sin(2*np.pi*midi(m)*tt)+.3*np.sin(2*np.pi*midi(m)*1.0017*tt)) / len(chord)
        env=np.sin(np.pi*np.clip(tt/(beat*10),0,1))**1.8;out[int(st*SR):int(st*SR)+L]+=.09*pad*env
    out+=rng.normal(0,.0025,n).astype(np.float32);peak=max(float(np.max(np.abs(out))),1e-6);out*=min(.6/peak,1.0)
    p=CACHE/f'music_{total:.2f}_{seed}.wav';
    with wave.open(str(p),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(SR);w.writeframes((out*32767).astype('<i2').tobytes())
    return p

def synth_sfx(total,times):
    n=int(math.ceil(total+1)*SR);out=np.zeros(n,dtype=np.float32)
    for k,at in enumerate(times):
        tt=np.arange(int(.55*SR))/SR;sig=.30*np.sin(2*np.pi*(75+10*k)*tt)*np.exp(-6*tt);j=int(at*SR);e=min(n,j+len(sig));out[j:e]+=sig[:e-j]
    p=CACHE/f'sfx_{total:.2f}_{len(times)}.wav'
    with wave.open(str(p),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(SR);w.writeframes((np.clip(out,-.5,.5)*32767).astype('<i2').tobytes())
    return p

def build_audio(shots,total,project,music,sfx):
    inputs=[];filters=[];labels=[];idx=0
    for si,s in enumerate(shots):
        if s.text:
            p=project/'tts'/f'{si:03d}.mp3';p.parent.mkdir(parents=True,exist_ok=True);tts(s.text,p);wav=project/'tts'/f'{si:03d}.wav';run([exe('ffmpeg'),'-y','-v','error','-i',str(p),'-af','loudnorm=I=-17:TP=-2:LRA=7','-ar',str(SR),'-ac','1',str(wav)],timeout=300);inputs+=['-i',str(wav)];filters.append(f'[{idx}:a]adelay={int(s.start*1000)}|{int(s.start*1000)},volume=1.0[d{idx}]');labels.append(f'[d{idx}]');idx+=1
        elif s.kind=='source' and s.clip:
            wav=project/'source_audio'/f'{si:03d}.wav';wav.parent.mkdir(parents=True,exist_ok=True);run([exe('ffmpeg'),'-y','-v','error','-ss',str(s.cut),'-t',str(s.dur),'-i',str(s.clip),'-vn','-af','loudnorm=I=-17:TP=-2:LRA=7','-ar',str(SR),'-ac','1',str(wav)],timeout=300);inputs+=['-i',str(wav)];filters.append(f'[{idx}:a]adelay={int(s.start*1000)}|{int(s.start*1000)},volume=.95[d{idx}]');labels.append(f'[d{idx}]');idx+=1
    if not labels:raise RuntimeError('no dialogue audio generated')
    filters.append(''.join(labels)+f'amix=inputs={len(labels)}:duration=longest:dropout_transition=0[dialogue]')
    mi=idx;si=idx+1;inputs+=['-i',str(music),'-i',str(sfx)]
    filters.append(f'[{mi}:a]volume=.34,apad,atrim=0:{total:.3f}[music]')
    filters.append('[music][dialogue]sidechaincompress=threshold=.03:ratio=8:attack=15:release=350[ducked]')
    filters.append(f'[dialogue][ducked][{si}:a]amix=inputs=3:duration=first:dropout_transition=0,dynaudnorm=f=150:g=7,alimiter=limit=.95[out]')
    out=project/'audio.m4a';run([exe('ffmpeg'),'-y','-v','error',*inputs,'-filter_complex',';'.join(filters),'-map','[out]','-ar',str(SR),'-ac','2','-c:a','aac','-b:a','192k','-t',f'{total:.3f}',str(out)],timeout=900);return out

# ---------------------------------------------------------------------------
# ORCHESTRATOR

def source_moment_pipeline(topic,research,root,mode,wanted=10):
    stage(root,STATE,'source_hunt',mode=mode)
    sources=choose_sources(topic,research,count=7)
    if not sources:raise RuntimeError('No audiovisual candidates found.')
    moments=[]
    for si,s in enumerate(sources):
        source=dict(s);info=source_info(source['url']);source.update(info);source['subtitles']=False
        try:cues=source_subs(source['url'],hashlib.sha1(source['url'].encode()).hexdigest()[:15])
        except Exception:cues=[]
        if cues:
            source['subtitles']=True
            for m in vtt_moments(cues,3):m.update(source_index=si,source_url=source['url'],source_title=source.get('title',''),uploader=source.get('uploader',''),subtitle_cues=cues);moments.append(m)
        else:
            for m in asr_moments(source,root,3):m.update(source_index=si,source_url=source['url'],source_title=source.get('title',''),uploader=source.get('uploader',''));moments.append(m)
        if len(moments)>=wanted:break
    return sources,moments[:wanted]

def short_shots(topic,research,root,res):
    sources,moments=source_moment_pipeline(topic,research,root,'short',10)
    if len(moments)<3:raise RuntimeError('Could not obtain three usable spoken source moments after subtitles and Whisper probes.')
    script=build_script_short(topic,research,moments);shots=[];groups=[]
    # Real speaker first, then narration, then speaker, then narration/source alternation.
    order=script.get('order',[]) or list(range(3))
    # Accept either 1-based LLM order or zero-based fallback order; drop invalid/duplicate picks.
    seen=set();queue=[]
    for i in order:
        try:m=moments[int(i)-1] if int(i)>0 else moments[int(i)]
        except Exception:continue
        key=(m['source_url'],round(m['cut'],2));
        if key not in seen:seen.add(key);queue.append(m)
    for m in moments:
        key=(m['source_url'],round(m['cut'],2))
        if key not in seen:seen.add(key);queue.append(m)
    downloaded=[]
    for i,m in enumerate(queue[:10]):
        key=hashlib.sha1((m['source_url']+f'|{m['cut']:.2f}|{m['dur']:.2f}').encode()).hexdigest()[:12];p=ASSET_CLIPS/f'{slug(topic)}_short_{i:02d}_{key}.mp4'
        if not p.exists():download_segment(m['source_url'],m['cut'],m['dur'],p)
        local_words=m.get('asr_words') or []
        if local_words:
            # Probe-ASR timestamps are absolute source times; downloaded clip words must be local.
            local_words=[{'text':w['text'],'start':max(0,float(w['start'])-float(m['cut'])),'end':max(0,float(w['end'])-float(m['cut']))} for w in local_words]
        elif has_module('faster_whisper'):
            local_words=whisper_words(p)
        m['file']=str(p);m['local_words']=local_words;downloaded.append(m)
    root_words=lambda m: [{'text':w['text'],'start':w['start'],'end':w['end']} for w in m.get('local_words',[]) if w['end']<=m['dur']+.2]
    narr=script.get('narration',[]);ni=0
    def add_src(m):
        nonlocal shots
        st=sum(x.dur for x in shots);words=root_words(m);shots.append(Shot('source',min(8,float(m['dur'])),Path(m['file']),0.0,'',words,st))
        for g in cap_groups(words):groups.append({'start':st+g['start'],'end':st+g['end'],'text':g['text']})
    def add_vo(text,broll=None):
        nonlocal shots
        p=root/'temp'/f'vo_{len(shots):03d}.mp3';p.parent.mkdir(parents=True,exist_ok=True);tts(text,p);d=audio_duration(p);st=sum(x.dur for x in shots);shots.append(Shot('narration',d,Path(broll['file']) if broll else None,0.0,text,None,st));
        for g in cap_groups(proportional_words(text,st,d)):groups.append(g)
    if downloaded:add_src(downloaded.pop(0))
    for text in narr:
        if text:add_vo(text,downloaded[0] if downloaded else None)
        if downloaded:add_src(downloaded.pop(0))
        if sum(s.dur for s in shots)>=54:break
    for m in downloaded:
        if sum(s.dur for s in shots)>=54:break
        add_src(m)
    total=sum(s.dur for s in shots)
    if total<45:raise RuntimeError(f'Short edit only reached {total:.1f}s; agent will retry another story.')
    if total>59:shots=shots[:]; raise RuntimeError(f'Short edit exceeded 59s at {total:.1f}s; agent will re-plan.')
    root.joinpath('captions.json').write_text(json.dumps(groups,ensure_ascii=False,indent=2),encoding='utf-8')
    return shots,groups

def doc_shots(topic,research,root,res,duration_target):
    sources,moments=source_moment_pipeline(topic,research,root,'doc',12)
    if len(moments)<4:raise RuntimeError('Documentary source hunt could not obtain enough original spoken moments.')
    script=build_script_doc(topic,research,moments,duration_target);shots=[];groups=[]
    # Title card, then 5-act blocks.
    shots.append(Shot('card',1.8,None,0.0,topic[:42],None,0.0))
    files=[]
    for i,m in enumerate(moments):
        key=hashlib.sha1((m['source_url']+f'|{m['cut']:.2f}|{m['dur']:.2f}').encode()).hexdigest()[:12];p=ASSET_CLIPS/f'{slug(topic)}_doc_{i:02d}_{key}.mp4'
        if not p.exists():download_segment(m['source_url'],m['cut'],m['dur'],p)
        if has_module('faster_whisper') and not m.get('local_words'):m['local_words']=whisper_words(p)
        m['file']=str(p);files.append(m)
    for b in script.get('blocks',[]):
        st=sum(x.dur for x in shots);kind=b.get('kind','narration');mi=int(b.get('moment',0) or 0);mi=max(0,min(mi,len(files)-1))
        if kind=='source':
            m=files[mi];dur=min(8,float(m['dur']));words=m.get('local_words',[]);shots.append(Shot('source',dur,Path(m['file']),0.0,'',words,st));
            for g in cap_groups(words):groups.append({'start':st+g['start'],'end':st+g['end'],'text':g['text']})
        else:
            text=clean(str(b.get('text','')));
            if not text:continue
            p=root/'temp'/f'doc_vo_{len(shots):03d}.mp3';p.parent.mkdir(parents=True,exist_ok=True);tts(text,p);d=audio_duration(p);shots.append(Shot('narration',d,Path(files[mi]['file']) if files else None,0.0,text,None,st));groups += cap_groups(proportional_words(text,st,d))
    total=sum(s.dur for s in shots)
    if total<max(90,duration_target*.55):raise RuntimeError(f'Documentary plan too short: {total:.1f}s')
    return shots,groups

def render_project(topic,mode,res,duration_target):
    root,state=project_for(topic,mode,res);stage(root,state,'research');r=research(topic);state['research']=r
    if mode=='short':shots,groups=short_shots(topic,r,root,res)
    else:shots,groups=doc_shots(topic,r,root,res,duration_target)
    state['shots']=[{'kind':s.kind,'start':s.start,'dur':s.dur,'clip':str(s.clip) if s.clip else None,'text':s.text} for s in shots];state['caption_groups']=groups
    stage(root,state,'render')
    for i,s in enumerate(shots):render_shot(s,root,mode,res,groups)
    music=synth_music(sum(s.dur for s in shots),17 if mode=='short' else 29);sfx=synth_sfx(sum(s.dur for s in shots),[s.start for s in shots if s.kind=='source'])
    audio=build_audio(shots,sum(s.dur for s in shots),root,music,sfx)
    concat=root/'shots.txt';concat.write_text('\n'.join(f"file '{(root/'shots'/f'{s.start:08.2f}.mp4').resolve().as_posix()}'" for s in shots),encoding='utf-8')
    video_only=root/'video_only.mp4';run([exe('ffmpeg'),'-y','-v','error','-f','concat','-safe','0','-i',str(concat),'-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p','-r',str(FPS),str(video_only)],timeout=1800)
    out=OUTPUTS/f'{slug(topic)}_{res}_{mode}.mp4';run([exe('ffmpeg'),'-y','-v','error','-i',str(video_only),'-i',str(audio),'-map','0:v','-map','1:a','-c:v','copy','-c:a','aac','-b:a','192k','-movflags','+faststart','-shortest',str(out)],timeout=900)
    state['output']=str(out);state['caption_srt']=str(root/'captions.srt');write_srt(groups,root/'captions.srt')
    qc=qc(out,mode,res,sum(s.dur for s in shots));state['qc']=qc;state['status']='ready_for_approval' if qc['pass'] else 'blocked';state['artifacts']={'video':str(out),'state':str(root/'state.json'),'captions':str(root/'captions.srt')};
    (root/'state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8');
    return state

# ---------------------------------------------------------------------------
# QC / METADATA

def probe(path):
    o=json.loads(run([exe('ffprobe'),'-v','error','-print_format','json','-show_streams','-show_format',str(path)],timeout=180).stdout);v=next((x for x in o['streams'] if x['codec_type']=='video'),{});a=next((x for x in o['streams'] if x['codec_type']=='audio'),{});return {'duration':float(o['format'].get('duration',0)),'video':{'width':int(v.get('width',0)),'height':int(v.get('height',0)),'codec':v.get('codec_name'),'fps':v.get('r_frame_rate')},'audio':{'codec':a.get('codec_name'),'sr':int(a.get('sample_rate',0))}}

def activity(path):
    if cv2 is None:return 1
    c=cv2.VideoCapture(str(path));n=int(c.get(cv2.CAP_PROP_FRAME_COUNT) or 0);prev=None;d=[]
    for pos in np.linspace(0,max(1,n-1),8).astype(int):
        c.set(cv2.CAP_PROP_POS_FRAMES,int(pos));ok,f=c.read()
        if not ok:continue
        g=cv2.cvtColor(f,cv2.COLOR_BGR2GRAY)
        if prev is not None:d.append(float(np.mean(cv2.absdiff(prev,g)))/255)
        prev=g
    c.release();return float(np.median(d)) if d else 0

def peak(path):
    p=run([exe('ffmpeg'),'-v','info','-i',str(path),'-af','volumedetect','-vn','-f','null','-'],timeout=180,check=False);m=re.search(r'max_volume:\s*(-?[\d.]+)\s*dB',p.stderr);return float(m.group(1)) if m else None

def qc(path,mode,res,expected):
    q=probe(path);wh=RES[res][mode];dur_ok=(45<=q['duration']<=59) if mode=='short' else abs(q['duration']-expected)/max(expected,1)<=.20;streams=q['video']['codec']=='h264' and q['audio']['codec'] in ('aac','mp4a');geom=(q['video']['width'],q['video']['height'])==wh;act=activity(path);pk=peak(path);ok=dur_ok and streams and geom and act>.012 and (pk is None or pk<-.5);return {'pass':ok,'duration':q['duration'],'duration_ok':dur_ok,'streams_ok':streams,'geometry':q['video'],'geometry_ok':geom,'visual_activity':act,'visual_activity_ok':act>.012,'peak_db':pk,'peak_ok':pk is None or pk<-.5}

def write_srt(groups,path):
    def ts(x):
        ms=int(round(max(0,x)*1000));return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'
    path.write_text('\n\n'.join(f'{i}\n{ts(g["start"])} --> {ts(g["end"])}\n{g["text"]}' for i,g in enumerate(groups,1))+'\n',encoding='utf-8')

def write_metadata(topic,mode,research,root):
    title=(topic[:82]+' — What Really Happened?')[:100];desc=f'Original research-led {mode.lower()} about {topic}. Source links and factual context are stored with the project. What would you have done?'
    if llm_provider()!='none':
        try:
            o=llm_json('Create concrete YouTube title and description from this research. No unsupported clickbait. End with a specific audience question. Return {"title":"...","description":"..."}.\n'+json.dumps(research,ensure_ascii=False)[:9000],max_tokens=1000);title=clean(str(o.get('title',title)))[:100];desc=str(o.get('description',desc)).strip()
        except Exception:pass
    (root/'title.txt').write_text(title+'\n',encoding='utf-8');(root/'description.txt').write_text(desc+'\n',encoding='utf-8');return {'title':title,'description':desc}

# ---------------------------------------------------------------------------
# AUTOPILOT / UI

def autopilot(mode,niche,res,topic=None,retries=5,duration='3m30s'):
    if topic: rows=[{'title':topic,'score':100,'score_10':10}]
    else:
        names=list(NICHES) if niche=='all' else [niche];rows=[]
        for n in names:rows+=niche_candidates(n,mode,8)
        rows.sort(key=lambda x:x['score'],reverse=True);rows=rows[:retries]
    if not rows:raise RuntimeError('Agenten hittade inga story-kandidater.')
    failures=[];target=210
    m=re.search(r'(\d+)m',duration);target=int(m.group(1))*60 if m else 210
    s=re.search(r'(\d+)s',duration);target+=(int(s.group(1)) if s else 0)
    for row in rows:
        t=row['title'];print(f'\n[AUTOPILOT] {t}  |  {row.get("score_10",10):.1f}/10 ({row.get("score",100):.1f}%)')
        try:
            root,st=project_for(t,mode,res);meta=research(t);write_metadata(t,mode,meta,root)
            # Use the real renderer with the selected story, bypassing any manual source picker.
            if mode=='short':return render_project(t,'short',res,55)
            return render_project(t,'doc',res,target)
        except Exception as exc:
            failures.append({'topic':t,'error':str(exc)[:700]});print('[AUTOPILOT] blocked -> next story')
    raise RuntimeError('All automatic story attempts failed: '+json.dumps(failures,ensure_ascii=False))

def banner():
    st=llm_status();print('\n'+'='*72);print('VIDEOFINAL 2026 | AUTOPILOT CREATOR STUDIO');print('LLM:',st['provider'],'/',st['model'] or 'none');print('='*72)

def choose(prompt,default,choices):
    x=input(prompt).strip() or default;return x if x in choices else default

def interactive():
    while True:
        banner();print('1) SHORTS AUTOPILOT');print('2) DOCUMENTARY AUTOPILOT');print('Q) EXIT');c=input('\nChoose [1]: ').strip().lower() or '1'
        if c=='q':return
        if c not in ('1','2'):continue
        mode='short' if c=='1' else 'doc'
        print('\nNICHE');print('  A) AUTO — agent scans all niches')
        for i,n in enumerate(NICHES,1):print(f'  {i:2}) {n}')
        n=input('Choose [A]: ').strip().lower() or 'a';niche='all' if n=='a' else (list(NICHES)[int(n)-1] if n.isdigit() and 1<=int(n)<=len(NICHES) else 'all')
        print('\nQUALITY');print('  1) 320p');print('  2) 720p');print('  3) 1080p');q=input('Choose [2]: ').strip() or '2';res={'1':'320p','2':'720p','3':'1080p'}.get(q,'720p')
        print('\nAUTOPILOT: topic, sources, script, voice, edit and QC are automatic.')
        try:
            st=autopilot(mode,niche,res);print('\n'+'='*72);print('READY FOR APPROVAL');print('topic :',st['topic']);print('output:',st['output']);print('qc:',json.dumps(st['qc'],ensure_ascii=False));print('='*72)
        except Exception as exc:print('\nAUTOPILOT STOPPED:',exc);print('The story/build state is preserved under projects/.')

def selftest():
    print('VIDEOFINAL SELFTEST')
    assert RES['320p']['short']==(320,568);assert RES['720p']['short']==(720,1280);assert RES['1080p']['doc']==(1920,1080)
    assert cap_groups(proportional_words('This is a test of captions',0,2));p=synth_music(2);assert p.exists();print('PASS: core, captions, music, resolutions')

def main():
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=['short','doc']);p.add_argument('--topic',default='');p.add_argument('--niche',default='all');p.add_argument('--resolution',choices=list(RES),default='720p');p.add_argument('--duration',default='3m30s');p.add_argument('--selftest',action='store_true');p.add_argument('--test-llm',action='store_true');p.add_argument('--capabilities',action='store_true')
    a=p.parse_args()
    if a.selftest:selftest();return
    if a.test_llm:print(json.dumps(test_llm(),ensure_ascii=False,indent=2));return
    if a.capabilities:print(json.dumps({'llm':llm_status(),'ffmpeg':shutil.which('ffmpeg'),'ffprobe':shutil.which('ffprobe'),'yt_dlp':has_module('yt_dlp'),'edge_tts':has_module('edge_tts'),'faster_whisper':has_module('faster_whisper'),'resolutions':RES,'niches':list(NICHES)},ensure_ascii=False,indent=2));return
    if len(sys.argv)==1:ensure_dependencies();interactive();return
    ensure_dependencies()
    if not a.mode:p.error('--mode required when not interactive')
    print(json.dumps(autopilot(a.mode,a.niche,a.resolution,a.topic or None,5,a.duration),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
