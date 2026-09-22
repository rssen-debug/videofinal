# -*- coding: utf-8 -*-
"""
story.py – PIXEL UNIVERSE v6: mission-comedy template system.

RESEARCH-DRIVEN STRUCTURE (top-anime retention science, applied to 8-bit):
  1. COLD OPEN   – every episode opens mid-chaos. No introductions ever.
  2. FLAW ENGINE – every character has ONE flaw that creates the conflict
                   themselves (overconfidence, greed, cowardice...). Luck
                   never drives the plot; personality does.
  3. MYSTERY     – "The Watcher" / the red spiral appears as unexplained
                   clues (scene flag mystery=True → silhouette on screen).
  4. ESCALATION  – templates carry a tier (1-5). batch.py walks seeds up
                   the tiers, so a season rises from petty crime (t1) to
                   a broken moon (t5).
  5. CLIFFHANGER – the final scene always asks a new question or lands an
                   absurd reveal, built for loops and next-episode swipes.
  6. SHOW, DON'T EXPLAIN – punchlines arrive as extreme animation (fall,
                   shock, flex, fire) instead of dialogue.

VERB-DRIVEN ANIMATION (parse_actions reads the text as the shot list):
  jump/run/dance/spin/hit/duck/wave/sleep/walk  +  NEW: fire/shock/fall/flex
"""
import random

NAMES = ["leo", "nova", "trix", "puff", "milo", "zia"]
SETTINGS = ["forest", "night", "beach", "space", "snow", "underwater", "candy"]

# --- The flaw engine: personality that CAUSES the plot ---------------------
FLAWS = {
    "doris": "overconfidence – believes every plan is foolproof, especially hers",
    "apan": "greed – cannot walk past anything shiny, edible or both",
    "bosse": "laziness – will invent elaborate systems to avoid work",
    "boris": "grumpiness – trusts no plan, yet always follows them anyway",
    "leo": "clumsiness – great instincts, terrible landing gear",
    "nova": "stubbornness – would argue with a locked door",
    "trix": "perfectionism – measures twice, panics once",
    "zia": "naivety – believes everyone, including obvious villains",
    "puff": "snack obsession – all priorities rank below food",
    "milo": "drame queen tendencies – narrates his own trauma in real time",
    "kanin": "cowardice – screams first, saves the day accidentally",
    "kurre": "cowardice – professional at hiding, accidental hero",
    "stina": "recklessness – jumps before looking, looks great doing it",
}

# verb -> action (whole-word matching; write verbs near the name!)
VERBS = {
    "jump":  ["jump", "jumps", "jumped", "leap", "leaps", "leaped", "leapt",
              "bounced", "hopped"],
    "run":   ["run", "runs", "ran", "rush", "rushes", "rushed", "sprint",
              "sprints", "sprinted", "dash", "dashes", "dashed", "bolt",
              "bolts", "bolted", "fled", "charge", "charged", "charge,"],
    "dance": ["dance", "dances", "danced", "boogie", "boogied", "groove", "grooved"],
    "spin":  ["spin", "spins", "spun", "spinning", "twirl", "twirls", "twirled"],
    "hit":   ["hit", "hits", "punch", "punches", "punched", "smack", "smacked",
              "bonk", "bonks", "bonked", "whacked", "kicked", "slammed"],
    "duck":  ["duck", "ducks", "ducked", "dodged", "crouch", "crouched"],
    "wave":  ["wave", "waves", "waved", "saluted", "salute"],
    "sleep": ["sleep", "sleeps", "slept", "snooze", "snoozed", "napped",
              "snores", "snored"],
    "walk":  ["walk", "walks", "walked", "sneak", "sneaks", "sneaked",
              "snuck", "stroll", "strolled", "slunk", "crept"],
    # --- v6 superpowers & comedy beats ---
    "fire":  ["firebreathes", "blasts", "blasted", "roasts", "ignites",
              "incinerates", "scorches"],
    "shock": ["freezes", "froze", "gasp", "gasps", "gasped", "yelps", "yelped", "stunned"],
    "fall":  ["trips", "tripped", "faceplants", "faceplanted", "slips",
              "topples", "toppled", "tumbles", "tumbled", "flops", "stumbled"],
    "flex":  ["flexes", "flexed", "poses", "posed", "smirks", "struts", "strutted"],
    "powerup": ["awakens", "awakened", "unleashes", "unleashed", "erupts", "ascends"],
}
GROUP_WORDS = [" they ", " both ", " everyone ", " the duo ", " the two ",
               " together", " duo ", " the crew ", " the squad ", " the four "]


