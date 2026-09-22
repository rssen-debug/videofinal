#!/usr/bin/env python3
"""trend_scout.py — single-file SHORTS MACHINE: discover trends, download, make the video.

PIPELINE (1:1 with the youtubeshortskai episodes, same style):
  scout  -> find trending stories (no hardcoded 500-list needed; discovery first)
  build  -> scaffold episode files from a brief pick
  eyes   -> download ANY direct media URL (X/Twitch/Kick/YouTube/VOD sections)
  make   -> render the Short: same captions, same structure, same QA

SAME STYLE? Yes by construction: 720x1280/30, white DejaVu 52px captions at y948
(max 2 lines), live-clips + muted B-roll assembly, loudnorm speech, ducked
procedural documentary bed, volumedetect/RMS/ASR QA. TTS: the exact Arena
session voice cannot ship in a file (session-scoped); default is a FIXED free
edge-tts voice (consistent forever), or pin ElevenLabs/OpenAI + your key, or drop
in your own WAVs. Pick ONE voice and never swap silently.

WHICH APIs / KEYS?
  Needed:  NONE for scout/eyes-download/make (Kick public API, Reddit public
           JSON, Google News RSS, YouTube channel RSS, yt-dlp, edge-tts, FFmpeg).
  Optional: BRAVE_API_KEY (free tier) for `eyes --find` web-link discovery;
           OPENAI_API_KEY / ELEVEN_API_KEY (+voice id) for cloud TTS;
           --cookies FILE (YOUR OWN exported session) if a site gates downloads.
  Rate limits: this tool is polite on purpose (delays + cache + backoff) and has
  NO evasion features. If a site says stop, it stops. Use your own accounts/keys.

USAGE
  python3 trend_scout.py scout --days 7 --top 5 [--roster mine.json --out briefs/]
  python3 trend_scout.py build --brief briefs/scout_2026-09-20.json --pick 0 --episode 07
  python3 trend_scout.py eyes --get URL -o clip.mp4 [--sections "*1:00-2:00"] [--cookies c.txt]
  python3 trend_scout.py eyes --find "kai cenat iceland"   # needs BRAVE_API_KEY
  python3 trend_scout.py make --do init --brief ... --pick 0 --episode 07
  python3 trend_scout.py make --do run --make make_07.json
  python3 trend_scout.py make --do selftest --dir /tmp/selftest   # no network, proves it works
  python3 trend_scout.py roster

ROSTER: discovery-first (Kick popular, Reddit, news) + small curated watchlist
below. New names surface as new_faces guesses. Extend via --roster JSON:
[{"name":"...","fame":8,"kick":"slug","twitch":null,"youtube_channel_id":null}]

RULES BAKED IN: real footage only (no AI visuals); finished MP4 shown to the
user and approved BEFORE any push; one locked narrator voice; no fabricated quotes.
"""
import argparse, json, os, re, sys, html, time, hashlib, subprocess, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta
from pathlib import Path

UA = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) trend_scout/2.0'}
POLITE_DELAY = 1.5
KICK_CH = 'https://kick.com/api/v1/channels/{}'
KICK_CLIPS = 'https://kick.com/api/v2/channels/{}/clips?sort=date&direction=desc&per_page=20'
KICK_POPULAR = 'https://kick.com/api/v2/livestreams?sort=viewer_count&direction=desc&per_page=25'
YT_RSS = 'https://www.youtube.com/feeds/videos.xml?channel_id={}'
GNEWS = 'https://news.google.com/rss/search?q={}&hl=en-US&gl=US&ceid=US:en'
BRAVE = 'https://api.search.brave.com/res/v1/web/search?q={}&count=10'

WATCHLIST = [
    {"name": "Adin Ross", "fame": 9, "kick": "adinross"},
    {"name": "N3on", "fame": 8, "kick": "n3on"},
    {"name": "Trainwreckstv", "fame": 8, "kick": "trainwreckstv"},
    {"name": "Vitaly", "fame": 7, "kick": "vitaly"},
    {"name": "Sneako", "fame": 7, "kick": "sneako"},
    {"name": "xQc", "fame": 9, "kick": "xqc", "twitch": "xqc"},
    {"name": "WestCol", "fame": 7, "kick": "westcol"},
    {"name": "Amouranth", "fame": 8, "kick": "amouranth", "twitch": "amouranth"},
    {"name": "StableRonaldo", "fame": 7, "kick": "stableronaldo"},
    {"name": "Lacy", "fame": 6, "kick": "lacy"},
    {"name": "Kai Cenat", "fame": 10, "twitch": "kaicenat"},
    {"name": "iShowSpeed", "fame": 10, "tags": ["youtube", "irl"]},
    {"name": "Plaqueboymax", "fame": 8, "twitch": "plaqueboymax", "tags": ["music"]},
    {"name": "DDG", "fame": 8, "tags": ["artist", "youtube"]},
    {"name": "Drake", "fame": 10, "tags": ["artist"]},
    {"name": "Travis Scott", "fame": 9, "tags": ["artist"]},
]

KEYWORDS = {
    "announce": (6, 8, ["announcement"]), "new series": (5, 9, ["series"]),
    "beef": (9, 8, ["beef"]), "drama": (8, 7, ["drama"]), " vs ": (7, 7, ["versus"]),
    "banned": (9, 8, ["ban"]), "suspend": (9, 8, ["ban"]), "arrest": (9, 9, ["legal"]),
    "quit": (7, 9, ["quit"]), "retir": (7, 8, ["retire"]), "breakup": (8, 7, ["split"]),
    "split": (7, 6, ["split"]), "responds": (7, 7, ["response"]), "fires back": (8, 7, ["response"]),
    "expos": (8, 8, ["expose"]), "leak": (7, 8, ["leak"]), "record": (6, 8, ["record"]),
    "world record": (6, 9, ["record"]), "subathon": (5, 8, ["event"]), "marathon": (5, 8, ["event"]),
    "finally": (5, 7, ["update"]), "returns": (5, 8, ["return"]), "trailer": (4, 8, ["trailer"]),
    "fight": (8, 8, ["boxing"]), "boxing": (7, 7, ["boxing"]), "tour": (5, 7, ["tour"]),
    "hospital": (8, 7, ["health"]), "hack": (7, 8, ["hack"]), "scam": (8, 7, ["scam"]),
    "apolog": (7, 6, ["apology"]), "collab": (5, 7, ["collab"]), "cheat": (8, 7, ["cheating"]),
}

