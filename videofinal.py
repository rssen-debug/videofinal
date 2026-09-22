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
        'yt_dlp':'yt-dlp>=2024.08.0',
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
    clients=('android_vr','android','web_embedded','tv','web','default')
    cookie_file=os.environ.get('VIDEOFINAL_YT_COOKIES','').strip()
    for client in clients:
        cmd=[sys.executable,'-m','yt_dlp','--flat-playlist','--dump-single-json','--skip-download','--no-warnings',
             '--extractor-args',f'youtube:player_client={client}',f'ytsearch{max(n*3,12)}:{q}']
        if cookie_file and Path(cookie_file).exists():cmd += ['--cookies',cookie_file]
        p=run(cmd,timeout=180,check=False)
        if p.returncode:continue
        try:o=json.loads(p.stdout)
        except Exception:continue
        rows=[]
        for e in o.get('entries',[]) if isinstance(o,dict) else []:
            if not isinstance(e,dict):continue
            vid=e.get('id');u=e.get('webpage_url') or e.get('url') or (f'https://www.youtube.com/watch?v={vid}' if vid else '')
            if not u:continue
            rows.append({'id':vid or '','url':u,'title':clean(e.get('title','')),'uploader':clean(e.get('uploader') or e.get('channel') or ''),'channel_url':e.get('channel_url') or '','client':client})
            if len(rows)>=n:break
        if rows:return rows
    return []

def _topic_entities(topic:str,research:dict[str,Any])->list[str]:
    ents=[clean(str(x)) for x in (research.get('entities',[]) or []) if clean(str(x))]
    if ents:return list(dict.fromkeys(ents))[:6]
    hits=[]
    for m in re.finditer(r'\b[A-Z][A-Za-z0-9_-]{2,}(?:\s+[A-Z][A-Za-z0-9_-]{2,})?\b',topic):
        x=clean(m.group(0))
        if x.lower() not in {'The','This','What','After','How','Why','And'} and x not in hits:hits.append(x)
    return hits[:6]

def choose_sources(topic,research,count=7):
    ents=_topic_entities(topic,research)
    queries=[topic]
    for e in ents:
        queries.extend([f'"{e}" official',f'"{e}" live interview',f'"{e}" full stream',f'"{e}" original'])
    queries += [q for q in (research.get('queries',[]) or []) if q and q not in queries]
    cand=[];seen=set()
    for q in queries[:18]:
        for r in yt_search(q,8):
            if r['url'] in seen:continue
            seen.add(r['url'])
            blob=(r['title']+' '+r['uploader']).lower();score=.25
            for e in ents:
                parts=[p.lower() for p in e.split() if len(p)>=4]
                if parts and all(p in blob for p in parts):score+=.20
            if any(k in blob for k in ('official','original','live','interview','podcast','channel','network')):score+=.10
            if any(k in blob for k in ('reaction','fan edit','fan-made','compilation','commentary','shorts','highlights','reupload')):score-=.28
            r['party_score']=round(max(0,min(.99,score)),3);cand.append(r)
    cand.sort(key=lambda x:x['party_score'],reverse=True)
    if llm_provider()!='none' and cand:
        try:
            sample=[{'i':i+1,'title':r['title'],'uploader':r['uploader'],'url':r['url'],'score':r['party_score']} for i,r in enumerate(cand[:60])]
            obj=llm_json('Select source videos for a fact-first internet documentary. Prefer original/first-party speaker, creator, company, event, network, interview, or livestream. A single source may supply many different moments. Reject fan edits, commentary, reuploads and duplicate coverage. Return {"pick":[1,2,3,4,5,6,7]}.\n'+json.dumps(sample,ensure_ascii=False),max_tokens=1700)
            picks=[]
            for i in obj.get('pick',[])[:count]:
                try:
                    row=cand[int(i)-1]
                    if row not in picks:picks.append(row)
                except Exception:pass
            if picks:cand=picks
        except Exception:pass
    return cand[:max(1,count)]

def source_info(url:str):
    cookie_file=os.environ.get('VIDEOFINAL_YT_COOKIES','').strip()
    for client in ('android_vr','android','web_embedded','tv','web','default'):
        cmd=[sys.executable,'-m','yt_dlp','--dump-single-json','--skip-download','--no-warnings','--extractor-args',f'youtube:player_client={client}',url]
        if cookie_file and Path(cookie_file).exists():cmd += ['--cookies',cookie_file]
        p=run(cmd,timeout=180,check=False)
        if p.returncode:continue
        try:
            o=json.loads(p.stdout)
            return {'duration':float(o.get('duration') or 60),'title':o.get('title',''),'uploader':o.get('uploader') or o.get('channel',''),'id':o.get('id',''),'client':client}
        except Exception:continue
    return {'duration':60.0}