def parse_actions(text, cast_names):
    """Who does what in this line? Returns {cast_name: action|None}.

    Whole-word matching, nearest-verb-to-name wins within a 6-word radius,
    group words (they/both/together) hand the verb to the rest of the cast.
    """
    import re

    import engine
    low = (text or "").lower()
    padded = " " + low + " "
    words = [re.sub(r"[^\wåäöüé'-]", "", w) for w in low.split()]
    verb_at = {}
    for i, w in enumerate(words):
        for action, verbs in VERBS.items():
            if w in verbs:
                verb_at.setdefault(i, action)

    # Engelsk grammatik: verbet bör HELST komma EFTER namnet ("Doris spun").
    # Lika avstånd -> framåtriktat verb vinner; annars närmast vinner.
    found = {}
    for name in cast_names:
        found[name] = None
        aliases = engine.alias_group(name)
        best = None
        for iw, w in enumerate(words):
            if w not in aliases:
                continue
            for vi, action in verb_at.items():
                dist = abs(vi - iw)
                key = (dist, 0 if vi >= iw else 1)
                if dist <= 6 and (best is None or key < best[0]):
                    best = (key, action)
        if best:
            found[name] = best[1]

    if verb_at and any(g in padded for g in GROUP_WORDS):
        action = next(iter(verb_at.values()))
        for name in cast_names:
            if found[name] is None:
                found[name] = action
    return found


