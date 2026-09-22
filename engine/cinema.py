#!/usr/bin/env python3
"""CINEMA KIT — återanvändbara ffmpeg-byggstenar för "studio-look".
Importera i din builder: from cinema import ease, ss, GRADE, GRAIN, LETTERBOX, bloom_chain, MUSIC_BEAT
"""
import math

# ---------------- easing (F9/Easy Ease & overshoot) ----------------
def ss(T0, D):
    return f"min(max((t-{T0:.3f})/{D:.3f},0),1)"

def ease(T0, D, a, b, back=False):
    p = f"({ss(T0, D)})"
    if back:
        return f"{a}+({b}-{a})*(1+2.70158*pow({p}-1,3)+1.70158*pow({p}-1,2))"
    return f"{a}+({b}-{a})*{p}*{p}*(3-2*{p})"

def drift(T0, D, amp=14, period=5.0, phase=0.0):
    """organisk kamera-drift (parallax-känsla) för overlays"""
    return f"({amp}*sin(2*PI*(t-{T0:.2f})/{period:.2f}+{phase:.2f})*min(max((t-{T0:.2f})/2,0),1))"

# ---------------- LOOK (färg + film + glow) ----------------
# teal/orange-dokumentär-grade
GRADE = ("eq=contrast=1.12:saturation=1.16:gamma=0.98,"
         "colorbalance=rs=-0.045:bs=0.06:rm=0.02:bm=-0.03")
# filmisk grain (t = temporärt, u = uniform)
GRAIN = "noise=alls=6:allf=t+u"
# letterbox (cinema-bars)
def letterbox(h=62):
    return (f"drawbox=x=0:y=0:w=iw:h={h}:color=black@1:t=fill,"
            f"drawbox=x=0:y=ih-{h}:w=iw:h={h}:color=black@1:t=fill")

def bloom_chain(inlabel, outlabel, sigma=11, opacity=0.22, uid="bl"):
    """glow/bloom: blend(screen) av oskärpa över sig själv. UNIKA labels krävs."""
    return (f"[{inlabel}]split=2[{uid}a][{uid}b];"
            f"[{uid}b]gblur=sigma={sigma}[{uid}g];"
            f"[{uid}a][{uid}g]blend=all_mode=screen:all_opacity={opacity}[{outlabel}]")

# ---------------- LJUD ----------------
# musik: mörk drone MED pulsslag (90 BPM => slag var 0.6667 s) — klipp beats till k*0.6667!
MUSIC_BEAT = ("aevalsrc=exprs='(0.15*exp(-7*mod(t,0.6667))*sin(2*PI*55*t)"
              "+0.07*sin(2*PI*110*t)*exp(-5*mod(t,0.6667)))*(0.7+0.3*sin(2*PI*0.05*t))"
              "+0.028*sin(2*PI*49*t)'")

# SFX-formler (syntetiska = fria från copyright)
SFX_IMPACT = ("aevalsrc=exprs='0.85*sin(2*PI*52*t)*exp(-5.5*t)"
              "+0.30*sin(2*PI*110*t)*exp(-8*t)':s=44100")     # 1.6 s
SFX_WHOOSH = ("aevalsrc=exprs='0.30*sin(2*PI*(300+900*exp(-6*t))*t)*exp(-9*pow(t-0.35,2)/0.09)'"
              ":s=44100")                                      # ca 1.0 s
SFX_RISER = ("aevalsrc=exprs='0.16*sin(2*PI*(160+260*t)*t)"
             "+0.10*sin(2*PI*(90+40*t)*t)':s=44100")           # 2.4 s
SFX_GLITCH = ("aevalsrc=exprs='0.22*sin(2*PI*1400*t)*lt(mod(t,0.11),0.03)'"
              ":s=44100")                                      # digitala klick

def beat(t, bpm=90):
    """närmaste beat-tid (för beat-syncade snitt)"""
    step = 60.0 / bpm
    return round(t / step) * step

# ---------------- PARALLAX (2.5D) ----------------
def parallax_bg(zoom_rate=0.00022, zmax=1.18, d=99999, s="1280x720", fps=30):
    """bakgrunds-plat: långsam zoompan + sidodrift"""
    return (f"zoompan=z='min(1+{zoom_rate}*on,{zmax})':"
            f"x='iw/2-(iw/zoom)/2+34*sin(on/{fps*7.0})':"
            f"y='ih/2-(ih/zoom)/2':d={d}:s={s}:fps={fps}")

def parallax_fg(T0, amp=26, period=7.0):
    """foreground-cutout: motriktad drift => djup. Returnera x-offset-uttryck."""
    return f"({amp}*sin(2*PI*t/{period:.2f}))*min(max((t-{T0:.2f})/1.2,0),1)"

# ================= v2.1: LOOKS + TRACKING + extra SFX =================
# Olika look per story-del: hook=DEFAULT, archive=COLD/ARCHIVE, reveal=HEAT, night=NIGHT
LOOKS = {
    "DEFAULT": "eq=contrast=1.12:saturation=1.16:gamma=0.98,"
               "colorbalance=rs=-0.045:bs=0.06:rm=0.02:bm=-0.03",
    "COLD":    "eq=contrast=1.14:saturation=0.82:gamma=1.02,"
               "colorbalance=bs=0.14:rs=-0.06:bh=0.04",
    "HEAT":    "eq=contrast=1.16:saturation=1.22:gamma=0.95,"
               "colorbalance=rs=0.09:bs=-0.06:rh=0.05",
    "ARCHIVE": "eq=contrast=0.92:saturation=0.55:gamma=1.05,hue=s=0.6",
    "NIGHT":   "eq=contrast=1.18:saturation=0.9:gamma=0.9,"
               "colorbalance=bs=0.08:gm=-0.03",
}

def track(T0, T1, a0, a1, back=True):
    """manuell '3D camera tracking'-pan: eased värde mellan två punkter över tid.
    Använd för att låta text/GFX 'följa' något i ett klipp (mata in två referenspunkter)."""
    return ease(T0, max(T1 - T0, 0.01), a0, a1, back=back)

SFX_CLICK = ("aevalsrc=exprs='0.25*sin(2*PI*1800*t)*exp(-60*t)"
             "+0.10*sin(2*PI*900*t)*exp(-30*t)':s=44100")   # UI-klick/tick
SFX_AMBIENCE = ("aevalsrc=exprs='0.03*sin(2*PI*120*t)*(0.6+0.4*sin(2*PI*0.09*t))"
                "+0.02*sin(2*PI*67*t)*sin(2*PI*0.03*t)':s=44100")  # mörkt rum
