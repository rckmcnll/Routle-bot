# ─── Bluesky Bot Configuration ────────────────────────────────────────────────
# Copy this file to config.py and fill in your values.
# Never commit config.py with real credentials to version control!

# ── Bot account (the account that will POST the leaderboard) ──────────────────
BOT_HANDLE   = "your-bot.bsky.social"   # e.g. "routlebot.bsky.social"
BOT_PASSWORD = "xxxx-xxxx-xxxx-xxxx"       # Use an App Password from bsky Settings

# ── Custom feed to monitor ────────────────────────────────────────────────────
# Feed URL: https://bsky.app/profile/<FEED_CREATOR_HANDLE>/feed/<FEED_SLUG>
# Example:  https://bsky.app/profile/feedowner.bsky.social/feed/your-feed-slug
FEED_CREATOR_HANDLE = "feedowner.bsky.social"  # Profile that owns the feed generator
FEED_SLUG           = "your-feed-slug"         # The short name after /feed/

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

# Quiet hours — reactions are suppressed between these local times (scores still recorded).
# Set both to the same value (e.g. "00:00") to disable quiet hours entirely.
QUIET_HOURS_START = "23:00"
QUIET_HOURS_END   = "07:00"

# Fun standings — one random category posted at this time each day (set to "" to disable)
FUN_STANDINGS_TIME = "14:00"

# Number of players to show in weekly/monthly/yearly standings.
# Players beyond this cutoff are not shown.
# Set to 0 or None to show all eligible players.
# Posts are automatically split into threaded replies to fit Bluesky's character limit.
STANDINGS_SPOTS = 0

# ── Ranking method for period standings ────────────────────────────────────────
# Controls how players are ranked in weekly, monthly, and yearly standings.
#
# "total"    Raw total guesses. Lower = better. Rewards playing every day.
#            (Original behaviour — simple and transparent.)
#
# "avg"      Average guesses per day played. Players below MIN_DAYS_THRESHOLD
#            are shown but marked ineligible (—) and sorted to the bottom.
#            Rewards skill; use MIN_DAYS_THRESHOLD to ensure fairness.
#
# "adjusted" Average across ALL days in the period. Unplayed days count as
#            a DNF (MAX_SQUARES+1 guesses). Rewards both skill and consistency
#            without a hard cutoff. Recommended for monthly/yearly.
#
# "best_n"   Average of the player's best BEST_OF_N_DAYS scores. Forgives
#            off days and absences. "Your best 5 of 7 rounds count."
#            Recommended for weekly. Set BEST_OF_N_DAYS = 0 to use all days.
#
# "weighted" Inverted points (first guess = max points) multiplied by
#            participation rate. Blends skill and attendance smoothly.

RANKING_METHOD      = "adjusted"   # "total" | "avg" | "adjusted" | "best_n" | "weighted"
MIN_DAYS_THRESHOLD  = 3          # Minimum days to be eligible (used by "avg" only)
BEST_OF_N_DAYS      = 5          # Best N days counted (used by "best_n"; 0 = all days)

# Each period can have its own ranking method, or inherit the default.
# Set to None to use the default RANKING_METHOD for that period.
#
# Recommended:
#   weekly  → "best_n"    (best 5 of 7 — forgives a bad day)
#   monthly → "adjusted"  (unplayed = DNF — rewards consistency over a month)
#   yearly  → "adjusted"  (same logic, longer horizon)
#   custom  → "total"     (simple and transparent for ad-hoc queries)

WEEKLY_RANKING_METHOD   = "best_n"    # Weekly standings ranking (None = use RANKING_METHOD)
MONTHLY_RANKING_METHOD  = "adjusted"  # Monthly standings ranking
YEARLY_RANKING_METHOD   = "adjusted"  # Yearly standings ranking
CUSTOM_RANKING_METHOD   = "total"     # Ad-hoc custom standings ranking

# ── Storage ───────────────────────────────────────────────────────────────────
# Pin the leaderboard post to the bot's profile after posting
# Each new leaderboard replaces the previous pin
PIN_LEADERBOARD = True

# Handle to DM when a leaderboard post goes out (set to "" to disable)
NOTIFY_HANDLE = ""

# AT-URI of the Routlers list (run ./run_bot.sh create-list to generate)
# Set to "" to disable list management
ROUTLERS_LIST_URI = ""