def parse_vtt_file(path:Path):
    if not path.exists():return []
    return parse_vtt(path)

def source_subs(url:str, tag:str):
    d=CACHE/'subs';d.mkdir(parents=True,exist_ok=True);pref=d/tag
    cookie_file=os.environ.get('VIDEOFINAL_YT_COOKIES','').strip()
    clients=('android_vr','web_embedded','android','tv','web','default')
    for client in clients:
        cmd=[sys.executable,'-m','yt_dlp','--skip-download','--write-auto-subs','--write-subs','--sub-langs','en.*,en','--sub-format','vtt','--convert-subs','vtt','--no-warnings','--extractor-args',f'youtube:player_client={client}','-o',str(pref)+'.%(ext)s',url]
        if cookie_file and Path(cookie_file).exists():cmd += ['--cookies',cookie_file]
        run(cmd,timeout=240,check=False)
        for p in d.glob(tag+'*.vtt'):
            cues=parse_vtt_file(p)
            if cues:return cues
    return []

def vtt_moments(cues,wanted=8):
    windows=[];seen=set()
    for i,c in enumerate(cues):
        start=c['start'];parts=[];end=start
        for j in range(i,min(len(cues),i+12)):
            if cues[j]['start']-start>8:break
            parts.append(cues[j]['text']);end=cues[j]['end'];dur=end-start;text=clean(' '.join(parts))
            if 4<=dur<=8 and len(text.split())>=6:
                key=re.sub(r'\W+','',text.lower())[:140]
                if key in seen:continue
                seen.add(key);windows.append({'cut':max(0,start-.18),'dur':min(8,end-max(0,start-.18)+.35),'quote':text})
            if len(windows)>=wanted*3:break
        if len(windows)>=wanted*3:break
    if llm_provider()!='none' and windows:
        try:
            sample=[{'i':i+1,'quote':w['quote'],'cut':w['cut']} for i,w in enumerate(windows[:80])]
            obj=llm_json('Pick the strongest complete spoken moments from this transcript. Prefer concrete claims, emotional turns, answers and moments that explain the story. Return {"pick":[1,2,3,4,5,6,7,8]}.\n'+json.dumps(sample,ensure_ascii=False),max_tokens=1500)
            picked=[]
            for i in obj.get('pick',[])[:wanted]:
                try:picked.append(windows[int(i)-1])
                except Exception:pass
            if picked:windows=picked
        except Exception:pass
    return windows[:wanted]

def asr_moments(source,root,wanted=8):
    dur=float(source.get('duration') or 0)
    if dur<5 or not has_module('faster_whisper'):return []
    length=min(8.5,max(5.5,dur*.10));positions=[dur*x for x in (0,.10,.20,.30,.40,.50,.60,.70,.80,.90)]
    out=[]
    for raw_cut in positions:
        cut=round(max(0,min(float(raw_cut),max(0,dur-length))),2)
        key=hashlib.sha1((source['url']+f'|asr|{cut}').encode()).hexdigest()[:12];p=ASSET_CLIPS/f'probe_{key}.mp4'
        try:
            if not p.exists():download_segment(source['url'],cut,length,p)
            words=whisper_words(p)
            if not words:continue
            windows=[]
            for i,w in enumerate(words):
                st=float(w['start']);buf=[];en=st
                for z in words[i:i+50]:
                    if float(z['start'])-st>8:break
                    buf.append(z);en=float(z['end']);txt=clean(' '.join(a['text'] for a in buf));d=en-st
                    if 4<=d<=8 and len(txt.split())>=6:
                        windows.append({'cut':max(0,cut+st-.18),'dur':min(8,en-st+.45),'quote':txt,'asr_words':[{'text':a['text'],'start':float(a['start'])+cut,'end':float(a['end'])+cut} for a in buf]})
            windows.sort(key=lambda x:len(x['quote'].split()),reverse=True)
            for w in windows[:3]:out.append(w)
        except Exception:continue
        if len(out)>=wanted:break
    seen=set();uniq=[]
    for w in out:
        k=re.sub(r'\W+','',w['quote'].lower())[:140]
        if k in seen:continue
        seen.add(k);uniq.append(w)
    return uniq[:wanted]