# ---------------------------------------------------------------------------
# SEASON 1 – escalation tiers 1-5. EVERY scene text is the shot list.
# Scene flags: reaction (! ? ♥ ★) · mystery (draws The Watcher) · props
# ---------------------------------------------------------------------------
TEMPLATES = [
    # ---------------- TIER 1: petty crime, huge egos ----------------
    {
        "title": "Bank Job Gone Bongo", "tier": 1, "cast": ["doris", "apan"],
        "scenes": [
            {"setting": "forest",
             "text": "'DROP THE WALRUS!' Doris sprinted through the pines with the loot. Rico tripped on the getaway rope. Obviously."},
            {"setting": "forest",
             "text": "'One instruction: do not touch the red vine,' said Doris. Rico flexed at it anyway. The alarm agreed."},
            {"setting": "forest",
             "text": "The mushroom guards charged. Doris blasted them with a sneeze of pure fire. New trick. Do not ask.",
             "props": "svamp"},
            {"setting": "forest",
             "text": "They bolted through the ravine together, screaming like professionals."},
            {"setting": "night", "mystery": True,
             "text": "High above the pines, a small dark figure watched them celebrate. It took notes."},
            {"setting": "night",
             "text": "Then the vault heaved open by itself. Inside: a map with BOTH their faces on it. 'Reload,' said Rico.",
             "reaction": "★"},
        ],
    },
    {
        "title": "The Beach Break-In", "tier": 1, "cast": ["doris", "apan"],
        "scenes": [
            {"setting": "beach",
             "text": "Rico's coconut fortress was under attack. The enemy: one extremely smug crab.",
             "props": "krabba, snäcka", "reaction": "!"},
            {"setting": "beach",
             "text": "'On three. One - THREE!' They charged down the beach together, faster than the waves."},
            {"setting": "beach",
             "text": "Rico leapt over the crab. Doris spun like a pink tornado. Strategy: pure chaos."},
            {"setting": "beach",
             "text": "The crab counterattacked. Doris ducked. Rico did not. Rico regrets everything."},
            {"setting": "beach",
             "text": "Victory. They danced on the ruins of the fortress until the sun gave up."},
            {"setting": "night",
             "text": "They both slept on the beach. In the tide, something enormous learned to knock. Three slow knocks.",
             "reaction": "★"},
        ],
    },
    # ---------------- TIER 2: the pattern appears ----------------
    {
        "title": "The Crab Uprising", "tier": 2, "cast": ["doris", "apan"],
        "scenes": [
            {"setting": "beach",
             "text": "Invasion at dawn. A thousand crabs clicked in perfect sync. Rico smiled: 'Finally, a fair fight.'",
             "props": "krabba"},
            {"setting": "beach",
             "text": "Doris charged the shell-wall. Rico ducked under a flying crab. Air support was NOT requested."},
            {"setting": "beach",
             "text": "The Crab King raised a golden claw. Rico bowed so fast he faceplanted into the sand."},
            {"setting": "beach",
             "text": "'DIPLOMACY FAILED!' They dashed across the sand together, threading snapping claws."},
            {"setting": "beach", "mystery": True,
             "text": "On the King's throne: the spiral symbol from the vault map. Doris froze solid. '...Not again.'"},
            {"setting": "night",
             "text": "Back at camp they both slept badly. The ocean knocked three times, politely, and waited for an answer.",
             "reaction": "★"},
        ],
    },
    {
        "title": "Zero-G Snack Protocol", "tier": 2, "cast": ["puff", "milo"],
        "scenes": [
            {"setting": "night",
             "text": "Milo pressed the red button. In his defense, it said 'Do Not Press For Free Snacks.'",
             "props": "raket", "reaction": "?"},
            {"setting": "space",
             "text": "Zero gravity. Puff gasped so hard he spun backwards into the snack cupboard. Priorities."},
            {"setting": "space",
             "text": "The vault gem drifted past. Milo leapt, missed, and kicked off the ceiling like a legend.",
             "props": "ädelsten"},
            {"setting": "space",
             "text": "Laser grid! They spun through the gaps together, leaving two perfect holes in the smoke."},
            {"setting": "space", "mystery": True,
             "text": "Through the window: a cloaked figure on the moon's rim, waving slowly. Nobody waves that slow."},
            {"setting": "night",
             "text": "They crashed home with the gem. It hummed a lullaby. The moon hummed back on the same frequency.",
             "reaction": "★"},
        ],
    },
    # ---------------- TIER 3: organized weirdness ----------------
    {
        "title": "Frost Protocol II: Union Break", "tier": 3, "cast": ["kurre", "stina"],
        "scenes": [
            {"setting": "snow",
             "text": "6 AM. The snowball drones picketed the fortress. Their signs read: 'THROW YOURSELF.'"},
            {"setting": "snow",
             "text": "Ash crouched behind a snowman, urgently blending in. Pix strutted straight up to the union boss.",
             "props": "snögubbe"},
            {"setting": "snow",
             "text": "Negotiations exploded. They dashed between the launchers together as the sky turned white."},
            {"setting": "snow",
             "text": "Pix smacked the biggest drone into surrender mode. Ash yelped from inside his snowman."},
            {"setting": "snow", "mystery": True,
             "text": "The boss drone's screen glitched: one red spiral, then static. Pix posed for a camera that was not there. Weird."},
            {"setting": "snow",
             "text": "They both snoozed in the victory bunker. Outside, the snow fell UP for exactly one second."},
        ],
    },
    {
        "title": "The Candy Vault Diaries", "tier": 3, "cast": ["trix", "zia"],
        "scenes": [
            {"setting": "candy",
             "text": "Zia licked the evidence. Trix screamed silently into a lollipop. Standard procedure.",
             "props": "tårta"},
            {"setting": "candy",
             "text": "The vault opened at 33 twists of the rainbow lock. Trix counted. Zia flexed at the security bees.",
             "props": "regnbåge"},
            {"setting": "candy",
             "text": "Caramel lasers woke up angry. They rushed between the gumdrop columns together."},
            {"setting": "candy",
             "text": "Zia blasted the lock with birthday-candle fire. Impressive. Wrong door, but impressive."},
            {"setting": "candy", "mystery": True,
             "text": "Inside: one gummy bear wearing the spiral badge. Trix gasped. The bear waved back. Bears cannot wave."},
            {"setting": "night",
             "text": "They fled home cakeless but alive. Behind them, unnoticed, the gummy bear started growing."},
        ],
    },
    # ---------------- TIER 4: the water remembers ----------------
    {
        "title": "Operation Splashback", "tier": 4, "cast": ["doris", "boris"],
        "scenes": [
            {"setting": "underwater",
             "text": "The coral mine sang its own countdown. Thirty seconds. Boris hated mines that sing.",
             "props": "snäcka"},
            {"setting": "underwater",
             "text": "Doris dashed between the steam vents. Boris ducked under a bubble-mine and lost his hat. Again.",
             "props": "fisk"},
            {"setting": "underwater",
             "text": "The eel guard demanded a password. Boris flexed and said 'password'. It worked. It never works."},
            {"setting": "underwater",
             "text": "Core overheating! They bolted for the surface together, towing the grumpy mine."},
            {"setting": "beach", "mystery": True,
             "text": "On the pier, a dark figure fished with no bait and smiled at Doris. The empty line hummed the lullaby."},
            {"setting": "night",
             "text": "They both slept with the mine wired to the doorbell. Somewhere below, the ocean learned a new song.",
             "reaction": "★"},
        ],
    },
    # ---------------- TIER 5: SEASON FINALE ----------------
    {
        "title": "The Spiral Awakens", "tier": 5, "cast": ["doris", "apan"],
        "scenes": [
            {"setting": "forest",
             "text": "Every screen in Pixelville glitched the same red spiral at once. Rico's sandwich glitched too. Unforgivable."},
            {"setting": "night",
             "text": "Portals ripped open over the rooftops. They charged into the nearest one together, armed with snacks.",
             "props": "portal"},
            {"setting": "space",
             "text": "On the shattered moon, Doris blasted a hole through the spiral gate with full fire-breath. 'Warned you about the tacos,' said Rico.",
             "props": "portal"},
            {"setting": "space",
             "text": "The Watcher finally stepped forward. Doris awakened her full aura in defiance. Rico ducked in the shockwave. Rude."},
            {"setting": "space", "mystery": True,
             "text": "They grabbed the master key and bolted back through the portal together as the moon reassembled in silence.",
             "props": "portal"},
            {"setting": "night",
             "text": "Back home: zero applause. The TV switched itself on: 'SEASON 1 COMPLETE. LOADING SEASON 2...' Rico choked on confetti.",
             "reaction": "★"},
        ],
    },
    # ---------------- TIER 2-3: neon + heist classics ----------------
    {
        "title": "Neon Jungle Run", "tier": 2, "cast": ["leo", "nova"],
        "scenes": [
            {"setting": "night",
             "text": "'OUT OF THE PARKING ZONE!' The tow-crane lifted their getaway cart. Leo chose this exact moment to juggle."},
            {"setting": "forest",
             "text": "'RUN!' They sprinted through the pines together as the alarm howled behind them."},
            {"setting": "forest",
             "text": "Leo leapt the ravine. Nova spun through the laser web. Nobody even blinked."},
            {"setting": "forest",
             "text": "The mushroom guards formed a wall. Nova bonked the biggest one. Leo toppled over a victory cone.",
             "props": "svamp"},
            {"setting": "night", "mystery": True,
             "text": "On the ridge above them, something tall watched and lit exactly one tiny green light. File under 'later'."},
            {"setting": "night",
             "text": "They both slept. The forest kept whispering one word, slow and proud: 'spiral'."},
        ],
    },
    {
        "title": "The Crystal Heist", "tier": 3, "cast": ["doris", "apan"],
        "scenes": [
            {"setting": "beach",
             "text": "03:00 hours. Rico spotted the glowing gem first - someone hid it in a shell by the sea.",
             "reaction": "!", "props": "ädelsten, snäcka"},
            {"setting": "beach",
             "text": "'Back off, it's mine,' grunted Doris, but Rico dashed ahead, faster than the tide."},
            {"setting": "forest",
             "text": "They sprinted through the jungle together, past vines and one very offended frog.",
             "props": "groda, svamp"},
            {"setting": "forest",
             "text": "Doris leapt onto the crystal platform. Rico tripped on the laser wire. The alarms sang opera."},
            {"setting": "forest", "mystery": True,
             "text": "Rico flexed over the gem while the security drone projected one single frame: the red spiral."},
            {"setting": "night",
             "text": "Mission complete. They danced on the rooftop while the house across the street slowly turned to watch. Houses do not turn.",
             "reaction": "★"},
        ],
    },
]