# ---------------- net helpers ----------------
def http_get(url, timeout=20):
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode('utf-8', 'ignore')
    except Exception as e:
        print(f'  [warn] {url[:90]} -> {e}', file=sys.stderr)
        return None


def cached_get(url, cache_dir, ttl_h=6):
    cdir = Path(cache_dir)
    cdir.mkdir(parents=True, exist_ok=True)
    key = re.sub(r'[^a-z0-9]+', '-', url.lower())[:100] + '-' + hashlib.md5(url.encode()).hexdigest()[:8]
    p = cdir / (key + '.cache')
    if p.exists() and time.time() - p.stat().st_mtime < ttl_h * 3600:
        return p.read_text()
    time.sleep(POLITE_DELAY)
    raw = http_get(url)
    if raw is not None:
        p.write_text(raw)
    return raw


# ---------------- discovery sources (keyless) ----------------
def kick_channel(slug, cache):
    raw = cached_get(KICK_CH.format(slug), cache)
    if not raw:
        return None
    try:
        d = json.loads(raw)
    except Exception:
        return None
    live = d.get('livestream') or {}
    cats = live.get('categories') or [{}]
    return {'live': bool(live), 'live_title': live.get('session_title') if live else None,
            'category': cats[0].get('name') if live else None,
            'followers': d.get('followersCount', d.get('followers_count')), 'slug': slug}


def kick_clips(slug, cache):
    raw = cached_get(KICK_CLIPS.format(slug), cache)
    if not raw:
        return []
    try:
        d = json.loads(raw)
    except Exception:
        return []
    clips = d.get('data', d if isinstance(d, list) else [])
    out = []
    for c in clips if isinstance(clips, list) else []:
        out.append({'title': c.get('title'), 'views': c.get('views', 0),
                    'url': c.get('clip_url') or f"https://kick.com/{slug}"})
    return out


def kick_popular(cache, limit=25):
    raw = cached_get(KICK_POPULAR, cache)
    if not raw:
        return []
    try:
        d = json.loads(raw)
    except Exception:
        return []
    rows = d.get('data', d if isinstance(d, list) else [])
    out = []
    for r in rows if isinstance(rows, list) else []:
        ch = r.get('channel') or {}
        user = ch.get('user') or {}
        out.append({'streamer': user.get('username') or ch.get('slug'),
                    'title': r.get('session_title'), 'viewers': r.get('viewer_count', 0),
                    'url': f"https://kick.com/{ch.get('slug')}"})
    return out[:limit]


def parse_rss_items(xml):
    items = []
    for m in re.finditer(r'<entry>(.*?)</entry>|<item>(.*?)</item>', xml, re.S):
        body = m.group(1) or m.group(2)
        title = re.search(r'<title>(.*?)</title>', body, re.S)
        link = re.search(r'<link[^>]*href="([^"]+)"', body) or re.search(r'<link>(.*?)</link>', body, re.S)
        date = ''
        for tag in ('published', 'updated', 'pubDate'):
            dm = re.search(rf'<{tag}>(.*?)</{tag}>', body, re.S)
            if dm:
                date = dm.group(1).strip()
                break
        items.append({'title': html.unescape(title.group(1).strip()) if title else '',
                      'url': link.group(1).strip() if link else '', 'date': date})
    return items


def rss_date_ok(datestr, days):
    if not datestr:
        return True
    try:
        dt = datetime.fromisoformat(datestr.replace('Z', '+00:00'))
    except ValueError:
        try:
            import email.utils as eu
            dt = eu.parsedate_to_datetime(datestr)
        except Exception:
            return True
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - dt <= timedelta(days=days)


def youtube_recent(channel_id, days, cache):
    xml = cached_get(YT_RSS.format(channel_id), cache)
    return [i for i in parse_rss_items(xml)] if xml else []


def news_recent(query, days, cache):
    xml = cached_get(GNEWS.format(urllib.parse.quote(query)), cache)
    if not xml:
        return []
    return [i for i in parse_rss_items(xml) if rss_date_ok(i['date'], days)][:15]


def reddit_hot(sub, cache, limit=25):
    for host in ('www.reddit.com', 'old.reddit.com'):
        raw = cached_get(f'https://{host}/r/{sub}/hot.json?limit={limit}&t=day&raw_json=1', cache, ttl_h=1)
        if not raw:
            continue
        try:
            kids = json.loads(raw)['data']['children']
        except Exception:
            continue
        out = []
        for k in kids:
            d = k.get('data', {})
            out.append({'title': d.get('title', ''), 'score': d.get('score', 0),
                        'url': 'https://www.reddit.com' + d.get('permalink', ''),
                        'comments': d.get('num_comments', 0)})
        return out
    return []


def brave_find(query, key, count=10):
    req = urllib.request.Request(BRAVE.format(urllib.parse.quote(query)) + f'&count={count}',
                                 headers=dict(UA, **{'X-Subscription-Token': key, 'Accept': 'application/json'}))
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            d = json.load(r)
    except Exception as e:
        print(f'[warn] brave search failed: {e}', file=sys.stderr)
        return []
    return [{'title': w.get('title', ''), 'url': w.get('url', '')}
            for w in (d.get('web', {}).get('results', []))]