def download_segment(url:str,cut:float,dur:float,out:Path):
    out.parent.mkdir(parents=True,exist_ok=True)
    cookie_file=os.environ.get('VIDEOFINAL_YT_COOKIES','').strip()
    formats=('bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best[height<=720]/best','best[height<=720]/best')
    clients=('android_vr','android','web_embedded','tv','web','default')
    last=''
    for fmt in formats:
        for client in clients:
            cmd=[sys.executable,'-m','yt_dlp','--no-progress','--force-keyframes-at-cuts','--merge-output-format','mp4','-f',fmt,'--download-sections',f'*{cut:.2f}-{cut+dur:.2f}','--extractor-args',f'youtube:player_client={client}','-o',str(out),url]
            if cookie_file and Path(cookie_file).exists():cmd += ['--cookies',cookie_file]
            p=run(cmd,timeout=700,check=False);last=(p.stderr or p.stdout or '')[-1200:]
            if p.returncode==0 and out.exists() and out.stat().st_size>10000:return out
            if out.exists():
                try:out.unlink()
                except Exception:pass
    # Full-download trim fallback; this mirrors the proven Arena strategy.
    temp=out.with_suffix('.source.mp4')
    cmd=[sys.executable,'-m','yt_dlp','--no-progress','--merge-output-format','mp4','--extractor-args','youtube:player_client=android_vr,android,web_embedded,tv,default','-f',formats[0],'-o',str(temp),url]
    if cookie_file and Path(cookie_file).exists():cmd += ['--cookies',cookie_file]
    p=run(cmd,timeout=1200,check=False)
    if p.returncode or not temp.exists():raise RuntimeError('source download failed: '+last)
    run([exe('ffmpeg'),'-y','-v','error','-ss',str(cut),'-t',str(dur),'-i',str(temp),'-vf','scale=-2:720,fps=30,setsar=1','-c:v','libx264','-preset','veryfast','-crf','20','-pix_fmt','yuv420p','-c:a','aac','-b:a','128k','-movflags','+faststart',str(out)],timeout=1000)
    return out

