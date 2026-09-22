# 🎬 VIDEOFINAL 2026 (PART 2) — THE DEVELOPER MASTER BLUEPRINT
### Complete 1:1 Technical Specification for Autonomous SunnyV2-Style Documentary & Short Generation

> **Audience:** Senior Backend & Video Pipeline Engineers.  
> **Purpose:** Everything needed to build, automate, and scale the SunnyV2 documentary engine: exact data sources, video scrapers, 16-agent AI reasoning, ASR alignment, 6-second visual pacing formula, multi-track sidechain ducking, and FFmpeg filtergraphs.

---

## 📑 TABLE OF CONTENTS
1. [System Overview & Editorial Philosophy](#1-system-overview)
2. [Data & Video Discovery Engine (How Real Footage is Found)](#2-data--video-discovery)
3. [Visual Sourcing & 2.5D Graphic Processing](#3-visual-sourcing)
4. [AI Agent Brain: 16-Agent Decision Hierarchy](#4-ai-agent-brain)
5. [Story Arc & Narration Scriptwriting Engine](#5-story-arc--scriptwriting)
6. [Visual Pacing: The "Anti-Boredom" 6-Second Rule](#6-visual-pacing)
7. [Audio Architecture, Sound Design & Sidechain Ducking](#7-audio-architecture)
8. [ASS Dynamic Karaoke Subtitle Engine](#8-ass-subtitles)
9. [JSON Schemas & Timeline Data Structures](#9-json-schemas)
10. [FFmpeg Render Execution & Filtergraphs](#10-ffmpeg-render-graphs)
11. [Machine QC Protocol (The Reject Gate)](#11-machine-qc)

---

<a name="1-system-overview"></a>
## 1. SYSTEM OVERVIEW & EDITORIAL PHILOSOPHY

The SunnyV2 format is **not** a traditional news report, nor is it a slideshow. It is a high-octane **cinematic internet video essay** characterized by:
- **Fast-paced investigative storytelling**: Strong dramatic tension, rising stakes, and fatal blindspots.
- **Real live video clips with original audio**: Streamer moments, interview clips, confrontations, and podcast debates integrated with their raw audio punchlines.
- **TTS Voiceover around the clips**: British/American documentary narration that sets up the context, pauses for the clip to play, and delivers the analytical payoff.
- **Constant visual movement**: No static frame lasts longer than 3–5 seconds. If a still image is on screen, it has Ken Burns drift or 2.5D parallax.
- **Sound design punches**: Risers leading into revelations, low-end impacts on chapter titles, whooshes on camera cuts, and subtle camera shutter clicks on article headlines.

---

<a name="2-data--video-discovery"></a>
## 2. DATA & VIDEO DISCOVERY ENGINE (HOW REAL FOOTAGE IS FOUND)

The pipeline discovers trending creator stories and extracts high-resolution video clips without human intervention.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        DATA SCOUTING INGESTION                         │
├──────────────────┬──────────────────┬─────────────────┬────────────────┤
│    KICK API v2   │  TWITCH & YOUTUBE│   REDDIT API    │  GOOGLE NEWS   │
│  /channels/clips │   RSS Feeds & VOD│r/LivestreamFail │  RSS Searches  │
│  /livestreams    │   yt-dlp Slicer  │r/YouTube Drama  │  Dexerto, TMZ  │
└────────┬─────────┴────────┬─────────┴────────┬────────┴────────┬───────┘
         │                  │                  │                 │
         └──────────────────┼──────────────────┴─────────────────┘
                            ▼
              ┌───────────────────────────┐
              │  Story Scoring & Ranking  │
              │  (Controversy, Retention) │
              └─────────────┬─────────────┘
                            ▼
              ┌───────────────────────────┐
              │ yt-dlp Precise Cut Slicer │
              │ (--download-sections)     │
              └─────────────┬─────────────┘
                            ▼
              ┌───────────────────────────┐
              │ ASR Word-Level Alignment  │
              │ (Whisper Timestamp Match) │
              └───────────────────────────┘
```

### A. Scraping Endpoints & Watchlists
1. **Kick API v2**:
   - `GET https://kick.com/api/v2/livestreams?sort=viewer_count&direction=desc&per_page=25`
   - `GET https://kick.com/api/v2/channels/{slug}/clips?sort=date&direction=desc&per_page=20`
   - Yields: Direct HLS / MP4 CDN clip URLs, creator metadata, view counts, and clip titles.
2. **Reddit API**:
   - `GET https://www.reddit.com/r/LivestreamFail/hot.json?limit=25`
   - `GET https://www.reddit.com/r/youtube/search.json?q=controversy&sort=new`
   - Extracts: Clip mirror links (Streamable, Clips.twitch.tv, Kick clips) and comment sentiment.
3. **YouTube RSS Feeds**:
   - `GET https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}`
   - Tracks 15+ curated creators (`Kai Cenat`, `Adin Ross`, `MrBeast`, `xQc`, `IShowSpeed`, `Trainwreckstv`).
4. **Google News RSS**:
   - `GET https://news.google.com/rss/search?q={creator}+drama&hl=en-US&gl=US&ceid=US:en`
   - Extracts: Journalism sources (Dexerto, Kotaku, TMZ, Forbes, BBC).

### B. Precise Video Slicing with `yt-dlp` (Zero Waste)
Downloading entire 5GB–10GB VODs causes sandbox exhaustion. The engine uses `yt-dlp`'s HTTP range-request section downloader:

```bash
# Download ONLY seconds 14:15 to 14:32 directly into 720p H.264
yt-dlp \
  --download-sections "*14:15-14:32" \
  --force-keyframes-at-cuts \
  -f "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]" \
  --output "assets/clips/clip_incident_%(id)s.mp4" \
  "<TARGET_URL>"
```

### C. ASR Word-Level Alignment (Whisper Speech-to-Text)
To cut exactly when a streamer starts screaming, laughing, or making a confession, raw audio from the downloaded clip is passed to Whisper ASR:
```python
# Output: word-level timing array
[
  {"text": "I", "start": 0.12, "end": 0.28},
  {"text": "never", "start": 0.30, "end": 0.58},
  {"text": "agreed", "start": 0.60, "end": 0.95},
  {"text": "to", "start": 0.98, "end": 1.10},
  {"text": "that!", "start": 1.12, "end": 1.45}
]
```
The editor slices the clip boundary at `start - 0.15s` and `end + 0.30s` to prevent clipping speech.

---

<a name="3-visual-sourcing"></a>
## 3. VISUAL SOURCING & 2.5D GRAPHIC PROCESSING

When live video clips aren't on screen, SunnyV2 uses **motion stills**, **headline cards**, and **social evidence cards**.

### A. The 2.5D Parallax Engine
Still images are never rendered flat. The engine separates subjects from backgrounds:
1. **Subject Isolation**: Extracts head/torso cutouts via rembg / OpenCV thresholding.
2. **Background Inpainting**: Fills background behind subject with Gaussian blur (`radius=15`) or content-aware fill.
3. **Opposing Camera Movement**:
   - Background slowly pushes inward: $Zoom_{bg} = 1.0 \to 1.06$
   - Foreground subject slowly drifts upward/outward: $Zoom_{fg} = 1.0 \to 1.12$, $Y_{shift} = 0 \to -18px$.
   - Result: 3D parallax depth on flat JPG photos.

### B. Social Media Proof Cards (`gfx_kit.py`)
Renders simulated Twitter/X tweets, Kick chat messages, or YouTube community posts:
- Canvas: 760×260 RGBA card at $y=230$.
- Styling: #10141A dark mode, #1D9BF0 verified blue badge, high-contrast white text, metrics line (❤️ 42K, 🔄 12K).
- Placement: Composited over darkened or blurred video frames.

### C. Big SunnyV2 Chapter Cards
- Background: Near-black (#0C0E12) with subtle radial vignette.
- Headline: 68px `Anton-Regular` in pure white with 4px black outline and 12px outer glow.
- Subline: 26px `BebasNeue-Regular` in bright red (#E82832) or amber (#FFD700) underlined by a 2px horizontal rule.

---

<a name="4-ai-agent-brain"></a>
## 4. AI AGENT BRAIN: 16-AGENT DECISION HIERARCHY

The documentary is written, directed, and checked by 16 collaborative AI agents:

```
[1. TOPIC AGENT] ───► [2. RESEARCH AGENT] ───► [3. FACT-CHECK AGENT]
         │
         ▼
[4. RISK AGENT]  ───► [5. HOOK AGENT]     ───► [6. STORY AGENT]
         │
         ▼
[7. SCRIPT AGENT]───► [8. PACING AGENT]   ───► [9. FOOTAGE AGENT]
         │
         ▼
[10. VISUAL AGENT]──► [11. GRAPHICS AGENT]───► [12. AUDIO AGENT]
         │
         ▼
[13. EDIT AGENT] ───► [14. QC AGENT]      ───► [15. TITLE/THUMBNAIL]
                                                      │
                                                      ▼
                                            [16. UPLOAD AGENT]
```

### Agent Roles & Prompts:
1. **Topic Agent**: Analyzes news feeds. Scores drama on Virality (1–10), Search Volume, and Narrative Conflict.
2. **Research Agent**: Collects 5–10 primary sources. Extracts verified dates, viewer counts, and quotes.
3. **FactCheck Agent**: Cross-checks claims. Removes unverified gossip or unsubstantiated accusations.
4. **Risk Agent**: Enforces Fair Use doctrine (criticism, review, reporting). Replaces defamatory phrasing with journalistic attribution (*"Allegations surfaced...", "Documents revealed..."*).
5. **Hook Agent**: Formulates the opening 0–5 seconds. Formula: `[Extreme Result] + [Mystery Inversion] + [Visual Shock]`.
6. **Story Agent**: Constructs the 5-act narrative arc (Rise, Blindspot, Incident, Escalation, Aftermath).
7. **Script Agent**: Writes the voiceover script in 8–10 distinct blocks (A1 through B2). Inserts explicit clip lead-ins (*"Listen to how he responded...", "Watch this exact moment..."*).
8. **Pacing Agent**: Enforces word count (145 WPM). Allocates 4–8 seconds for video clips to play uninterrupted.
9. **Footage Agent**: Maps script lines to exact video clip timestamps (`file`, `start`, `duration`).
10. **Visual Agent**: Defines camera motion (Ken Burns push vs pull), lighting filters, and color palette.
11. **Graphics Agent**: Designs the Anton title cards, lower thirds, and social UI cards.
12. **Audio Agent**: Coordinates TTS voice model (`en-GB-RyanNeural`), SFX cue points, and sidechain ducking levels.
13. **Edit Agent**: Assembles the master `timings.json` and `shots.json` sequence.
14. **QC Agent**: Executes automated post-render checks. Rejects videos with clipping audio or static slideshow pacing.
15. **Title & Thumbnail Agent**: Tests 10 high-CTR title variations and generates 3-element thumbnail prompts (Subject face + Exaggerated emotion + 3-word Anton text).
16. **Upload Agent**: Prepares YouTube metadata, description timestamps, tags, and pinned comment.

---

<a name="5-story-arc--scriptwriting"></a>
## 5. STORY ARC & NARRATION SCRIPTWRITING ENGINE

### The 5-Act SunnyV2 Formula:
- **Act 1: The Hook & Ascent (0:00 - 0:35)**: Introduce the creator at the absolute peak of their influence. Show rapid subscriber growth.
- **Act 2: The Blindspot (0:35 - 1:15)**: The first subtle signs of arrogance, rule-bending, or controversy that audience members ignored.
- **Act 3: The Breaking Point (1:15 - 2:05)**: The live stream incident happens. Play the **REAL VIDEO CLIP WITH RAW AUDIO**. Let the streamer say the exact words.
- **Act 4: The Escalation & Reaction (2:05 - 2:55)**: Other streamers react. Community backlash explodes on Reddit and Twitter. Play a second reaction clip.
- **Act 5: The Aftermath & Legacy (2:55 - 3:40)**: Bans, legal fallout, lost sponsorships, and the analytical conclusion on why modern fame evaporates overnight.

---

<a name="6-visual-pacing"></a>
## 6. VISUAL PACING: THE "ANTI-BOREDOM" 6-SECOND RULE

> **MANDATE RULE:** A viewer will click away if the screen remains static for more than 4–6 seconds.

```
0s          3s          6s          9s          12s         15s         18s
├───────────┼───────────┼───────────┼───────────┼───────────┼───────────┤
│ Title Card│Ken Burns  │ Tweet UI  │ REAL CLIP │ REAL CLIP │Ken Burns  │
│ + Impact  │Photo Zoom │ Card      │ (Live VO) │ (Raw Clip)│Article    │
│ (TTS VO)  │ (TTS VO)  │ (TTS VO)  │ (TTS VO)  │ (Clip Aud)│ (TTS VO)  │
└───────────┴───────────┴───────────┴───────────┴───────────┴───────────┘
```

### Techniques to Prevent Fatigue:
1. **Video Clip Splicing**:
   - First 2–3 seconds of a video clip: Narrator speaks over the clip while clip audio is muted or low.
   - Next 4–6 seconds: Narrator goes silent, background music ducks to -26dB, and the **real clip audio plays at 100% volume**.
2. **Camera Transitions**:
   - Chapter switches use a 0.13s exposure dip (`fade=t=in:st=0:d=0.13`) resembling a camera flash.
   - Camera shutter SFX (`click.wav`) plays synchronously with newspaper/tweet cuts.
3. **Motion Easing**:
   - Never use linear motion. Always use Cubic Ease-Out: $f(x) = 1 - (1 - x)^3$.
   - Restrained zoom: Zoom from $1.00 \to 1.03$ or $1.04 \to 1.01$.

---

<a name="7-audio-architecture"></a>
## 7. AUDIO ARCHITECTURE, SOUND DESIGN & SIDECHAIN DUCKING

### Audio Track Stack:
- **Track 1: Narration Voiceover (TTS)**: Clean, dry, loudnorm mastered to `-17.0 LUFS`.
- **Track 2: Real Video Clip Audio**: Original live streamer dialogue, game sound, or interview audio.
- **Track 3: Cinematic Sound Bed (Music)**: Slow minor harmony dark piano bed at 70 BPM.
- **Track 4: SFX Bed**: Impacts, whooshes, risers, and camera clicks.

### The Sidechain Ducking Formula:
When the narrator or a live clip speaks, the background music **must** drop automatically.

```
Narration Active:  ═══════════                 ═════════════════
Clip Audio Active:            ════════════════
Music Bed:         ───\______/────────────────\________________/────
                      -26 dBFS    -26 dBFS         -26 dBFS
```

In FFmpeg, this is achieved with the `sidechaincompress` filter:
```
[1:a]volume=0.35[bed];
[bed][0:a]sidechaincompress=threshold=0.03:ratio=8:attack=15:release=350[ducked];
[0:a][ducked]amix=inputs=2:duration=first:dropout_transition=2[outa]
```
- `threshold=0.03`: Triggers ducking immediately when speech is detected.
- `ratio=8`: Heavy 8:1 compression ratio drops music by ~18dB.
- `attack=15`: 15ms fast attack prevents volume clashes.
- `release=350`: 350ms smooth release allows music to rise naturally during pauses.

---

<a name="8-ass-subtitles"></a>
## 8. ASS DYNAMIC KARAOKE SUBTITLE ENGINE

Documentary subtitles are formatted in Advanced SubStation Alpha (`.ass`):
- **Font**: `Anton-Regular`, 44pt.
- **Position**: Centered, lower third (`MarginV=42`, safe above progress bars).
- **Primary Color**: Pure white (`&H00FFFFFF`).
- **Accent Keyword Color**: Gold (`&H0000D7FF`) or Yellow (`&H0000FFFF`).
- **Outline**: 3.5px solid black outline (`&H00000000`).
- **Shadow**: 2.0px soft shadow (`&H80000000`).

Sample ASS Event with Keyword Pop:
```
Dialogue: 0,0:00:03.20,0:00:05.80,Default,,0,0,0,,He had over {\c&H00D7FF&\b1}100,000{\r} live viewers.
```

---

<a name="9-json-schemas"></a>
## 9. JSON SCHEMAS & TIMELINE DATA STRUCTURES

### `shots.json` Schema (Scene by Scene):
```json
[
  {
    "id": "A1_01",
    "kind": "still",
    "dur": 4.25,
    "image": "title_card.png",
    "variant": "zoom_in",
    "effect": "flash_dip"
  },
  {
    "id": "A1_02",
    "kind": "video_clip",
    "dur": 6.50,
    "file": "assets/clips/streamer_reaction.mp4",
    "cut": 34.20,
    "has_audio": true,
    "audio_gain": 1.0
  },
  {
    "id": "A2_01",
    "kind": "still",
    "dur": 3.80,
    "image": "tweet_card.png",
    "variant": "zoom_out"
  }
]
```

### `timings.json` Schema:
```json
{
  "total": 221.0,
  "blocks": [
    {"name": "A1", "audio": "audio/A1.wav", "dur": 18.2, "words": 48},
    {"name": "A2", "audio": "audio/A2.wav", "dur": 22.4, "words": 59}
  ],
  "clips": [
    {"name": "bark_incident", "start": 32.5, "dur": 6.8, "file": "clips/bark.mp4"},
    {"name": "speed_reaction", "start": 142.0, "dur": 8.4, "file": "clips/speed.mp4"}
  ],
  "sfx": [
    {"type": "impact", "time": 0.0, "vol": 0.8},
    {"type": "whoosh", "time": 18.2, "vol": 0.5},
    {"type": "riser", "time": 30.0, "vol": 0.6}
  ]
}
```

---

<a name="10-ffmpeg-render-graphs"></a>
## 10. FFMPEG RENDER EXECUTION & FILTERGRAPHS

The video assembly executes in 3 optimized phases to avoid memory crashes:

### Phase 1: Per-Shot Micro-Rendering
Each still shot or clip slice is rendered individually to a cache folder:
```bash
# Still shot with restrained Ken Burns push
ffmpeg -y -v error -loop 1 -framerate 30 -i assets/gfx/card.png \
  -vf "scale=1920:1080,zoompan=z='1.0+0.027*on/120':x='iw/2-(iw/zoom)/2':y='ih/2-(ih/zoom)/2':d=120:s=1280x720:fps=30,setsar=1" \
  -t 4.0 -c:v libx264 -pix_fmt yuv420p cache/shot_001.mp4

# Video clip slice with exact crop and audio extraction
ffmpeg -y -v error -ss 14.5 -t 6.0 -i assets/clips/vod.mp4 \
  -vf "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30" \
  -c:v libx264 -pix_fmt yuv420p -c:a aac -ar 44100 -ac 2 cache/shot_002.mp4
```

### Phase 2: Lossless Concatenation
```bash
ffmpeg -y -f concat -safe 0 -i concat.txt -c copy cache/raw_video_merged.mp4
```

### Phase 3: Audio Ducking & Subtitle Burn-in
```bash
ffmpeg -y \
  -i cache/raw_video_merged.mp4 \
  -i audio/documentary_bed.wav \
  -filter_complex \
  "[1:a]volume=0.32[music]; \
   [music][0:a]sidechaincompress=threshold=0.03:ratio=8:attack=15:release=350[ducked]; \
   [0:a][ducked]amix=inputs=2:duration=first[aout]; \
   [0:v]subtitles=captions.ass:fontsdir=assets/fonts[vout]" \
  -map "[vout]" -map "[aout]" \
  -c:v libx264 -b:v 2500k -pix_fmt yuv420p \
  -c:a aac -b:a 192k -ar 44100 \
  videofinal.mp4
```

---

<a name="11-machine-qc"></a>
## 11. MACHINE QC PROTOCOL (THE REJECT GATE)

The file `verify_build.py` enforces broadcast compliance. A video is **automatically rejected** if any check fails:

| Check | Metric | Pass Condition | Reject Action |
|---|---|---|---|
| **Streams** | Video & Audio | `H.264` + `AAC` (44.1 kHz) | Hard Exit 1 |
| **Duration** | Target Drift | $|Dur_{actual} - Dur_{target}| / Dur_{target} \le 5\%$ | Hard Exit 1 |
| **Visual Motion** | Gray Frame Diff | Median Activity $> 0.25$ | Re-render with faster cuts |
| **Audio Loudness**| Integrated LUFS | $-17.0 \pm 1.5$ LUFS | Re-run loudnorm |
| **Clip Energy** | Dynamic Spikes | $\ge 3$ audio windows $> 1.15\times$ neighbor RMS | Flag missing clip audio |
| **Audio Clipping** | True Peak | Max RMS $< 0.95$ (No digital distortion) | Apply peak limiter |

---

## 🛠️ DEVELOPER HANDOFF CHECKLIST

To deploy this engine in your backend / microservice:
- [x] Install system `ffmpeg` with `libx264` and `libass`.
- [x] Provide `yt-dlp` in `$PATH` for real clip extraction.
- [x] Place font `Anton-Regular.ttf` in `assets/fonts/`.
- [x] Configure LLM client credentials (`GROQ_API_KEY`, `OPENAI_API_KEY`, or local Ollama).
- [x] Run `python3 krille2026.py --selftest` to verify all mathematical synthesizers.
- [x] Execute `python3 krille2026.py --mode doc --topic "<TOPIC>"` to produce the broadcast master.