ESCALATION_TIERS = [t["tier"] for t in TEMPLATES]


KNOX_HOLLOW = [
    {
        "title": "Knox Hollow S01E01: The Signal", "tier": 5,
        "cast": ["jun", "mira", "knox", "grim"],
        "scenes": [
            {"setting": "city",      # COLD OPEN: mitt i action, direkt (research: AoT/Eva)
             "text": "A stranger fell out of the Knox Hollow sky at dusk. Jun sprinted across the rooftops before the sirens even started. Mira and Knox rushed after him. Even Grim ran, out of pure spite."},
            {"setting": "city", "mystery": True,   # WORLD + o besvarat mysterium
             "text": "High above the neon, something watched from the tallest antenna. It held a hand-drawn map with four faces circled in red."},
            {"setting": "city",      # karaktärer avslöjas av RÖRELSE före replik (Liz-tekniken)
             "text": "Mira crept toward the crash crater, reading every reflection in the windows. Knox saluted the crater three times, to be safe. Jun jumped straight in."},
            {"setting": "city",
             "text": "Grim strutted into the streetlight with a cape of stolen traffic banners. 'That signal belongs to ME,' he declared. Knox flexed back, purely out of confusion."},
            {"setting": "city",      # MATRIX-DUCKNING: slow-mo slås på automatiskt
             "text": "Grim smacked the pavement with a road sign. Jun ducked, smooth as streaming in 4K. Mira and Knox gasped in unison."},
            {"setting": "city",      # TRANSFORMATION: mech-powerup – mitt i stan!
             "text": "The old antenna ignited. Knox awakened his guardian protocol, older than the city itself. Jun froze mid-step. Mira froze. Even Grim froze. The pigeons froze too."},
            {"setting": "city",      # OP-låts-jakt: hela ganget i speedlines
             "text": "They bolted down Neon Avenue together – four shadows, one signal, zero plan."},
            {"setting": "city", "mystery": True, "reaction": "★",    # CLIFFHANGER (stämmorna i stan!)
             "text": "Behind them, every screen in the city blinked the same spiral. The Watcher took notes. It was smiling now. Probably."},
        ],
    },
]