def source_moment_pipeline(topic,research,root,mode,wanted=12):
    stage(root,STATE,'source_hunt',mode=mode)
    sources=choose_sources(topic,research,count=7)
    if not sources:
        raise RuntimeError('No audiovisual candidates found after automatic discovery.')
    moments=[]
    for si,s in enumerate(sources):
        source=dict(s)
        try:source.update(source_info(source['url']))
        except Exception:source.setdefault('duration',60.0)
        try:cues=source_subs(source['url'],hashlib.sha1(source['url'].encode()).hexdigest()[:15])
        except Exception:cues=[]
        if cues:
            for m in vtt_moments(cues,wanted=min(8,wanted-len(moments))):
                m.update(source_index=si,source_url=source['url'],source_title=source.get('title',''),uploader=source.get('uploader',''),subtitle_cues=cues)
                moments.append(m)
        else:
            for m in asr_moments(source,root,wanted=min(8,wanted-len(moments))):
                m.update(source_index=si,source_url=source['url'],source_title=source.get('title',''),uploader=source.get('uploader',''))
                moments.append(m)
        if len(moments)>=wanted:break
    return sources,moments[:wanted]

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
    sources,moments=source_moment_pipeline(topic,research,root,'short',12)
    if not sources:
        raise RuntimeError('No audiovisual source survived automatic acquisition.')
    script=build_script_short(topic,research,moments)
    shots=[];groups=[]
    order=script.get('order',[]) or list(range(min(6,len(moments))))
    seen=set();queue=[]
    for i in order:
        try:
            m=moments[int(i)-1] if int(i)>0 else moments[int(i)]
        except Exception:
            continue
        key=(m.get('source_url'),round(float(m.get('cut',0)),2))
        if key not in seen:
            seen.add(key);queue.append(m)
    for m in moments:
        key=(m.get('source_url'),round(float(m.get('cut',0)),2))
        if key not in seen:
            seen.add(key);queue.append(m)

    # If speech moments are sparse, add real-footage B-roll windows from the same
    # verified sources. These carry source audio, but only speech windows get
    # word-synced source captions.
    if len(queue)<5:
        for si,src in enumerate(sources[:4]):
            dur=float(src.get('duration') or 60)
            for pct in (0.08,0.28,0.48,0.68,0.84):
                cut=min(max(0.0,dur*pct),max(0.0,dur-6.0))
                key=(src.get('url'),round(cut,2))
                if key in seen:
                    continue
                seen.add(key)
                queue.append({
                    'source_url':src['url'],'source_title':src.get('title',''),
                    'uploader':src.get('uploader',''),'cut':cut,'dur':6.0,'quote':'',
                })
                if len(queue)>=8:
                    break
            if len(queue)>=8:
                break

    downloaded=[]
    for i,m in enumerate(queue[:12]):
        key=hashlib.sha1((m['source_url']+f'|{m.get("cut",0):.2f}|{m.get("dur",6):.2f}').encode()).hexdigest()[:12]
        p=ASSET_CLIPS/f'{slug(topic)}_short_{i:02d}_{key}.mp4'
        try:
            if not p.exists():
                download_segment(m['source_url'],float(m.get('cut',0)),float(m.get('dur',6)),p)
        except Exception:
            continue
        local_words=m.get('asr_words') or []
        if local_words:
            local_words=[{
                'text':w['text'],
                'start':max(0,float(w['start'])-float(m.get('cut',0))),
                'end':max(0,float(w['end'])-float(m.get('cut',0)))
            } for w in local_words]
        elif has_module('faster_whisper') and not m.get('quote'):
            local_words=whisper_words(p)
        m['file']=str(p);m['local_words']=local_words
        downloaded.append(m)

    if not downloaded:
        raise RuntimeError('All automatic source downloads failed.')

    def words_for(m):
        return [w for w in (m.get('local_words') or []) if float(w.get('start',0)) <= float(m.get('dur',6))+.2]

    narr=list(script.get('narration',[]) or [])
    narr_i=0

    def add_source(m):
        st=sum(x.dur for x in shots)
        dur=min(8.0,max(4.0,float(m.get('dur',6))))
        words=words_for(m)
        shots.append(Shot('source',dur,Path(m['file']),0.0,'',words,st))
        for g in cap_groups(words):
            groups.append({'start':st+g['start'],'end':st+g['end'],'text':g['text']})

    def add_narration(text, broll=None):
        st=sum(x.dur for x in shots)
        p=root/'temp'/f'vo_{len(shots):03d}.mp3';p.parent.mkdir(parents=True,exist_ok=True)
        tts(text,p);d=max(.5,audio_duration(p))
        shots.append(Shot('narration',d,Path(broll['file']) if broll else None,0.0,text,None,st))
        groups.extend(cap_groups(proportional_words(text,st,d)))

    # Consequence-first rhythm: source -> narrator -> source -> narrator.
    if downloaded:
        add_source(downloaded.pop(0))
    while downloaded and sum(x.dur for x in shots)<54:
        if narr_i<len(narr):
            add_narration(narr[narr_i],downloaded[0] if downloaded else None)
            narr_i+=1
        if downloaded and sum(x.dur for x in shots)<54:
            add_source(downloaded.pop(0))
        else:
            break

    # Pad only with remaining real footage; never synthesize visual filler.
    while downloaded and sum(x.dur for x in shots)<54:
        add_source(downloaded.pop(0))

    total=sum(x.dur for x in shots)
    if total<45:
        raise RuntimeError(f'Short edit only reached {total:.1f}s; automatic source coverage was insufficient.')
    if total>59:
        raise RuntimeError(f'Short edit exceeded 59s at {total:.1f}s; automatic re-plan required.')
    root.joinpath('captions.json').write_text(json.dumps(groups,ensure_ascii=False,indent=2),encoding='utf-8')
    return shots,groups

def doc_shots(topic,research,root,res,duration_target):
    sources,moments=source_moment_pipeline(topic,research,root,'doc',12)
    if not sources:raise RuntimeError('Documentary source hunter found no audiovisual sources.')
    # Documentary fallback: when original dialogue is scarce, build evidence-card/B-roll beats
    # from real source footage and research instead of fabricating speaker quotes.
    if len(moments)<4:
        for si,src in enumerate(sources[:6]):
            dur=float(src.get('duration') or 60)
            for pct in (0.12,0.42,0.72):
                cut=min(max(0.0,dur*pct-3.0),max(0.0,dur-7.0))
                moments.append({
                    'source_index':si,'source_url':src['url'],
                    'source_title':src.get('title',''),'uploader':src.get('uploader',''),
                    'quote':'','cut':cut,'dur':min(7.0,max(5.0,dur-cut)),
                    'subtitle_cues':[],
                })
                if len(moments)>=8:break
            if len(moments)>=8:break
    if len(moments)<4:raise RuntimeError('Documentary source hunter could not obtain enough source moments.')
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
    print('\n[IDEA LAB] top candidates:')
    for i,r in enumerate(rows[:5],1):
        print(f"  {i}) {r.get('score_10',r.get('score',0)/10):.1f}/10 ({r.get('score',0):.1f}%) — {r.get('title','')[:110]}")
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