# ---------------- scoring ----------------
def story_score(title, fame, days_old):
    t = (' ' + title.lower() + ' ')
    conflict = curiosity = 2
    tags = set()
    for kw, (cf, cu, tg) in KEYWORDS.items():
        if kw in t:
            conflict = max(conflict, cf)
            curiosity = max(curiosity, cu)
            tags.update(tg)
    unexpected = 7 if conflict >= 8 else 5
    relevance = 10 if days_old <= 1 else (8 if days_old <= 3 else 6)
    arc = 7 if conflict >= 7 else 6
    scores = {'curiosity': curiosity, 'conflict': conflict, 'famous_people': fame,
              'unexpected': unexpected, 'visual_potential': 7,
              'current_relevance': relevance, 'story_arc': arc}
    return scores, sum(scores.values()), sorted(tags)


def guess_streamer(title):
    m = re.match(r"^([A-Z][\w']+(?: [A-Z][\w']+)?)\b", title.strip())
    return m.group(1) if m else None


# ---------------- scout ----------------
def scout(args):
    roster = json.load(open(args.roster)) if args.roster else WATCHLIST
    cache = Path(args.out) / '.cache'
    print(f'Scouting discovery + {len(roster)} watchlist, last {args.days} days...')
    cands, faces = [], {}
    known = {c['name'].lower() for c in roster}

    print('== discovery: kick popular ==')
    for row in kick_popular(str(cache)):
        if row['title'] and (row['viewers'] or 0) >= 2000:
            s, total, tags = story_score(row['title'], 7, 0)
            cands.append({'creator': row['streamer'] or '?', 'signal': 'kick-popular',
                          'title': f"{row['streamer']}: {row['title']} [{row['viewers']} viewers]",
                          'url': row['url'], 'scores': s, 'total': total, 'tags': tags})
    for sub in ('LivestreamFail', 'Kick', 'Twitch'):
        print(f'== discovery: r/{sub} ==')
        for p in reddit_hot(sub, str(cache)):
            if p['score'] < 300:
                continue
            s, total, tags = story_score(p['title'], 7, 1)
            g = guess_streamer(p['title'])
            if g and g.lower() not in known:
                faces[g] = faces.get(g, 0) + p['score']
            if total >= 42:
                cands.append({'creator': g or sub, 'signal': f'reddit-{sub}',
                              'title': f"{p['title']} [{p['score']} upvotes]",
                              'url': p['url'], 'scores': s, 'total': total, 'tags': tags})
    for q in ('Kick streamer', 'Twitch streamer drama', 'streamer announces'):
        print(f'== discovery: news "{q}" ==')
        for a in news_recent(q, args.days, str(cache))[:6]:
            s, total, tags = story_score(a['title'], 7, 2)
            if total >= 42:
                cands.append({'creator': guess_streamer(a['title']) or '?', 'signal': 'news',
                              'title': a['title'], 'url': a['url'],
                              'scores': s, 'total': total, 'tags': tags})
    for c in roster:
        name = c['name']
        print(f'== watchlist: {name} ==')
        sigs = []
        if c.get('kick'):
            ch = kick_channel(c['kick'], str(cache))
            if ch:
                print(f"  kick: live={ch['live']} followers={ch['followers']} {ch['live_title'] or ''}")
                if ch['live'] and ch['live_title']:
                    sigs.append(('kick-live', ch['live_title'], f"https://kick.com/{c['kick']}", 0))
            for cl in kick_clips(c['kick'], str(cache))[:10]:
                sigs.append(('kick-clip', cl['title'] or '', cl['url'], 1))
        if c.get('youtube_channel_id'):
            for v in youtube_recent(c['youtube_channel_id'], args.days, str(cache)):
                sigs.append(('youtube', v['title'], v['url'], 1))
        for a in news_recent(f'"{name}" streamer', args.days, str(cache))[:8]:
            sigs.append(('news', a['title'], a['url'], 2))
        for src, title, url, age in sigs:
            if not title:
                continue
            s, total, tags = story_score(title, c.get('fame', 6), age)
            if total >= 42:
                cands.append({'creator': name, 'signal': src, 'title': title, 'url': url,
                              'scores': s, 'total': total, 'tags': tags})
                print(f'  + [{total}] {title[:100]}')
    seen, uniq = set(), []
    for c in sorted(cands, key=lambda x: -x['total']):
        k = re.sub(r'\W+', '', c['title'].lower())[:80]
        if k not in seen:
            seen.add(k)
            uniq.append(c)
    top = uniq[:args.top]
    new_faces = sorted(faces.items(), key=lambda x: -x[1])[:10]
    stamp = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / f'scout_{stamp}.json').write_text(json.dumps(
        {'date': stamp, 'watchlist': [c['name'] for c in roster],
         'new_faces': [{'guess': g, 'heat': h} for g, h in new_faces],
         'candidates': top}, indent=1))
    md = [f'# Scout brief {stamp}', '', f'{len(uniq)} scored signals, top {len(top)}.',
          'New-face guesses (promote to roster if real): ' +
          (', '.join(f'{g} ({h})' for g, h in new_faces) or 'none'), '',
          '**RULES: real footage only. Approval gate before any push.**',
          'Check EPISODES.json topic_keys/source URLs before reserving - never recreate',
          'a covered story (e.g. 04 already did the Riot boosting ban).', '']
    for i, c in enumerate(top):
        md += [f"## {i}. [{c['total']}] {c['creator']} — {c['title']}",
               f"Signal: {c['signal']} · tags: {', '.join(c['tags'])}", c['url'],
               'Verify: primary source? clean AV (own channel, no watermarks)? complete thoughts?',
               f'Next: `build --brief ... --pick {i} --episode NN`', '']
    (outdir / f'scout_{stamp}.md').write_text('\n'.join(md))
    print(f'Wrote {outdir}/scout_{stamp}.json + .md ({len(top)} top)')


