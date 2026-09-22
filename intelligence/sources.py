#!/usr/bin/env python3
"""research/sources.py — källintag: HTTP, Wikipedia, Google News, Wikimedia,
YouTube-sök (via yt-dlp) + nedladdning. Allt med cache, retries och licens-tagg.

Hierarki av källor (TIERS) definieras i research/claims.py, men licens/typ
registreras här så fort en källa hämtas.
"""
import os, re, json, time, hashlib, subprocess, sys

try:
    import requests
except Exception:  # pragma: no cover
    requests = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, ".cache", "http")
os.makedirs(CACHE, exist_ok=True)

UA = ("Mozilla/5.0 (compatible; sunny_auto/1.0; documentary research; "
      "educational use)")

# ---------- licens-tier (till claims.py) ----------
LICENSE_TIERS = {
    # Tier 1 = fri att använda (PD / CC-BY / CC0 etc.)
    "pd": 1, "public domain": 1, "cc0": 1, "cc-by": 1, "cc by": 1,
    "cc-by-sa": 1, "cc by-sa": 1, "cc-by 3.0": 1, "cc-by 4.0": 1,
    # Tier 2 = använd med attribution/villkor
    "cc-by-2.0": 2, "cc-by-sa-2.0": 2, "cc-by-sa-3.0": 2, "cc-by-sa-4.0": 2,
    "gfdl": 2,
    # Tier 3 = granska noga
    "cc-by-nc": 3, "cc-by-nc-sa": 3, "cc-by-nd": 3,
}

def slugify(s):
    s = str(s).lower()
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s[:48] or "topic"

def _cache_path(url):
    return os.path.join(CACHE, hashlib.md5(url.encode()).hexdigest() + ".bin")

def get(url, params=None, headers=None, timeout=20, retries=2, binary=False,
        json_out=False, use_cache=True):
    """Hämtar URL med backoff + disk-cache. Returnerar bytes/text/json/dict."""
    if not requests:
        raise RuntimeError("requests saknas — pip install requests")
    q = url + "?" + "&".join(f"{k}={v}" for k, v in (params or {}).items())
    cp = _cache_path(q)
    if use_cache and os.path.exists(cp) and not binary:
        try:
            data = open(cp, "rb").read()
            return json.loads(data) if json_out else data.decode("utf-8", "replace")
        except Exception:
            pass
    h = {"User-Agent": UA, "Accept": "application/json,text/html,*/*"}
    h.update(headers or {})
    last = None
    for i in range(retries + 1):
        try:
            r = requests.get(url, params=params, headers=h, timeout=timeout)
            if r.status_code == 200:
                if not binary:
                    with open(cp, "wb") as f:
                        f.write(r.content)
                    return r.json() if json_out else r.text
                return r.content
            last = r.status_code
        except Exception as e:
            last = e
        time.sleep(1.2 * (i + 1))
    raise RuntimeError(f"HTTP misslyckades {url}: {last}")

def wikipedia_search(topic, limit=6):
    out = get("https://en.wikipedia.org/w/api.php",
              params={"action": "opensearch", "search": topic, "limit": str(limit),
                      "namespace": "0", "format": "json", "redirects": "resolve"},
              json_out=True)
    try:
        return {"titles": out[1], "descriptions": out[2], "urls": out[3]}
    except Exception:
        return {"titles": [], "descriptions": [], "urls": []}

def wikipedia_summary(title):
    t = title.replace(" ", "_")
    j = get(f"https://en.wikipedia.org/api/rest_v1/page/summary/{t}",
            json_out=True)
    return {"title": j.get("title", title),
            "extract": j.get("extract", ""),
            "url": j.get("content_urls", {}).get("desktop", {}).get("page", "")}

def wikipedia_extract(title):
    """Fullständig platt-text via action=query&prop=extracts (max 90k tecken)."""
    j = get("https://en.wikipedia.org/w/api.php",
            params={"action": "query", "prop": "extracts", "explaintext": "1",
                    "titles": title, "format": "json",
                    "exintro": "0", "redirects": "1"},
            json_out=True)
    pages = j.get("query", {}).get("pages", {})
    for p in pages.values():
        return p.get("extract", "")
    return ""

