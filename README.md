# VideoFinal 2026

## One command

`python videofinal.py`

Interactive mode is designed for three selections maximum:
1. MODE: Shorts or Documentary
2. NICHE: A for automatic all-niche scouting or one niche
3. QUALITY: 320p / 720p / 1080p

After that, the agent runs without topic/source confirmation prompts.

## Shorts autopilot

`scout → score → research → source hunt → transcript/Whisper → quote moment selection → script → TTS → original source audio → captions → music/SFX → render → QC → retry next story`

Shorts target 45–59 seconds and 9:16. Source captions are tied to the actual speaker using source subtitles and, when needed, word-level Whisper timestamps. Original source audio is preserved for source shots; narration is mixed separately and music is ducked under dialogue.

Source acquisition tries resilient YouTube player clients in sequence and trims small sections instead of downloading unnecessary full VODs. The user does not have to paste source URLs in the normal interactive flow.

## Documentary autopilot

`scout → research → five-act story → original source moments → narration → evidence cards → motion footage → music/SFX → render → QC`

Documentary output is 16:9 and uses the same real-footage/audio/QC core, but with documentary-specific pacing and story structure.

## Cerebras

Set a NEW key in the Windows environment as `CEREBRAS_API_KEY`. VideoFinal uses Cerebras first and falls back to OpenAI/Groq/custom providers when configured.

`python videofinal.py --test-llm`

The default Cerebras model is `gpt-oss-120b`.

Never commit API keys. `SET_CEREBRAS_KEY.bat` stores the key in the Windows user environment and runs the health check.

## Niche score

The scout prints a production-opportunity score on a 0–10 and percentage scale. The score is a planning heuristic based on factors such as hook, freshness, visual potential, research depth and sourceability; it is not a guarantee of views.

## Local checks

`python videofinal.py --selftest`

`python -m py_compile videofinal.py`

## Files

`videofinal.py` is the canonical production entrypoint. `krille2026.py` and `videofinal2026part2.md` remain in the repo as historical/reference material from the earlier Arena-style build.