# ---------------- eyes (download powers, no X API) ----------------
def eyes_download(url, out, fmt='best[height<=720]/best', sections=None, cookies=None, timeout=900):
    cmd = ['yt-dlp', '--no-progress', '-f', fmt, '--merge-output-format', 'mp4']
    for s in sections or []:
        cmd += ['--download-sections', s]
    if cookies:
        cmd += ['--cookies', cookies]
    cmd += ['-o', out, url]
    print('eyes:', ' '.join(cmd[:4]), '...', url[:80])
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        print(r.stderr[-1500:], file=sys.stderr)
        raise SystemExit(f'eyes download failed for {url[:80]}')
    if not Path(out).exists():
        raise SystemExit(f'eyes: expected file missing: {out}')
    return out


def eyes_cli(a):
    if a.find:
        key = a.brave_key or os.environ.get('BRAVE_API_KEY')
        if not key:
            raise SystemExit('eyes --find needs BRAVE_API_KEY (free tier) via --brave-key or env')
        for hit in brave_find(a.find, key):
            print(f"{hit['title'][:110]}\n  {hit['url']}")
        return
    if not a.get:
        raise SystemExit('eyes needs --get URL or --find QUERY')
    eyes_download(a.get, a.o, sections=a.sections, cookies=a.cookies)
    print('saved:', a.o)


# ---------------- build (1:1 scaffold) ----------------
BUILD_CHECKLIST = """## Production checklist (1:1 with this pipeline)
1. Reserve: update EPISODES.json (reserved); commit+push BEFORE production.
2. Hunt real footage with eyes: creator's own Twitch/Kick VODs, own YouTube/X posts.
   REJECT watermarked re-uploads and meme edits. No AI visuals, ever.
3. Transcribe locate-windows, pick COMPLETE thoughts, no mid-sentence cuts.
4. Script deadpan bridges; words ~= (58 - dialogue_s) x 2.4. One locked voice.
5. make --do run: live + muted B-roll, 720x1280/30, white 52px captions only,
   ducked bed, PROBE frames first, then full render + QA.
6. APPROVAL GATE: show MP4 in chat, get explicit approval. Then finish+audit+push.
"""


def make_template(ep, pick):
    slug = re.sub(r'[^a-z0-9]+', '_', pick['title'].lower())[:50].strip('_')
    return {
        "episode": ep, "title": pick['title'][:90] + ' — <add audience question>',
        "out": f"{ep}_{slug}.mp4",
        "crop": [470, 40, 852, 720],
        "crop_note": "TODO: probe source frames, exclude chat/watermarks/counters, then set box",
        "fps": 30, "music_slot": int(ep) % 4,
        "sources": [{"url": pick['url'], "file": f"{ep}_source_main.mp4",
                     "format": "best[height<=720]/best", "sections": ["*START-END"],
                     "note": "TODO: replace with own-channel AV + verified windows"}],
        "live": [{"file": f"{ep}_source_main.mp4", "start": 0.0, "end": 8.0,
                  "drop": 0, "pad": 0.12, "note": "TODO: complete thought, file seconds"}],
        "broll": {"1": [f"{ep}_source_main.mp4", 20.0, 35.0]},
        "narration": ["TODO bridge one (~15 words).", "TODO bridge two + question."],
        "tts": {"provider": "edge", "voice": "en-US-GuyNeural", "rate": "-5%",
                "openai_voice": "onyx", "eleven_voice_id": "",
                "wavs": [], "note": "wavs (if set) win over TTS; one voice forever"},
        "caption_fixes": {},
    }


def build(args):
    brief = json.load(open(args.brief))
    pick = brief['candidates'][args.pick]
    ep = args.episode.zfill(2)
    root = Path(args.dir)
    root.mkdir(parents=True, exist_ok=True)
    (root / f'{ep}_sources.json').write_text(json.dumps([{
        "url": pick['url'], "filename": f"{ep}_source_main.mp4",
        "format": "best[height<=720]/best", "sections": ["*START-END"],
        "role": "PRIMARY HUNT: creator's own AV + verified windows.",
        "dialogue_ranges": []}], indent=2) + '\n')
    (root / f'{ep}_narration.txt').write_text(
        '1. <bridge one: who/what, ~15 words>\n\n2. <bridge two + specific question>\n')
    (root / f'{ep}_RESEARCH.md').write_text('\n'.join([
        f'# Episode {ep} — {pick["creator"]}: {pick["title"]}',
        f"Research date: {datetime.now(timezone.utc).date()}. Signal: {pick['signal']} ({pick['url']})",
        f"Story score: {pick['total']} {pick['scores']}", '',
        '## Findings and editorial choice', '<verify + audience question>', '',
        '## Primary audiovisual evidence', '<own-channel AV; windows + complete thoughts>', '',
        '## Voice disclosure', '<locked or approved substitute + date>', '',
        '## Visual and technical QA', '<after render>', '',
        '## Rights', '<no licenses verified, no monetization guarantee>', '',
        BUILD_CHECKLIST]))
    (root / f'make_{ep}.json').write_text(json.dumps(make_template(ep, pick), indent=2) + '\n')
    print(f'Scaffolded {ep}_sources/narration/RESEARCH + make_{ep}.json in {root}')
    print('Next: verify AV, fill make JSON (windows/crop/narration), make --do run, QA, APPROVAL, push.')


# ---------------- make (the machine: same style renderer) ----------------
CAP = dict(font_size=52, top_y=948, center_x=330, max_w=550, line_step=61,
           font='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')
PROGRESSIONS = [
    [[42, 49, 54, 57], [38, 45, 50, 54], [41, 48, 53, 57], [36, 43, 50, 55]],
    [[40, 47, 52, 55], [36, 43, 48, 55], [43, 50, 55, 59], [38, 45, 53, 57]],
    [[45, 52, 55, 59], [41, 48, 52, 55], [38, 45, 50, 53], [43, 50, 53, 57]],
    [[36, 43, 50, 53], [41, 48, 55, 60], [38, 45, 52, 57], [43, 50, 57, 60]],
]


