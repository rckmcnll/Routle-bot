# ─── Bluesky Bot Configuration ────────────────────────────────────────────────
# Copy this file to config.py and fill in your values.
# Never commit config.py with real credentials to version control!

# ── Bot account (the account that will POST the leaderboard) ──────────────────
BOT_HANDLE   = "your-bot.bsky.social"   # e.g. "routlebot.bsky.social"
BOT_PASSWORD = "xxxx-xxxx-xxxx-xxxx"       # Use an App Password from bsky Settings

# ── Custom feed to monitor ────────────────────────────────────────────────────
# Feed URL: https://bsky.app/profile/<FEED_CREATOR_HANDLE>/feed/<FEED_SLUG>
# Example:  https://bsky.app/profile/rockom.bsky.social/feed/routle
FEED_CREATOR_HANDLE = "rockom.bsky.social"  # Profile that owns the feed generator
FEED_SLUG           = "routle"              # The short name after /feed/

# ── Game settings ─────────────────────────────────────────────────────────────
GAME_NAME   = "Routle"
GAME_DOMAIN = "routle.city"
MAX_SQUARES = 5                          # Max possible 🟩 squares (max score)

# ── Schedule — all times are 24h local time (HH:MM) ──────────────────────────
LEADERBOARD_TIME     = "21:00"           # Daily leaderboard post time

# Day of week for the weekly leaderboard (0=Monday … 6=Sunday)
# The weekly post fires at LEADERBOARD_TIME on this day.
WEEKLY_LEADERBOARD_DAY = 6              # 6 = Sunday

# Monthly leaderboard posts at LEADERBOARD_TIME on the 1st of each month
# (covering the previous month — e.g. May 1st posts April's results).

# Yearly leaderboard posts at LEADERBOARD_TIME on January 1st
# (covering the previous year).

# How often to check the feed for new results and fire reactions (minutes)
POLL_INTERVAL_MINUTES = 5

# Number of players to show in weekly/monthly/yearly standings.
# Players beyond this cutoff are not shown.
# Set to 0 or None to show all eligible players.
# Posts are automatically split into threaded replies to fit Bluesky's character limit.
STANDINGS_SPOTS = 10

# ── Storage ───────────────────────────────────────────────────────────────────
# Handle to DM when a leaderboard post goes out (set to "" to disable)
NOTIFY_HANDLE = ""

# AT-URI of the Routlers list (run ./run_bot.sh create-list to generate)
# Set to "" to disable list management
ROUTLERS_LIST_URI = ""

SCORES_FILE   = "scores.json"
ACES_FILE     = "aces.json"           # All-time ace counts per player
STREAKS_FILE  = "streaks.json"        # Consecutive daily play streaks
OPTOUTS_FILE       = "optouts.json"        # Handles that have DM'd STOP
KNOWN_PLAYERS_FILE = "known_players.json"  # Players already added to the Routlers list

# ── Reaction messages ──────────────────────────────────────────────────────────
# Edit these freely — they're posted as replies to players' score posts.
#
# ACE_MESSAGES     : posted when someone gets a first-guess ace (score = 1)
#   Placeholders: {handle}    → the player's handle (with @)
#                 {aces_line} → a randomly chosen ACE_COUNT_LINES entry
#
# ACE_COUNT_LINES  : appended to ace messages to celebrate the milestone
#   Placeholders: {aces} → the player's all-time ace count
#
# DNF_MESSAGES     : posted when someone misses every stop (all 🟥)
#   Placeholders: {handle} → the player's handle (with @)