def news_rss(query, hl="en-US", count=12):
    """Google News RSS → lista av {title, source, url, published}."""
    xml = get("https://news.google.com/rss/search",
              params={"q": query, "hl": hl, "gl": "US", "ceid": "US:en"})
    import xml.etree.ElementTree as ET
    items = []
    try:
        root = ET.fromstring(xml)
        for it in root.iter("item"):
            items.append({
                "title": (it.findtext("title") or "").strip(),
                "source": (it.findtext("source") or "").strip(),
                "url": (it.findtext("link") or "").strip(),
                "published": (it.findtext("pubDate") or "").strip(),
            })
    except Exception:
        pass
    return items[:count]

def wikimedia_search(query, limit=10, width=1280):
    """Sök bilder/filer på Wikimedia Commons → lista av metadata."""
    j = get("https://commons.wikimedia.org/w/api.php",
            params={"action": "query", "generator": "search",
                    "gsrsearch": query, "gsrnamespace": "6", "gsrlimit": str(limit),
                    "prop": "imageinfo", "iiprop": "url|size|extmetadata|mime",
                    "iiurlwidth": str(width), "format": "json", "origin": "*"},
            json_out=True)
    out = []
    try:
        for page in j.get("query", {}).get("pages", {}).values():
            ii = (page.get("imageinfo") or [{}])[0]
            md = ii.get("extmetadata", {}) or {}
            lic = (md.get("LicenseShortName", {}) or {}).get("value", "")
            out.append({
                "title": page.get("title", ""),
                "mime": ii.get("mime", ""),
                "width": ii.get("width", 0),
                "height": ii.get("height", 0),
                "url": ii.get("thumburl") or ii.get("url", ""),
                "original": ii.get("url", ""),
                "license": lic,
                "desc": (md.get("ImageDescription", {}) or {}).get("value", ""),
            })
    except Exception:
        pass
    return out

def youtube_search(query, limit=6, max_dur=180):
    """yt-dlp `ytsearch` → kandidat-klipp (id, titel, duration, kanal).
    Returnerar [] om yt-dlp saknas eller nätet blockar."""
    try:
        import yt_dlp  # noqa
    except Exception:
        return []
    cmd = [sys.executable, "-m", "yt_dlp", "--no-warnings", "--flat-playlist",
           "--print", "%(id)s\t%(duration)s\t%(title)s\t%(channel)s\t%(url)s",
           f"ytsearch{limit}:{query}"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except Exception:
        return []
    out = []
    for line in r.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) < 5:
            continue
        vid, dur, title, channel, url = parts[:5]
        try:
            dur_f = float(dur or 0)
        except Exception:
            dur_f = 0
        if dur_f and dur_f > max_dur:
            continue
        out.append({"id": vid, "duration": dur_f, "title": title,
                    "channel": channel, "url": url,
                    "license": "youtube", "risk": "review"})
    return out

def ensure_ffmpeg():
    """Returnerar sökväg till ffmpeg (installerar imageio-ffmpeg vid behov)."""
    for cand in ("ffmpeg", "/usr/local/bin/ffmpeg"):
        if subprocess.run(["bash", "-c", f"command -v {cand}"],
                          capture_output=True).returncode == 0:
            return cand
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "imageio-ffmpeg"])
    exe = subprocess.run([sys.executable, "-c",
                          "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())"],
                         capture_output=True, text=True).stdout.strip()
    try:
        os.symlink(exe, "/usr/local/bin/ffmpeg")
    except Exception:
        pass
    return exe

def download(url, dest, timeout=120):
    """Laddar ner fil till dest. Skapar mappar."""
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return dest
    data = get(url, binary=True, use_cache=False, timeout=timeout)
    if not data:
        raise RuntimeError("tom nedladdning: " + url)
    with open(dest, "wb") as f:
        f.write(data)
    return dest