TEMPLATES = KNOX_HOLLOW + TEMPLATES


def normalize_scenes(raw):
    out = []
    for s in raw:
        out.append({"setting": s.get("setting", "forest"),
                    "text": s.get("text") or s.get("en") or s.get("sv") or "",
                    "action": s.get("action") or None,
                    "reaction": s.get("reaction") or None,
                    "props": s.get("props"),
                    "mystery": s.get("mystery") or None})
    return out


def make_story(seed, lang="en", story_index=None, cast=None):
    import engine
    rng = random.Random(seed)
    tpl = TEMPLATES[story_index % len(TEMPLATES)] if story_index is not None else rng.choice(TEMPLATES)

    cast = [c.strip() for c in cast] if cast else list(tpl.get("cast") or [rng.choice(NAMES)])
    names = [engine.resolve_character(c)[3] for c in cast]
    name0 = names[0]
    name1 = names[1] if len(names) > 1 else name0

    title_key = "title" if "title" in tpl else "title_en"
    title = tpl[title_key].format(namn=name0, kompis=name1)
    scenes = normalize_scenes(
        [dict(s, text=(s.get("text") or s.get("en") or s["sv"]).format(namn=name0, kompis=name1))
         for s in tpl["scenes"]])
    beats = "\n".join("• " + s["text"] for s in scenes)
    cast_str = " & ".join(names)
    tier = tpl.get("tier", 1)
    description = (f"{title} ⚡ (mission tier {tier})\n\nStarring {cast_str}.\n\n{beats}\n\n"
                   "A PixelTube original – every frame drawn and every note composed by code.\n"
                   "Watch for the spiral. It's watching back. 🌀\n\n"
                   "#pixelanimation #cartoon #animatedseries #pixeluniverse")
    tags = ["pixel animation", "animated series", "cartoon", "pixel art",
            "comedy animation", "adventure cartoon", "agent dino", "original cartoon"]

    return {"title": title, "name": name0, "cast": cast, "scenes": scenes,
            "tier": tier,
            "tags": tags, "description": description, "seed": seed, "lang": "en"}