def tts_lines(lines, cfg, workdir):
    """Synthesize narration lines -> list of wav paths. wavs list wins if set."""
    wavs = [str(Path(workdir) / w) for w in cfg.get('wavs', [])]
    if wavs:
        assert len(wavs) == len(lines), 'wavs count must match narration lines'
        return wavs
    prov = cfg.get('provider', 'edge')
    outs = []
    if prov == 'edge':
        import asyncio
        import edge_tts
        async def gen(text, voice, rate, mp3):
            await edge_tts.Communicate(text, voice, rate=rate).save(mp3)
        for i, line in enumerate(lines, 1):
            mp3 = str(Path(workdir) / f'narr{i}.mp3')
            outs.append(str(Path(workdir) / f'narr{i}.wav'))
            asyncio.run(gen(line, cfg.get('voice', 'en-US-GuyNeural'), cfg.get('rate', '-5%'), mp3))
            subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', mp3, '-ar', '44100',
                            '-ac', '1', '-c:a', 'pcm_s16le', outs[-1]], check=True)
        return outs
    if prov == 'openai':
        key = os.environ.get('OPENAI_API_KEY')
        assert key, 'OPENAI_API_KEY required'
        for i, line in enumerate(lines, 1):
            body = json.dumps({'model': 'tts-1', 'voice': cfg.get('openai_voice', 'onyx'),
                               'input': line, 'response_format': 'mp3'}).encode()
            req = urllib.request.Request('https://api.openai.com/v1/audio/speech', data=body,
                                         headers={'Authorization': f'Bearer {key}',
                                                  'Content-Type': 'application/json'})
            mp3 = str(Path(workdir) / f'narr{i}.mp3')
            with urllib.request.urlopen(req, timeout=120) as r, open(mp3, 'wb') as f:
                f.write(r.read())
            outs.append(str(Path(workdir) / f'narr{i}.wav'))
            subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', mp3, '-ar', '44100',
                            '-ac', '1', '-c:a', 'pcm_s16le', outs[-1]], check=True)
        return outs
    if prov == 'eleven':
        key = os.environ.get('ELEVEN_API_KEY')
        vid = cfg.get('eleven_voice_id')
        assert key and vid, 'ELEVEN_API_KEY + eleven_voice_id required'
        for i, line in enumerate(lines, 1):
            body = json.dumps({'text': line, 'model_id': 'eleven_multilingual_v2'}).encode()
            req = urllib.request.Request(
                f'https://api.elevenlabs.io/v1/text-to-speech/{vid}', data=body,
                headers={'xi-api-key': key, 'Content-Type': 'application/json',
                         'Accept': 'audio/mpeg'})
            mp3 = str(Path(workdir) / f'narr{i}.mp3')
            with urllib.request.urlopen(req, timeout=120) as r, open(mp3, 'wb') as f:
                f.write(r.read())
            outs.append(str(Path(workdir) / f'narr{i}.wav'))
            subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', mp3, '-ar', '44100',
                            '-ac', '1', '-c:a', 'pcm_s16le', outs[-1]], check=True)
        return outs
    raise SystemExit(f'unknown tts provider: {prov} (edge/openai/eleven or wavs)')


def asr_words(audio_wav, model_name='base.en'):
    from faster_whisper import WhisperModel
    m = WhisperModel(model_name, device='cpu', compute_type='int8')
    segs, _ = m.transcribe(audio_wav, language='en', beam_size=3,
                           word_timestamps=True, vad_filter=True)
    words = []
    for s in segs:
        for w in (s.words or []):
            if w.word.strip():
                words.append({'text': w.word.strip(), 'start': round(w.start, 2),
                              'end': round(w.end, 2)})
    return words