SCORES_FILE        = "data/scores.json"
ACES_FILE          = "data/aces.json"           # All-time ace counts per player
STREAKS_FILE       = "data/streaks.json"        # Consecutive daily play streaks
OPTOUTS_FILE       = "data/optouts.json"        # Handles that have DM'd STOP
KNOWN_PLAYERS_FILE = "data/known_players.json"  # Players already added to the Routlers list
DNF_COUNTS_FILE    = "data/dnf_counts.json"     # All-time DNF counts per player
RECORDS_FILE       = "data/records.json"        # Community records (player count highs etc.)
FUN_HISTORY_FILE   = "data/fun_history.json"    # Last posted date per fun category

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_FILE         = "logs/bot.log"   # Path to the rotating log file
LOG_LEVEL        = "INFO"      # DEBUG | INFO | WARNING | ERROR
LOG_BACKUP_COUNT = 3           # Number of rotated backup files to keep (e.g. bot.log.1 … .3)

# ── Network ───────────────────────────────────────────────────────────────────
API_TIMEOUT = 20   # Seconds before a Bluesky API request times out
API_RETRIES = 3    # Attempts on transient errors (timeouts, connection resets) before giving up

# ── Head-to-Head Challenge settings ──────────────────────────────────────────

# File that stores all challenge state (created automatically)
CHALLENGES_FILE = "data/challenges.json"
REACTIONS_FILE  = "data/reactions.json"    # Post URIs already reacted to (dedup guard)

# Characters in a generated invite code (uppercase alphanum, no ambiguous 0/O/1/I/L)
CHALLENGE_CODE_LENGTH = 6

# Maximum participants per challenge (set to None for unlimited)
CHALLENGE_MAX_PARTICIPANTS = 20

# Time of day (HH:MM, 24h local) to run the challenge tick:
#   - activates challenges that start today
#   - sends daily standings DMs to all participants
#   - finalizes challenges that ended yesterday and sends the final report
# Set to None to disable (challenges will never activate automatically).
# Tip: set slightly after LEADERBOARD_TIME so daily scores are fully ingested.
CHALLENGE_REPORT_TIME = "10:30"

# Number of best daily scores that count toward the final ranking (of 7 days).
# DNF counts as 7 for challenge ranking purposes.
CHALLENGE_BEST_OF = 5

# Messages sent when a player creates a challenge. {code} is the invite code.
CHALLENGE_CREATED_MESSAGES = [
    "Challenge accepted! Your invite code is {code} — valid for 24 hours. "
    "Share it with your rivals and tell them to DM it to me. "
    "Contest starts tomorrow and runs for 7 days. Best 5 of 7 scores wins. 🚊",
    "Oh, you want beef? Your challenge code is {code}. "
    "Send it to whoever thinks they can out-Routle you. "
    "Registration closes at midnight, contest kicks off tomorrow. 🚌",
    "A challenger appears! Code: {code} — good for 24 hours. "
    "Rope in your fellow transit nerds. Best 5 of 7 scores wins. 🚋",
    "Your duel is registered. Invite code: {code}. "
    "Share it around — anyone who DMs me that code joins the fun. "
    "Week-long battle starts tomorrow, daily standings delivered here. 🗺️",
]

# Messages sent when a player joins a challenge. {code} is the invite code.
CHALLENGE_JOINED_MESSAGES = [
    "You're in! Challenge {code} starts tomorrow — I'll DM you standings each day. "
    "Best 5 of 7 scores wins. 🚊",
    "Tickets punched! You've joined challenge {code}. "
    "Runs for 7 days starting tomorrow, daily standings in your DMs. 🚌",
    "Boarded! You're registered for challenge {code}. "
    "Starts tomorrow, standings delivered daily. Best of luck! 🚋",
]

# Sent when an invite code is not found or the challenge is complete.
CHALLENGE_NOT_FOUND_MESSAGE = (
    "Hmm, I don't recognize that code. It may have expired or been mistyped — "
    "codes are valid for 24 hours. Ask your challenger for a fresh one!"
)

# Sent when a challenge has reached CHALLENGE_MAX_PARTICIPANTS.
CHALLENGE_FULL_MESSAGE = (
    "Sorry, that challenge is already full. Ask them to start a new one!"
)

# Sent when the player is already enrolled in that challenge.
CHALLENGE_ALREADY_IN_MESSAGE = (
    "You're already registered for that challenge — starts tomorrow!"
)

