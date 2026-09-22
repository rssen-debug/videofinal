# 🎬 VideoFinal — Den mest avancerade videostudion

> **VideoFinal** är en enhetlig super-studio som kombinerar de mest avancerade delarna från alla dina projekt:
> 1. **sunnyv2youtube**: 16-agenters AI-orkestrering, 16:9 undersökande dokumentär-pipeline, 2.5D parallax, Anton glow-titlar, sociala UI-kort, ASS karaoke-textning och cinema color grading.
> 2. **youtubeshortskai**: 9:16 vertikala Shorts med trend scouting (`trend_scout.py`), split-screen för reaktioner, ord-för-ord ASR-synkronisering och automatisk audio-ducking.
> 3. **pixeltube**: 100% CPU-baserad proceduriell pixelanimering och ren algoritmisk ljudsyntes (chiptune + SFX: whooshes, impacts, risers) som eliminerar alla upphovsrättsliga risker och externa beroenden.
> 4. **youtubeshorts**: 2D-skelettriggar (puppet animation) med fonemstyrd läppsynk och avatar-kommentatorer som kan läggas ovanpå valfri video.

---

## ⚡ Snabbstart (Quick Start)

### 1. Installation & Verifiering
```bash
git clone https://github.com/rssen-debug/videofinal.git
cd videofinal
pip install -r requirements.txt

# Kör offline-självtest för att verifiera alla 7 delsystem:
python3 videofinal.py --selftest
```

### 2. Skapa 16:9 Dokumentär (SunnyV2 Style)
Kör hela 16-agenterspipelinen med research, manus, Anton-titlar, filmiskt sound design-bed och cinema grading:
```bash
python3 videofinal.py --mode doc --topic "MrBeast Empire"
```

### 3. Skapa 9:16 Vertikal Viral Short (Shorts/TikTok/Reels)
Skapa en split-screen-short med mörk proceduriell pianomatta, ord-för-ord kinetiska undertexter och retentionsfokus:
```bash
python3 videofinal.py --mode short --topic "Kai Stream Dispute"
```

### 4. Skapa 100% CPU Proceduriellt Animerat Avsnitt (PixelTube)
Rendera en komplett animerad scen utan några externa videofiler eller grafikresurser:
```bash
python3 videofinal.py --mode procedural --output anime_episode.mp4
```

### 5. Hitta Nya Trender Automatiskt (Trend Scout AI)
Scanna Kick, Twitch, YouTube och Reddit efter virala konflikter och retentionspotential:
```bash
python3 videofinal.py --scout
```

### 6. Maskinell QA & Granskning (Quality Control Gate)
Validera ljud-RMS, loudnorm, bildförändringsfrekvens och codec-standarder:
```bash
python3 videofinal.py --verify output_video.mp4
```

---

## 🏗️ Modulöversikt (Repo Architecture)