def render_short(cfg, workdir, probe_only=False):
    """Generic 1:1 renderer. cfg: make.json dict. Returns (mp4_path, report)."""
    import wave
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    import cv2
    W, H, SR, FPS = 720, 1280, 44100, cfg.get('fps', 30)
    work = Path(workdir)
    texts = cfg['narration']
    assert len(texts) == len(cfg['broll']), 'narration lines must match broll entries'
    # narration audio
    narr_wavs = tts_lines(texts, cfg.get('tts', {}), work)
    lengths = {}
    for i, f in enumerate(narr_wavs, 1):
        with wave.open(f) as w:
            lengths[i] = w.getnframes() / w.getframerate()
    # live windows -> exact starts from ASR word timings
    live = []
    for li, L in enumerate(cfg['live']):
        src = str(work / L['file'])
        assert Path(src).exists(), f'missing source: {src}'
        wav = str(work / f'_live{li}.wav')
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-ss', str(L['start']), '-i', src,
                        '-t', str(L['end'] - L['start']), '-ar', '16000', '-ac', '1',
                        '-f', 'wav', wav], check=True)
        words = L.get('words') or asr_words(wav)
        (work / f'_words{li}.json').write_text(json.dumps(words, indent=1))
        w0 = words[L.get('drop', 0)]
        st = L['start'] + w0['start'] - L.get('pad', 0.12)
        live.append(dict(words=words[L.get('drop', 0):], file=L['file'], start=st,
                         dur=L['end'] - st))
    # timeline: live, vo, live, vo ... (vo i uses broll[i])
    segs, total, words, n_idx = [], 0.0, [], 1
    order = []
    for li in range(len(live)):
        order.append(('live', li))
        if str(n_idx) in cfg['broll']:
            order.append(('vo', n_idx))
            n_idx += 1
    while str(n_idx) in cfg['broll']:
        order.append(('vo', n_idx))
        n_idx += 1
    for mode, idx in order:
        if mode == 'live':
            d = live[idx]
            segs.append(dict(mode=mode, li=idx, start=total, dur=d['dur']))
            total += d['dur']
        else:
            f, bs, be = cfg['broll'][str(idx)]
            segs.append(dict(mode=mode, n=idx, file=f, bs=bs, be=be, start=total,
                             dur=lengths[idx]))
            total += lengths[idx]
    import math
    D = math.ceil(total * FPS) / FPS
    fixes = cfg.get('caption_fixes', {})

    def fix(t):
        m = re.match(r'^([^A-Za-z]*)([A-Za-z]+)([^A-Za-z]*)$', t)
        if m and m.group(2).lower() in fixes:
            return m.group(1) + fixes[m.group(2).lower()] + m.group(3)
        return t
    for i in range(1, len(texts) + 1):
        ws = texts[i - 1].split()
        tot = sum(len(x) + 1 for x in ws)
        t = 0
        s = next(s for s in segs if s['mode'] == 'vo' and s['n'] == i)
        for x in ws:
            d = lengths[i] * (len(x) + 1) / tot
            words.append(dict(text=x, start=t + s['start'], end=t + d + s['start']))
            t += d
    # live caption offsets: word times are relative to the extracted window; the seg
    # audio starts `pad` seconds before words[0], so shift by (words[0] - pad).
    live_word_list = []
    for s in [x for x in segs if x['mode'] == 'live']:
        L = cfg['live'][s['li']]
        d = live[s['li']]
        pad = L.get('pad', 0.12)
        w0 = d['words'][0]['start']
        for w in d['words']:
            live_word_list.append(dict(text=fix(w['text']),
                                       start=w['start'] - w0 + pad + s['start'],
                                       end=w['end'] - w0 + pad + s['start']))
    words = sorted(words + live_word_list, key=lambda w: w['start'])
    # audio
    speech = np.zeros(round(D * SR))
    for j, s in enumerate(segs):
        if s['mode'] == 'vo':
            cmd = ['ffmpeg', '-y', '-i', narr_wavs[s['n'] - 1], '-vn', '-af',
                   'highpass=f=85,lowpass=f=8500,loudnorm=I=-17:TP=-2:LRA=7',
                   '-ar', str(SR), '-ac', '1', str(work / f'_chunk{j}.wav')]
        else:
            d = live[s['li']]
            cmd = ['ffmpeg', '-y', '-ss', str(d['start']), '-i', str(work / d['file']),
                   '-t', str(s['dur']), '-vn', '-af',
                   'highpass=f=85,lowpass=f=8500,loudnorm=I=-17:TP=-2:LRA=7',
                   '-ar', str(SR), '-ac', '1', str(work / f'_chunk{j}.wav')]
        subprocess.run(cmd, capture_output=True, check=True)
        with wave.open(str(work / f'_chunk{j}.wav')) as w:
            a = np.frombuffer(w.readframes(w.getnframes()), dtype='<i2').astype(float) / 32768
        ix = round(s['start'] * SR)
        n = min(len(a), len(speech) - ix)
        a = a[:n]
        fade = min(180, n // 4)
        a[:fade] *= np.linspace(0, 1, fade)
        a[-fade:] *= np.linspace(1, 0, fade)
        speech[ix:ix + n] = a
    # bed (rotating progression, same family as episodes)
    prog = PROGRESSIONS[cfg.get('music_slot', 0) % 4]
    beat = 60 / 62
    music = np.zeros(round(D * SR))

    def add(st, a):
        i = int(st * SR)
        n = min(len(a), len(music) - i)
        if i >= 0 and n > 0:
            music[i:i + n] += a[:n]

    def hz(m):
        return 440 * 2 ** ((m - 69) / 12)

    def piano(m, dur, amp):
        t = np.arange(int(dur * SR)) / SR
        f = hz(m)
        a = np.zeros(len(t))
        for h, wt in [(1, 1), (2, .27), (3, .14), (4, .05), (6, .015)]:
            a += wt * np.sin(2 * np.pi * f * h * (1 + .00004 * h) * t) * np.exp(-t * (.92 + .24 * h))
        a *= np.minimum(1, t / .012) * np.minimum(1, (dur - t) / .2)
        return amp * a
    for bar, st in enumerate(np.arange(0, D, beat * 8)):
        chord = prog[bar % 4]
        dur = beat * 10
        t = np.arange(int(dur * SR)) / SR
        env = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 1.8
        pad = np.zeros(len(t))
        for midi in chord:
            f = hz(midi)
            pad += (np.sin(2 * np.pi * f * t + .03 * np.sin(2 * np.pi * .12 * t)) +
                    .3 * np.sin(2 * np.pi * f * 1.0017 * t) +
                    .07 * np.sin(2 * np.pi * 2 * f * t)) / len(chord)
        add(st, .088 * pad * env)
        for off, note, vel in [(0, chord[0] + 12, .09), (2.5, chord[2] + 12, .06),
                               (5, chord[3] + 12, .052), (6.5, chord[1] + 12, .04)]:
            a = piano(note, 4.4, vel)
            add(st + off * beat, a)
            add(st + off * beat + .41, a * .17)
            add(st + off * beat + .83, a * .085)
        t2 = np.arange(1.6 * SR) / SR
        add(st, .015 * np.sin(2 * np.pi * hz(chord[0] - 12) * t2) *
            (1 - np.exp(-t2 * 7)) * np.exp(-t2 * 3))
    music *= np.minimum(1, np.arange(len(music)) / SR / 1.5)
    block = 441
    levels = np.array([np.sqrt(np.mean(speech[i:i + block] ** 2))
                       for i in range(0, len(speech), block)])
    gain = np.where(levels > .014, .3, .6)
    smooth, v = [], .25
    for x in gain:
        v += (x - v) * (.7 if x < v else .065)
        smooth.append(v)
    music *= np.repeat(smooth, block)[:len(speech)]
    mix = speech + music
    mix[-int(.5 * SR):] *= np.linspace(1, 0, int(.5 * SR))
    mix = np.clip(mix, -.97, .97)
    with wave.open(str(work / '_mix.wav'), 'w') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix * 32767).astype('<i2').tobytes())
    # captions (identical rules to episodes)
    groups, g = [], []
    for w in words:
        if g and (len(g) >= 5 or w['start'] - g[-1]['end'] > .35 or
                  any(g[-1]['start'] < z['start'] <= w['start'] for z in segs)):
            groups.append(g)
            g = []
        g.append(w)
        if w['text'].endswith(('.', '?', '!')):
            groups.append(g)
            g = []
    if g:
        groups.append(g)
    fonts = {}

    def font(n):
        if n not in fonts:
            fonts[n] = ImageFont.truetype(CAP['font'], n)
        return fonts[n]

    def cap_lines(s):
        d = ImageDraw.Draw(Image.new('RGB', (1, 1)))
        f = font(CAP['font_size'])
        lines, line = [], ''
        for word in s.split():
            trial = (line + ' ' + word).strip()
            if line and d.textlength(trial, font=f) > CAP['max_w']:
                lines.append(line)
                line = word
            else:
                line = trial
        if line:
            lines.append(line)
        return lines

    def caption(im, s):
        d = ImageDraw.Draw(im)
        f = font(CAP['font_size'])
        lines = cap_lines(s)
        assert len(lines) <= 2, ('Caption exceeds two lines', s)
        y = CAP['top_y']
        for line in lines:
            x = CAP['center_x'] - d.textlength(line, font=f) / 2
            d.text((x, y), line, font=f, fill='white', stroke_width=5, stroke_fill='black')
            d.text((x, y), line, font=f, fill='white', stroke_width=1, stroke_fill='white')
            y += CAP['line_step']
    checked = []
    for group in groups:
        if len(cap_lines(' '.join(w['text'] for w in group))) <= 2:
            checked.append(group)
        else:
            parts = [group]
            while any(len(cap_lines(' '.join(w['text'] for w in p))) > 2 for p in parts) and \
                    max(len(p) for p in parts) > 1:
                new = []
                for p in parts:
                    if len(cap_lines(' '.join(w['text'] for w in p))) > 2 and len(p) > 1:
                        c = max(1, len(p) // 2)
                        new.extend([p[:c], p[c:]])
                    else:
                        new.append(p)
                parts = new
            checked.extend(parts)
    groups = []
    for g in checked:
        if groups and g[-1]['end'] - g[0]['start'] < .35 and \
           g[0]['start'] - groups[-1][-1]['end'] < .3 and \
           not any(groups[-1][0]['start'] < z['start'] <= g[0]['start'] for z in segs) and \
           len(cap_lines(' '.join(w['text'] for w in groups[-1] + g))) <= 2:
            groups[-1].extend(g)
        else:
            groups.append(g)
    assert all(len(cap_lines(' '.join(w['text'] for w in g))) <= 2 for g in groups)
    # video
    def cover(pic, w, h):
        iw, ih = pic.size
        scale = max(w / iw, h / ih)
        cw, ch = w / scale, h / scale
        return pic.crop(((iw - cw) / 2, (ih - ch) / 2, (iw + cw) / 2, (ih + ch) / 2)) \
            .resize((w, h), Image.Resampling.BICUBIC)
    caps, prev, cache = {}, {}, {}

    def get(srcfile, t):
        if srcfile not in caps:
            caps[srcfile] = cv2.VideoCapture(str(work / srcfile))
            prev[srcfile] = -999
        c = caps[srcfile]
        idx = int(t * c.get(cv2.CAP_PROP_FPS))
        if prev[srcfile] == idx:
            return cache[srcfile].copy()
        if idx < prev[srcfile] or idx > prev[srcfile] + 5:
            c.set(cv2.CAP_PROP_POS_FRAMES, idx)
            prev[srcfile] = idx - 1
        while prev[srcfile] < idx:
            ok, f = c.read()
            prev[srcfile] += 1
            if ok:
                cache[srcfile] = Image.fromarray(cv2.cvtColor(f, cv2.COLOR_BGR2RGB))
        return cache[srcfile].copy()
    x0, y0, x1, y1 = cfg['crop']

    def frame(t):
        s = max((s for s in segs if s['start'] <= t), key=lambda s: s['start'])
        local = min(s['dur'] - .01, max(0, t - s['start']))
        if s['mode'] == 'live':
            d = live[s['li']]
            pic = get(d['file'], d['start'] + local)
        else:
            span = s['be'] - s['bs']
            pic = get(s['file'], s['bs'] + (local % span))
        im = cover(pic.crop((x0, y0, x1, y1)), W, H)
        overlay = Image.new('RGBA', (W, H))
        od = ImageDraw.Draw(overlay)
        for y in range(900, H):
            od.line((0, y, W, y), fill=(0, 0, 0, int(175 * (y - 900) / (H - 900))))
        im = Image.alpha_composite(im.convert('RGBA'), overlay).convert('RGB')
        g = next((g for g in groups if g[0]['start'] <= t < min(g[-1]['end'] + .08, D)), None)
        if g:
            caption(im, ' '.join(w['text'] for w in g))
        return im
    for t in [round(x, 2) for x in np.linspace(2, max(3, D - 2), 8)]:
        if t < D:
            frame(t).save(work / f'_qc_{t}.jpg')
    if probe_only:
        return None, {'duration': D, 'segs': len(segs), 'captions': len(groups)}
    def stamp(t):
        ms = round(t * 1000)
        return f'{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}'
    (work / '_out.srt').write_text('\n\n'.join(
        f'{i + 1}\n{stamp(g[0]["start"])} --> {stamp(g[-1]["end"])}\n' + ' '.join(w['text'] for w in g)
        for i, g in enumerate(groups)))
    out = work / cfg['out']
    cmd = ['ffmpeg', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '720x1280',
           '-r', str(FPS), '-i', '-', '-i', str(work / '_mix.wav'), '-c:v', 'libx264',
           '-preset', 'fast', '-crf', '23', '-pix_fmt', 'yuv420p', '-c:a', 'aac',
           '-b:a', '192k', '-t', str(D), '-movflags', '+faststart', str(out)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=open(work / '_render.log', 'w'))
    for i in range(round(D * FPS)):
        p.stdin.write(frame(i / FPS).tobytes())
    p.stdin.close()
    assert p.wait() == 0
    # QA
    q = subprocess.run(['ffprobe', '-v', 'error', '-show_entries',
                        'stream=width,height,codec_name', '-show_entries',
                        'format=duration,size', '-of', 'default=noprint_wrappers=1',
                        str(out)], capture_output=True, text=True)
    vd = subprocess.run(['ffmpeg', '-v', 'info', '-i', str(out), '-af', 'volumedetect',
                         '-vn', '-f', 'null', '-'], capture_output=True, text=True)
    mean = re.search(r'mean_volume: ([\-\d.]+) dB', vd.stderr)
    peak = re.search(r'max_volume: ([\-\d.]+) dB', vd.stderr)
    report = {'file': cfg['out'], 'duration': D, 'segments': len(segs),
              'captions': len(groups), 'ffprobe': q.stdout.strip().replace('\n', ' '),
              'mean_db': mean.group(1) if mean else '?',
              'peak_db': peak.group(1) if peak else '?'}
    (work / '_report.json').write_text(json.dumps(report, indent=1))
    return str(out), report


def make_selftest(workdir):
    """Hermetic end-to-end test: synthetic sources + sine narration. No network."""
    import wave
    import numpy as np
    work = Path(workdir)
    work.mkdir(parents=True, exist_ok=True)
    for name in ('srcA.mp4', 'srcB.mp4'):
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'lavfi', '-i',
                        'testsrc2=s=1280x720:r=30:d=20', '-f', 'lavfi', '-i',
                        'sine=frequency=440:duration=20', '-pix_fmt', 'yuv420p',
                        '-c:a', 'aac', '-shortest', str(work / name)], check=True)
    for i, f in enumerate((330, 392), 1):
        t = np.arange(3 * 44100) / 44100
        a = (0.3 * np.sin(2 * np.pi * f * t)).astype(float)
        with wave.open(str(work / f'n{i}.wav'), 'w') as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(44100)
            w.writeframes((a * 32767).astype('<i2').tobytes())
    cfg = {"episode": "00", "out": "selftest.mp4", "crop": [430, 0, 850, 720],
           "music_slot": 0,
           "live": [{"file": "srcA.mp4", "start": 1.0, "end": 5.0, "drop": 0, "pad": 0.1,
                     "words": [{"text": "Hello", "start": 0.2, "end": 0.8},
                               {"text": "world.", "start": 0.9, "end": 1.6}]},
                    {"file": "srcB.mp4", "start": 2.0, "end": 6.0, "drop": 0, "pad": 0.1,
                     "words": [{"text": "Second", "start": 0.2, "end": 0.8},
                               {"text": "clip.", "start": 0.9, "end": 1.6}]}],
           "broll": {"1": ["srcA.mp4", 8.0, 18.0], "2": ["srcB.mp4", 8.0, 18.0]},
           "narration": ["First test line here.", "Second line plus question?"],
           "tts": {"wavs": ["n1.wav", "n2.wav"]}, "caption_fixes": {}}
    (work / 'make_00.json').write_text(json.dumps(cfg, indent=1))
    out, rep = render_short(cfg, work)
    assert Path(out).exists() and Path(out).stat().st_size > 100000, 'selftest mp4 missing/small'
    assert 13 <= rep['duration'] <= 15, rep
    print('SELFTEST OK:', json.dumps(rep))
    return rep