# ── Reaction messages ──────────────────────────────────────────────────────────
# Edit these freely — they're posted as replies to players' score posts.
#
# FIRST_ACE_MESSAGES : posted exactly once — the very first time a player gets an ace.
#   Placeholders: {display_name}, {handle}
#   No {aces_line} — this is their origin story, not a count update.
#
# ACE_MESSAGES     : posted on every subsequent ace (score = 1, ace_count > 1)
#   Placeholders: {handle}    → the player's handle (with @)
#                 {aces_line} → a randomly chosen ACE_COUNT_LINES entry
#
# ACE_COUNT_LINES  : appended to ace messages to celebrate the milestone
#   Placeholders: {aces} → the player's all-time ace count
#
# DNF_MESSAGES     : posted when someone misses every stop (all 🟥)
#   Placeholders: {handle} → the player's handle (with @)

FIRST_ACE_MESSAGES = [
    "🟩 FIRST ACE. {display_name} has entered the chat, taken one look at the route, and immediately left having already won. Welcome to the club. There are no membership cards. There is only knowing.",
    "🎉 {display_name} — FIRST GUESS on their very first ace! Somewhere a TriMet driver is nodding slowly. They've seen this once before. In a dream.",
    "🚌 Hold on. {display_name} just got their first ace. On the first guess. We need a moment. The herons at Oaks Bottom need a moment. Everyone take a breath.",
    "⭐ A star is born. {display_name} has achieved their first first-guess ace and we are legally required to inform you that this changes everything. Congratulations. You are different now.",
    "🗺️ {display_name} looked at the puzzle, knew the answer, typed the answer, and was correct. First ace. Their Portland brain has fully activated. There is no going back.",
    "🚦 First ace for {display_name}! The traffic lights on Burnside turned green all the way down in their honor. TriMet is aware. They are pleased.",
    "🌧️ {display_name} — first ace unlocked. You have been granted honorary knowledge of every bus schedule in the metro area. It will come to you in your dreams now. This is normal.",
    "🎸 {display_name} just got their first ace and we're going to be honest with you: we didn't think this day would come so soon. We're not ready. The bot is not ready. Please hold.",
    "🦦 FIRST ACE: {display_name}. The river otters on the Willamette have been notified. They are doing their little celebration float. You earned this.",
    "🌹 {display_name} has cracked the code on their very first ace attempt. The roses in the Rose Garden are blooming slightly harder right now. Science cannot explain it.",
]

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
    "🎲 NATURAL 20. {display_name} rolled a critical hit on the very first guess. The Dungeon Master nods. The table erupts. {aces_line}",
    "⚔️ {display_name} — first guess, no hesitation. A paladin at full hit points, riding into the route with divine certainty. {aces_line}",
    "🧙 {display_name} cast *Identify* on the route and instantly knew its name and properties. First guess. Legendary spell slot well spent. {aces_line}",
    "🐉 The bard rolled Persuasion at advantage, got a 28, and the route just told {display_name} the answer. First guess. Bards, man. {aces_line}",
    "🗺️ {display_name} consulted the tavern map, rolled Perception — nat 20 — and identified the route before anyone else had even drawn their character sheet. {aces_line}",
    "🌅 {display_name} — first guess ace. The sun rose, the puzzle opened, and the answer was already known. Some people are simply awake before the rest of us. {aces_line}",
    "🎺 FANFARE FOR {display_name}. First guess. The herald is already composing the proclamation. {aces_line}",
    "🧲 {display_name} was drawn to the correct answer like a compass to true north. First guess. Magnetic. {aces_line}",
    "🪄 {display_name} tapped the puzzle once, said the word, and it was done. First guess. We don't ask how. {aces_line}",
    "🦁 THE LION DOES NOT DELIBERATE. {display_name}: first guess, zero hesitation, total dominance. {aces_line}",
    "🌸 {display_name} arrived, glanced at the route, nodded once, and typed. First guess. Understated greatness. {aces_line}",
    "⚡ Faster than light. Faster than thought. {display_name} answered before the question had fully formed. Guess one. {aces_line}",
    "🎓 {display_name} has studied the routes. Not casually — *studied* them. First guess is the degree. {aces_line}",
    "🌊 The tide knows where it's going. {display_name} knew where the route was going. First guess. Inevitable. {aces_line}",
    "🔭 {display_name} has the long view. Saw the route from a mile away. First guess. The telescope was already pointed. {aces_line}",
    "🎯 No wind. No noise. Just {display_name} and the answer, and the sound of a first guess landing perfectly. {aces_line}",
    "🦋 {display_name} landed on the answer before the question even finished opening its wings. First guess. Effortless transformation. {aces_line}",
    "🍀 Is it luck? Is it skill? With {display_name} on guess one, does it matter? The answer is correct. That's all we know. {aces_line}",
    "🌙 Other people sleep. {display_name} dreams of routes and wakes up knowing the answer. First guess. {aces_line}",
    "📐 {display_name} calculated the exact angle of approach and executed. First guess. Geometry has never been so satisfying. {aces_line}",
    "🐬 {display_name} echolocated the route from a kilometre away. First guess. We don't fully understand it but we respect it. {aces_line}",
    "🎪 Ladies and gentlemen: {display_name}. First guess. No net. No rehearsal. The crowd did not expect this but the crowd is pleased. {aces_line}",
    "🧊 Cool as ice. {display_name} looked at the route, looked at the answer, didn't blink. First guess. Unrattled. Unbothered. Correct. {aces_line}",
    "🌺 {display_name} — first guess. Some people bloom slowly. {display_name} arrived already in full flower. {aces_line}",
    "🏹 The arrow left the bow before the target had stopped moving. First guess. {display_name} shoots first and is correct. {aces_line}",
    "🎰 {display_name} walked up to the machine, put in one coin, and hit the jackpot. First guess. The odds were irrelevant. {aces_line}",
    "☀️ {display_name} — first guess ace. The sun does not wonder whether to rise. It rises. {display_name} does not wonder. They answer. {aces_line}",
    "🪸 {display_name} found the route the way coral finds the reef — like it was always there, like there was never any question. First guess. {aces_line}",
    "🔑 {display_name} had the key before the lock was even mentioned. First guess. The door: open. The route: identified. {aces_line}",
    "🌟 First guess. Not second. Not third. *First.* {display_name} is doing something the rest of us are only beginning to understand. {aces_line}",
]