```
videofinal/
├── videofinal.py             # 🚀 Master Unified CLI & Studio Orchestrator
├── ARCHITECTURE.md           # 🏛️ Djupgående teknisk arkitektur & syntesrapport
├── PIPELINE.md               # 📋 Steg-för-steg produktionsguide
├── STYLE_GUIDE.md            # 🎨 Typografi, ljudstandarder och färgprofiler
├── requirements.txt          # 📦 Python-beroenden
│
├── agents/                   # 🤖 16-Agent AI Studio (från sunnyv2youtube)
│   ├── llm_client.py         # Multi-provider LLM-klient med offline-fallback
│   ├── topic_agent.py        # Ämnesupptäckt & vinkling
│   ├── research_agent.py     # Djupresearch & källsamling
│   ├── factcheck_agent.py    # Faktagranskning & källverifiering
│   ├── story_agent.py        # Dramaturgisk kurva
│   ├── script_agent.py       # Manusskrivning
│   ├── hook_agent.py         # 5-sekunders retentionshooks
│   ├── risk_agent.py         # Juridisk risk & förtalskontroll
│   ├── qc_agent.py           # Efterproduktionsgranskning
│   ├── visual_agent.py       # Visuell storyboard & scenregi
│   ├── title_agent.py        # Klickoptimerade titlar (CTR)
│   ├── thumbnail_agent.py    # Thumbnail-komposition & prompter
│   └── upload_agent.py       # YouTube SEO & metadata
│
├── intelligence/             # 📡 Trend Scout & Research (från youtubeshortskai)
│   ├── trend_scout.py        # Kick, Twitch, YouTube RSS & Reddit crawler
│   ├── sources.py            # Dokumentär källhanterare
│   ├── claims.py             # Påståendeextrahering
│   └── trends.py             # Viralitets- och retentionsbedömning
│
├── engine/                   # 🎞️ Cinema, Subtitle & Audio Engines
│   ├── cinema.py             # 2.5D parallax, Ken Burns, teal/orange grade, film grain
│   ├── gfx_kit.py            # Anton glow-titlar, sociala kort, stat HUD
│   ├── vertical_engine.py    # 9:16 vertikal split-screen & kinetiska captions
│   ├── timeline.py           # Ljudstyrd tidslinje & multi-track montering
│   ├── pacing.py             # Klipptempo & retentionskurva
│   ├── sfx_bed.py            # Proceduriell SFX-motor (whooshes, risers, impacts)
│   ├── captions.py           # ASS karaoke med ord-highlight
│   └── audio.py              # Sidechain ducking & loudnorm
│
├── procedural/               # 👾 100% CPU Procedural Animation (från pixeltube)
│   ├── v2engine.py           # Pixelanime-motor, partiklar & kamera-shakes
│   ├── v2make.py             # Avsnittsbyggare & scener
│   ├── music.py              # Algoritmisk chiptune-synthesizer
│   ├── sfx.py                # Algoritmisk ljudeffektsynthesizer
│   └── hybrid_bridge.py      # Brygga för proceduriella cutaways i dokumentärer
│
├── rigs/                     # 🎭 2D Skeletal Puppet & Lip-Sync (från youtubeshorts)
│   ├── build_rigs.py         # Skelettriggning för 2D-figurer
│   ├── puppet_overlay.py     # Animerad avatar / kommentator som video-overlay
│   ├── rig-assistant/        # Assistant-puppet tillgångar & rig.json
│   └── rig-ninja/            # Ninja-puppet tillgångar & rig.json
│
├── presets/                  # ⚙️ Kanalprofiler & stilmallar
│   ├── caption_style.json    # Subtitle-stilar (Sunny, Beast, TikTok, Neon)
│   └── channel_preferences.json
│
└── tests/                    # ✅ Tester & Verifiering
    ├── selftest.py           # Automatiserat offline-test av alla 7 subsystem
    └── verify_build.py       # Strikt maskinell QA (loudness, rörelse, format)
```

---

## 🏆 Varför detta är det mest avancerade systemet

| Förmåga | Tidigare projekt | I **VideoFinal** |
|---|---|---|
| **Formatstöd** | Bara 16:9 (`sunnyv2`) eller bara 9:16 (`kai`) | **Både 16:9 cinema docs OCH 9:16 vertikala Shorts** i samma studiokärna |
| **B-Roll & Visuellt material** | Beroende av externa videoklipp / nedladdningar | **Hybrid-motor**: Live-klipp när de finns, 100% CPU proceduriell pixelanime när de saknas |
| **Ljud & SFX** | Manuella WAV-filer eller externa bibliotek | **100% egen procedural ljudsyntes** (ambient piano, chiptunes, impacts, risers, whooshes) |
| **Trendupptäckt** | Manuell ämnesval eller separat skript | **Integrerad Trend Scout AI** med live Kick/Twitch/Reddit-scoring |
| **Virtuella Karaktärer** | Separata stillbilder eller isolerade puppeter | **Inbyggd avatar-overlay** med automatisk munrörelse och reaktionsposer |
| **Kvalitetssäkring** | Enkla manuella checklistor | **Maskinell QA-gate** som automatiskt mäter RMS, loudnorm, bildaktivitet och codec |

---

## 📜 Licens
Utvecklat för autonom och semi-autonom innehållsproduktion. 100% royalty-fria proceduriella syntesresurser ingår.