ACE_MESSAGES = [
    "🚲 FIRST GUESS?! {display_name} just rolled up on a fixie before anyone else even read the clue.\n\n  {aces_line}",
    "☕ {display_name} got it on the first try — probably fueled by a single-origin pour-over from a café with no sign out front.\n\n {aces_line}",
    "🌲 {display_name} nailed it first guess! Even the herons at Oaks Bottom are impressed.\n\n {aces_line}",
    "🌹 Roses are red, the answer was right — {display_name} aced it on the first try tonight!\n\n {aces_line}",
    "🛤️ {display_name} didn't even need the second stop hint. First guess, no hesitation, very Portland.\n\n {aces_line}",
    "🎸 {display_name} got a first-guess ACE 🟩⬛⬛⬛⬛ — as effortless as a Tuesday night at Mississippi Studios.\n\n {aces_line}",
    "🧇 {display_name} crushed it on guess one! Timbers Army energy.\n\n {aces_line}",
    "🐦 {display_name} — first guess ace! Swift as a Vaux Swift, smooth as the MAX gliding across the Tilikum Bridge.\n\n {aces_line}",
    "🌧️ {display_name} got it on the first try. You are now the honorary Grand Marshall of the Rose Parade.\n\n {aces_line}",
    "🧃 {display_name} first guess!! They identified that route faster than tickets sell out for Revolution Hall shows.\n\n {aces_line}",
    "🚨 STOP EVERYTHING. {display_name} got a FIRST GUESS ACE. The MAX has been rerouted in their honor.\n\n {aces_line}",
    "🦅 {display_name} saw the route, knew the route, answered the route. One guess. No notes. Absolutely no notes.\n\n {aces_line}",
    "📻 {display_name} — first guess, no hesitation. The kind of energy that makes KMHD want to write a song about you.\n\n {aces_line}",
    "🌁 {display_name} cut through the fog like they were born knowing every bus line in this city. First guess. Unmissable.\n\n {aces_line}",
    "🎯 {display_name} didn't browse. Didn't hover. Didn't second-guess. Just walked up and put it in on the first try like they own the place (they do).\n\n {aces_line}",
    "🚡 {display_name} — first guess ACE. Took the aerial tram straight to the answer. No stops. No transfers. No mercy.\n\n {aces_line}",
    "🧠 {display_name} has a TriMet map tattooed on the inside of their eyelids apparently. First guess. Not even close to close.\n\n {aces_line}",
    "🌮 {display_name} walked up to the food cart pod and ordered the right thing immediately. No menu-staring. First guess ace.\n\n {aces_line}",
    "🎻 {display_name} — first guess, and they didn't even look nervous. Meanwhile the rest of us are still tuning our instruments.\n\n {aces_line}",
    "🦦 {display_name} floated down the Willamette, cracked this route open like a river otter with a clam, and moved on. First guess. Effortless.\n\n {aces_line}",
    "🌿 {display_name} identified that route the way a true Portlander identifies artisanal sourdough — instantly, confidently, and with mild superiority.\n\n {aces_line}",
    "🚦 {display_name} hit every green light. First guess ace. The city bent to their will today and honestly? Fair.\n\n {aces_line}",
    "📍 {display_name} — pinned it. First guess. Didn't even open the map. The map opened for *them*.\n\n {aces_line}",
    "🎪 {display_name} showed up to Pickathon knowing exactly where their tent site was. First guess. Icon behavior.\n\n {aces_line}",
    "🌊 {display_name} rode the first guess like a wave straight into the answer. The Willamette is proud. We are all proud.\n\n {aces_line}",
    "🏔️ {display_name} summited on the first attempt. No base camp. No acclimatization. Just vibes and correct transit knowledge.\n\n {aces_line}",
    "🍵 {display_name} — first guess ace. Calm. Measured. Correct. The energy of someone who actually has their life together.\n\n {aces_line}",
    "🚌 The driver didn't even announce the stop and {display_name} already knew. First guess ace. They're built different.\n\n {aces_line}",
    "🌃 {display_name} knows this city after dark, in the rain, on a Tuesday. First guess. No hesitation. This is their Portland.\n\n {aces_line}",
    "🎖️ {display_name} — FIRST GUESS ACE. We're not saying they're a TriMet legend, but we're also not NOT saying that.\n\n {aces_line}",
]

ACE_COUNT_LINES = [
    "That's ace #{aces} for them — somebody call Powell's, this needs to be a book.",
    "All-time ace #{aces}! The leaderboard historians are shook.",
    "Ace #{aces} on record! Buying everyone at the Alibi a round.",
    "That's #{aces} all-time. The transit gods are pleased.",
    "Ace number {aces}! Someone page the Zoobombers.",
    "#{aces} aces total and still going. This is their city.",
    "Career ace #{aces}! See you at the top of the leaderboard and also Pittock Mansion.",
]

DNF_MESSAGES = [
    "😬 {display_name} — not a single stop recognized today. We've all been there. Go touch some grass at Mt Tabor and try again tomorrow.",
    "🚌 {display_name} missed every stop today. The Trimet driver would like a word with you.",
    "☔ {display_name} went 0 for 5. Even the rain couldn't wash away that struggle. Chin up — tomorrow's route is waiting.",
    "🌉 {display_name}, the Burnside Bridge has seen some things. Today, it saw your guesses. It said nothing, but it saw them.",
    "🧋 {display_name} — fully DNF'd. May we suggest a restorative bubble tea and a TriMet schedule deep-dive?",
    "🎭 {display_name} went 0/5. Somewhere, a mime on Mississippi is silently empathizing.",
    "🌲 {display_name} didn't get it today. The old growth doesn't judge. Neither do we. (Much.)",
    "🚲 {display_name} — even the sharrows knew which route it was. Tomorrow, friend. Tomorrow.",
    "🛤️ {display_name} missed all five stops. Not all who wander are lost, but today's guesses definitely were.",
    "🍩 {display_name} went DNF. Delicious Donuts have a hole in it for a reason — sometimes there's just nothing there.",
]