ACE_COUNT_LINES = [
    # ── Portland ───────────────────────────────────────────────────────────────
    "That's ace #{aces} for them — somebody call Powell's, this needs to be a book.",
    "All-time ace #{aces}! The leaderboard historians are shook.",
    "Ace #{aces} on record! Buying everyone at the Alibi a round.",
    "That's #{aces} all-time. The transit gods are pleased.",
    "Ace number {aces}! Someone page the Zoobombers.",
    "#{aces} aces total and still going. This is their city.",
    "Career ace #{aces}! See you at the top of the leaderboard and also Pittock Mansion.",
    "Ace #{aces}. The herons at Oaks Bottom have been notified.",
    "#{aces} first-guess aces. A plaque is being commissioned for the Hollywood MAX platform.",
    "Ace #{aces} logged. The TriMet archivist is updating the permanent record.",
    "That's #{aces} aces. Word has reached the top of the Fremont Bridge.",
    # ── Literary / classical ───────────────────────────────────────────────────
    "Ace #{aces}. 'What a piece of work is a man' — Shakespeare didn't know about Routle, but he would have.",
    "#{aces} aces. Homer could have written an epic about this. Several, actually.",
    "Ace the {aces}th! As Tolkien wrote: 'Even the smallest person can change the course of the future.' This is not small.",
    "#{aces} aces on the board. Dante had nine circles. This person has {aces} aces. Different kind of journey.",
    "Ace #{aces}. Chekhov said if a route appears in act one, it must be identified by act one. Done.",
    "That's {aces} aces. Somewhere, a poet is drafting an ode. It will not be published but it will be heartfelt.",
    # ── RPG / gaming ──────────────────────────────────────────────────────────
    "Ace #{aces}! Achievement unlocked: *Transit Oracle*.",
    "#{aces} aces. Experience points awarded. The skill tree is fully lit.",
    "Ace number {aces}. New title unlocked: *Grand Master of the First Guess*.",
    "#{aces} aces — that's a legendary drop rate. The RNG favours the prepared.",
    # ── Cinematic / dramatic ───────────────────────────────────────────────────
    "Ace #{aces}. The crowd goes absolutely feral.",
    "#{aces} aces and the montage keeps getting longer.",
    "Ace {aces}. Cut to: the scoreboard. Freeze frame. Credits roll.",
    "That's ace #{aces}. The sequel writes itself.",
    # ── Understated / dry ─────────────────────────────────────────────────────
    "Ace #{aces}. Noted.",
    "#{aces}. Just #{aces}.",
    "Ace number {aces}. Business as usual, apparently.",
    "#{aces} aces. We've stopped being surprised. We remain impressed.",
    "Ace #{aces}. The bar was high. The bar has been cleared. The bar is now higher.",
    # ── Wild ──────────────────────────────────────────────────────────────────
    "ACE #{aces}!! Scientists are studying this person. The data is unprecedented.",
    "#{aces} aces. A small animal somewhere just looked up, sensed something, and went back to sleep.",
    "Ace {aces}. The number {aces}. Let that sink in. Take your time. {aces}.",
    "#{aces} ACES. The leaderboard is not a leaderboard anymore. It is a shrine.",
    "Ace #{aces}. We asked a psychic. They said: 'yes, this was always going to happen.' They also said to drink more water.",
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

# ── Milestone thresholds ─────────────────────────────────────────────────────
# Ace counts that trigger a milestone reply (in addition to every 100 after 100)
ACE_MILESTONES     = {5, 10, 25, 50, 100, 200, 500}

# Games-played counts that trigger a milestone reply
GAMES_MILESTONES   = {3, 7, 25, 50, 100, 200, 300, 365}

# Fire a DNF milestone every N DNFs
DNF_MILESTONE_EVERY = 5

# ── Milestone messages ────────────────────────────────────────────────────────
# Fired as a separate reply when a player hits a milestone.
# Placeholders: {display_name}, {handle}, {count}
#
# ace   → fires at aces 5, 10, 25, 50, 100, 200, 500 (and every 100 after)
# games → fires at games played 3, 7, 25, 50, 100, 200, 300, 365
# dnf   → fires every 5 DNFs

MILESTONE_MESSAGES = {
    "ace": [
        "{stars} 🏅 {display_name} — {count} first-guess aces. This is not a hobby. This is a calling.",
        "{stars} ⭐ {count} aces for {display_name}. The hall of fame committee has convened. The vote was unanimous.",
        "{stars} 🏆 {count} aces! {display_name} is not playing the same game as the rest of us anymore.",
        "{stars} 🎖️ {display_name} has {count} all-time aces. There should be a statue. We are looking into it.",
        "{stars} 🌟 {count} first-guess aces for {display_name}. Future generations will study this.",
        "{stars} 🗺️ {count} aces. {display_name} doesn't consult the map. The map consults {display_name}.",
        "{stars} 🚌 {count} aces! TriMet has quietly begun rerouting buses in {display_name}'s honour.",
        "{stars} 🎲 {count} aces. That's not luck. That's not skill. That's something we don't have a word for yet.",
        "{stars} 📜 Let it be recorded: {display_name}, {count} aces. The scribe's hand trembled slightly while writing this.",
        "{stars} 🔑 {count} aces for {display_name}. At this point they probably *wrote* some of these routes.",
    ],
    "games": [
        "🎮 {display_name} has played {count} games of Routle. A pattern is forming. It's a beautiful pattern.",
        "🚌 {count} games played! {display_name} has now guessed more routes than most people know exist.",
        "📅 {display_name} — {count} games in. The commitment is noted. The commitment is admired.",
        "🌱 {count} games for {display_name}. Something is growing here. Water it daily.",
        "🏃 {display_name} has shown up {count} times. Showing up is half the battle. {display_name} is winning the battle.",
        "🗓️ {count} games played by {display_name}. This is not a phase. This is a lifestyle.",
        "⭐ {display_name}: {count} games. The regulars know your name. The bus knows your stop.",
        "🌳 {count} games for {display_name}. The roots go deep. This city is in their bones.",
        "📊 {display_name} has {count} games logged. The analysts are compiling a report. The report is glowing.",
        "🚦 {count} games for {display_name}. {count} days of showing up. That means something.",
    ],
    "dnf": [
        "💪 {display_name} — {count} DNFs and still here. That's not failure. That's devotion.",
        "🌧️ {count} DNFs for {display_name}. The rain falls on everyone. {display_name} keeps coming back.",
        "🔥 {display_name} has DNF'd {count} times and returned every single time. This is the human spirit in action.",
        "🚲 {count} DNFs. {display_name} has fallen off the bike {count} times and gotten back on {count} times. Hero.",
        "🌊 {count} DNFs for {display_name}. The sea does not apologise. Neither does the route. Neither does {display_name}.",
        "📖 The story of {display_name}: {count} chapters of not quite getting it, and {count} chapters of coming back anyway. Still being written.",
        "🏔️ {count} DNFs. Every mountaineer has mornings the summit won. {display_name} keeps lacing up the boots.",
        "⚡ {display_name}: {count} DNFs. {count} times the route won the day. {count} times {display_name} came back for more. The score is {count}-{count}. Nobody's quitting.",
        "🌱 {count} DNFs for {display_name}. Some things grow slowly. The important ones usually do.",
        "🎯 {count} misses logged for {display_name}. Every great archer has a pile of arrows that didn't land. The next one might.",
    ],
}
