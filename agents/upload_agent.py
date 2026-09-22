#!/usr/bin/env python3
"""agents/upload_agent.py — UPLOAD-AGENT (YouTube Data API v3).

VALFRITT och AVSTÄNGT som standard. Aktiveras med:
    python sunny_auto.py --topic "X" --upload          (privat)
    python sunny_auto.py --topic "X" --upload --auto-publish   (public)

Kräver OAuth2-uppgifter för YouTube Data API (google cloud console):
 - root:     YT_CLIENT_SECRETS (sökväg till client_secrets.json) ENV
 - token:    ~/.sunny/yt_refresh.json  (sparas efter första device-flow)

Säkerhet: uploaden sker ALDRIG om risk_agent → HOLD, eller om QC failat.

Resumable upload görs rakt mot Googles endpoints (inga tunga Google-bibliotek).
"""
import os, json, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN_PATH = os.path.expanduser("~/.sunny/yt_refresh.json")
OAUTH = "https://oauth2.googleapis.com/token"
AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
UPLOAD = "https://www.googleapis.com/upload/youtube/v3/videos"
API = "https://www.googleapis.com/youtube/v3/videos"
SCOPE = "https://www.googleapis.com/auth/youtube.upload"

class UploadError(RuntimeError):
    pass

def _secrets():
    path = os.environ.get("YT_CLIENT_SECRETS")
    if path and os.path.exists(path):
        return json.load(open(path, encoding="utf-8"))["installed"]
    raise UploadError(
        "YT_CLIENT_SECRETS saknas. Skapa OAuth2-klient (desktop) i Google Cloud "
        "Console -> ladda ner client_secrets.json -> export YT_CLIENT_SECRETS=<path>")

def _post(url, data, headers=None):
    import requests
    h = {"Content-Type": "application/json"}
    h.update(headers or {})
    r = requests.post(url, data=json.dumps(data) if isinstance(data, dict) else data,
                      headers=h, timeout=60)
    if r.status_code >= 300:
        raise UploadError(f"{r.status_code}: {r.text[:400]}")
    return r

def _device_code(scopes=SCOPE):
    sec = _secrets()
    r = _post(AUTH.replace("/v2/auth", "/device/code"), {
        "client_id": sec["client_id"], "scope": scopes})
    j = r.json() if hasattr(r, "json") else json.loads(r.text)
    return j

def _poll_token(code, timeout_s=300):
    sec = _secrets()
    j = code
    end = time.time() + timeout_s
    print("     gå till:", j.get("verification_url"))
    print("     ange kod:", j.get("user_code"))
    while time.time() < end:
        r = _post(OAUTH, {
            "client_id": sec["client_id"], "client_secret": sec["client_secret"],
            "device_code": j["device_code"],
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code"})
        d = r.json() if hasattr(r, "json") else json.loads(r.text)
        if "access_token" in d:
            return {
                "access_token": d["access_token"],
                "refresh_token": d.get("refresh_token",
                                       _load_token().get("refresh_token", "")),
            }
        if d.get("error") != "authorization_pending":
            time.sleep(4)
        time.sleep(4)
    raise UploadError("device-flow timeout")

def _load_token():
    if os.path.exists(TOKEN_PATH):
        try:
            return json.load(open(TOKEN_PATH, encoding="utf-8"))
        except Exception:
            pass
    return {}

def _save_token(tok, tag):
    os.makedirs(os.path.dirname(TOKEN_PATH), exist_ok=True)
    json.dump({**tok, "tag": tag},
              open(TOKEN_PATH, "w", encoding="utf-8"), indent=1)

def _access_token(force=False):
    tok = _load_token()
    if not tok.get("refresh_token") or force:
        code = _device_code()
        tok = _poll_token(code)
        _save_token(tok, "youtube")
        return tok["access_token"]
    sec = _secrets()
    r = _post(OAUTH, {
        "client_id": sec["client_id"], "client_secret": sec["client_secret"],
        "refresh_token": tok["refresh_token"],
        "grant_type": "refresh_token"})
    d = r.json() if hasattr(r, "json") else json.loads(r.text)
    _save_token({**tok, **d}, "youtube")
    return d["access_token"]

def upload(video_path, metadata, privacy="private", auto_publish=False,
           credential_callback=None):
    """Resumable-upload. metadata: {title, description, tags, language}.
    Returnerar video_id."""
    token = _access_token()
    privacy = "public" if auto_publish else privacy
    meta = {
        "snippet": {
            "title": (metadata.get("title") or "video")[:100],
            "description": metadata.get("description", "")[:4900],
            "tags": (metadata.get("tags") or [])[:20],
            "defaultLanguage": metadata.get("language", "en"),
            "categoryId": "22",
        },
        "status": {"privacyStatus": privacy,
                   "selfDeclaredMadeForKids": False},
    }
    import requests
    size = os.path.getsize(video_path)
    headers = {"Authorization": f"Bearer {token}",
               "X-Upload-Content-Length": str(size),
               "X-Upload-Content-Type": "video/*",
               "Content-Type": "application/json; charset=UTF-8"}
    r = requests.post(f"{UPLOAD}?uploadType=resumable&part=snippet,status",
                      data=json.dumps(meta), headers=headers, timeout=60)
    if r.status_code not in (200, 201):
        raise UploadError(f"init: {r.status_code} {r.text[:300]}")
    loc = r.headers.get("Location")
    with open(video_path, "rb") as f:
        ur = requests.put(loc, data=f, headers={"Authorization": f"Bearer {token}"},
                          timeout=3600)
    if ur.status_code not in (200, 201):
        raise UploadError(f"upload: {ur.status_code} {ur.text[:300]}")
    body = ur.json()
    return body.get("id")