# SCORE_MESSAGES: reactions for scores 2–5 (keyed by guess number).
# Placeholder: {handle} → the player's handle (with @)
#
# Vibe guide:
#   2 → so close! one wrong guess before the answer
#   3 → solid, respectable, right in the middle
#   4 → a little rough, needed a few tries
#   5 → barely squeaked it out on the last guess

SCORE_MESSAGES = {
    2: [
        "😤 {display_name} — second guess. You were *right there*. The route was basically waving at you from across the Willamette.",
        "🚲 {display_name} got it on guess two. One stop away from glory. The Bike Portland crowd is sympathetic but not impressed.",
        "☕ {display_name} — so close! One wrong turn, like taking the wrong streetcar. Still, solid.",
        "🌉 {display_name} second guess. The answer was right over the bridge. You almost had it before the bridge opened.",
        "🌹 {display_name} — guess two! One redirect and you nailed it.",
        "🎸 {display_name} got it second try. Mississippi Studios doesn't let in people who guess first, anyway. You're on the list.",
        "🌧️ {display_name} — so close on guess two. Like almost making it to on the Max before the doors close. So. Close.",
        "🧇 {display_name} guess two! One bite off the mark. Still a solid slice, just not the pizza style you were hankering for.",
    ],
    3: [
        "👍 {display_name} — third guess, right down the middle. Solid. Dependable. Like the Portland Aerial Tram.",
        "🌲 {display_name} got it in three. Classic Portland: not flashy, not a disaster, just quietly competent.",
        "☕ {display_name} — three guesses. You took your time, like a proper pour-over. The result was worth it.",
        "🚌 {display_name} guess three. Right on schedule. Not the first bus, not the last bus — the one you actually planned to catch.",
        "🎭 {display_name} — three guesses, center stage. Not the opening act, not the encore. Solid main set energy.",
        "🌉 {display_name} got it in three. You crossed the bridge, you just took the Eastbank Esplanade first.",
        "🧃 {display_name} — guess three. Perfectly balanced, like a kombucha that actually tastes good. We see you.",
        "🛤️ {display_name} — three stops to find it. That's the Routle equivalent of a well-planned transfer. Respect.",
    ],
    4: [
        "😅 {display_name} — four guesses. You got there, but the bus had delays.",
        "🚲 {display_name} guess four. You made it, but you definitely took the long way around. Probably through the west hills.",
        "🌧️ {display_name} — four tries. That's like checking every pocket twice before finding your Hop card. But you found it!",
        "🚌 {display_name} got it on guess four. Classic Portland: took the scenic route through the fog and emerged, blinking, with the correct answer.",
        "☕ {display_name} — four guesses. That's a latte with an extra shot because the first three just weren't cutting it.",
        "🌹 {display_name} guess four. The roses in the rose garden don't bloom on the first try either. Technically.",
        "🎸 {display_name} — four tries. You opened four Honey Buckets before you found one with tp. Spared a square!",
        "🛤️ {display_name} needed four guesses. Somewhere a TriMet planner is gently updating your mental map.",
    ],
    5: [
        "😬 {display_name} — fifth guess. One more wrong and it would've been Japanese Garden therapy time. But you made it!",
        "🚲 {display_name} got it on guess five. You explored every wrong neighborhood first, which is honestly very Portland of you. Welcome home.",
        "🌧️ {display_name} — five guesses. That's like hitting every food cart in the pod before realizing you wanted the fish tacos the whole time.",
        "🚌 {display_name} guess five!  The ducks at Laurelhurst Park figured it out faster, but they also live on that pond. Home field advantage.",
        "☕ {display_name} — five tries. That's not a pour-over, that's a Dutch Bros coffee situation. But it got you there.",
        "🌉 {display_name} made it on guess five. Like a Pedalpalooza ride that takes a very scenic detour — chaotic, slightly confusing, ultimately triumphant.",
        "🎭 {display_name} — guess five. The curtain was coming down at the Schnitz and you shouted the answer from the back row. It counts!",
        "🍩 {display_name} got it on the last guess! Original Hotcake & Steak House line at 2am energy — questionable journey, correct destination.",
    ],
}