def make_cli(a):
    if a.do == 'selftest':
        make_selftest(a.dir or '/tmp/selftest')
    elif a.do == 'init':
        brief = json.load(open(a.brief))
        pick = brief['candidates'][a.pick]
        ep = a.episode.zfill(2)
        Path(f'make_{ep}.json').write_text(json.dumps(make_template(ep, pick), indent=2) + '\n')
        print(f'wrote make_{ep}.json — fill windows/crop/narration, then make --do run')
    elif a.do == 'run':
        cfg = json.load(open(a.make))
        blob = json.dumps(cfg)
        todos = sorted(set(re.findall(r'TODO[^"]*|START-END', blob)))
        assert not todos, f'fill make.json TODOs first: {todos}'
        work = Path(a.dir or '.')
        for s in cfg.get('sources', []):
            if s.get('download', True) and not (work / s['file']).exists():
                eyes_download(s['url'], str(work / s['file']),
                              fmt=s.get('format', 'best[height<=720]/best'),
                              sections=s.get('sections'), cookies=a.cookies)
        out, rep = render_short(cfg, work, probe_only=bool(a.probe))
        if out:
            print('DONE:', out, json.dumps(rep))
        else:
            print('PROBE ONLY:', json.dumps(rep))
    else:
        raise SystemExit('make --do {init,run,selftest}')


