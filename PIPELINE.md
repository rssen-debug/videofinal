# 📋 VideoFinal Pipeline: Production Playbook

Denna guide beskriver hur **VideoFinal Studio** kör sina produktionsflöden från idé till färdig renderad master.

---

## 1. Dokumentär-flöde (16:9 Cinema / SunnyV2)

```
[TOPIC/TREND] ──► [RESEARCH AGENT] ──► [FACT-CHECK & RISK] ──► [STORY/HOOK]
                                                                    │
┌───────────────────────────────────────────────────────────────────┘
▼
[SCRIPT WRITER] ──► [TIMELINE & PACING] ──► [VOICEOVER & DUCKING]
                                                   │
┌──────────────────────────────────────────────────┘
▼
[GFX KIT: TITLES/CARDS] ──► [CINEMA 2.5D GRADE] ──► [ASS KARAOKE CAPTIONS] ──► [QC GATE]
```

### Steg:
1. **Ämne & Trendanalys**: `topic_agent` identifierar ämnets kärnkonflikt och beräknar CTR-potential.
2. **Källinsamling & Faktagranskning**: `research_agent` och `factcheck_agent` verifierar primärkällor och säkerställer att påståenden inte bryter mot förtalslagstiftning (`risk_agent`).
3. **Dramaturgi & Krok**: `hook_agent` bygger de första 5 sekunderna för maximal tittarretention. `story_agent` skapar en 5-akters struktur.
4. **Ljud & Tidslinje**: `sfx_bed` syntetiserar filmiska impacts och whooshes. Bakgrundsmusiken duckas automatiskt vid tal.
5. **Visuell Komposition**: `cinema.py` lägger på 2.5D-parallax på stillbilder, teal & orange färgprofil och filmkorn. `gfx_kit.py` skapar glödande Anton-titlar och sociala mediekort.
6. **Maskinell QA**: `verify_build.py` verifierar att videon har tillräcklig bildrörelse, att ljudet har dynamiska höjdpunkter och att inga svarta bildrutor finns.

---

## 2. Vertikalt Short-flöde (9:16 Shorts/Reels/TikTok)

```
[TREND SCOUT AI] ──► [VOD CLIP SELECTION] ──► [SPLIT-SCREEN COMPOSITOR]
                                                        │
┌───────────────────────────────────────────────────────┘
▼
[PROCEDURAL AMBIENT PIANO] ──► [DYNAMIC WORD POP] ──► [FAST CUT ENGINE] ──► [FINAL SHORT]
```

### Steg:
1. **Trend Scout**: Scannar Kick/Twitch/YouTube efter heta klipp.
2. **Split-Screen Layout**: `vertical_engine.py` monterar över- och underfönster (kreatörsreaktion + spelsekvens/händelse).
3. **Ljuddesign**: Genererar proceduriell mörk ambient pianomatta med loudnorm-anpassning (-17 LUFS).
4. **Kinetiska Undertexter**: Ord-för-ord-highlighting med gult/grönt pop i bildens nedre tredjedel.

---

## 3. Proceduriellt Anime/Pixel-flöde (100% CPU)

```
[STORY GENERATOR] ──► [PIXEL ACTORS & SCENE] ──► [PROCEDURAL CHIPTUNE + SFX] ──► [MP4]
```

### Steg:
1. **Scen- & Karaktärsrendering**: `v2engine.py` ritar bakgrunder, partiklar, fartlinjer och ljuseffekter pixel för pixel.
2. **Ljudsyntes**: `music.py` och `sfx.py` skapar adaptiv chiptune-musik och ljudeffekter (steg, hopp, träffar, explosioner).
3. **Zero Asset Requirement**: Kan köras i valfri miljö helt utan internetanslutning eller GPU.
