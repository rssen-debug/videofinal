# 🎨 VideoFinal Style Guide

## 1. Upplösning & Bildformat

| Format | Dimensioner | Bildfrekvens | Användning |
|---|---|---|---|
| **Cinema Doc** | 1920×1080 / 1280×720 | 30.0 fps (CFR) | Huvudavsnitt, YouTube-dokumentärer |
| **Vertical Short** | 1080×1920 / 720×1280 | 30.0 fps (CFR) | YouTube Shorts, TikTok, Instagram Reels |
| **Procedural Anime** | 320×180 skalat x4 (1280×720) | 30.0 fps (CFR) | Retro cutaways, pixelavsnitt |

---

## 2. Typografi & Titlar

- **Rubriker / Hook-text**: `Anton-Regular` eller `BebasNeue-Regular`.
  - Versaler (ALL-CAPS).
  - Skarp vit text med cyan (#00ffff) eller gult (#ffd700) neonglöd och svart kantlinje (outline: 4-6px).
- **Undertexter (Karaoke / Pop)**:
  - Dokumentär: Centrerad ASS-stil i nedre tredjedelen (MarginV: 45). Aktivt ord lyser upp i stark kontrastfärg.
  - Shorts: 2 rader max, centrerad vid y=948 (på 1280-höjd), 52px teckenstorlek med semi-transparent mörk bakgrundsplatta vid behov.

---

## 3. Ljudstandarder & Mixning

- **Sample Rate**: 44 100 Hz, stereo eller mono mastrad till AAC 192 kbps.
- **Tal / Voiceover**: Loudnorm-anpassad till `-17.0 LUFS` (True Peak: -2.0 dBFS, LRA: 7).
- **Bakgrundsmusik (Bed)**: Duckas automatiskt till `-26 dBFS` när tal är aktivt.
- **SFX (Impacts/Risers)**: Toppar vid `-1.0 dBFS` för maximal dramatisk effekt vid klipp och vändpunkter.

---

## 4. Visuella Effekter & Pacing

- **2.5D Parallax**: Stillbilder delas i förgrund/bakgrund och rör sig i motsatt riktning med mjuk cubic easing.
- **Teal & Orange Grade**: Skuggor lutas mot subtil cyan/teal, högdagrar och hudtoner mot varm bärnsten/orange.
- **Klipprytm**: Aldrig längre än 5–6 sekunder utan visuell eller auditiv förändring (förhindrar "bildspels-effekt").