def main():
    p = argparse.ArgumentParser(description='trend_scout: shorts machine (scout/build/eyes/make)')
    sub = p.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('scout')
    s.add_argument('--roster')
    s.add_argument('--days', type=int, default=7)
    s.add_argument('--top', type=int, default=5)
    s.add_argument('--out', default='briefs')
    b = sub.add_parser('build')
    b.add_argument('--brief', required=True)
    b.add_argument('--pick', type=int, default=0)
    b.add_argument('--episode', required=True)
    b.add_argument('--dir', default='.')
    e = sub.add_parser('eyes')
    e.add_argument('--get')
    e.add_argument('--find')
    e.add_argument('-o', default='eyes_out.mp4')
    e.add_argument('--sections', action='append')
    e.add_argument('--cookies')
    e.add_argument('--brave-key')
    m = sub.add_parser('make')
    m.add_argument('--do', required=True)
    m.add_argument('--brief')
    m.add_argument('--pick', type=int, default=0)
    m.add_argument('--episode')
    m.add_argument('--make')
    m.add_argument('--dir')
    m.add_argument('--cookies')
    m.add_argument('--probe', action='store_true')
    sub.add_parser('roster')
    a = p.parse_args()
    if a.cmd == 'scout':
        scout(a)
    elif a.cmd == 'build':
        build(a)
    elif a.cmd == 'eyes':
        eyes_cli(a)
    elif a.cmd == 'make':
        make_cli(a)
    elif a.cmd == 'roster':
        print(json.dumps(WATCHLIST, indent=1))


if __name__ == '__main__':
    main()
