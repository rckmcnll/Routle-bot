# 🚌 Routle Bot — v3

A Bluesky bot for [Routle](https://routle.city) transit guessing games. Monitors a custom feed, tracks scores, posts daily leaderboards and threaded period standings, reacts to individual results with Portland-flavored commentary, tracks streaks and aces, manages a Routlers player list, and lets players opt out via DM.

Built for the [Portland TriMet Routle community](https://bsky.app/profile/pdxroutl.bsky.social). Easily adaptable to any Routle city or similar game.

---

## What it does

### Daily leaderboard
Posted every day at a configured time. Shows each player's emoji result grid, rank, and a score distribution histogram. Handles Bluesky's 300-character limit gracefully — long player lists are trimmed with an `…and N more` note.

```
🏆 Routle Daily — April 9, 2026

🟩⬛⬛⬛⬛ 🥇 @busonly
🟩⬛⬛⬛⬛ 🥇 @willowashmaple
🟥🟩⬛⬛⬛ 🥉 @rockom
🟥🟥🟥🟩⬛ 4. @drmitchpdx

10 players today!

  1▸ ███████ 7
  2▸ █ 1
  4▸ █ 1
  5▸ █ 1
```

### Period standings (weekly / monthly / yearly)
Posted on a schedule as threaded replies. Uses short handles and aligned columns. Long standings split across multiple posts in a thread automatically.

```
🏆 Routle Weekly Standings — Apr 7–13, 2026

🥇 busonly          ⌀1.40 (b5)  7/7d ⭐
🥈 willowashmaple   ⌀1.80 (b5)  7/7d ⭐
🥉 rockom           ⌀2.20 (b5)  6/7d
4. drmitchpdx        ⌀3.60 (b5)  7/7d 1✗

7 players · 7/7 days played · best 5/7d
```

### Reactions
The bot replies to each player's score post with Portland-flavored commentary:

- **Guess 1 (ace)** — celebratory message with all-time ace count
- **Guesses 2–5** — score-appropriate commentary (close call, solid, long way round, barely made it)
- **DNF** — commiseration
- **Streaks** — 🔥 suffix when a player hits 2+ consecutive days, new personal bests called out

All messages are defined in `config.py` — edit freely, add more, no code changes needed.

### Opt-out via DM
Players DM `stop` to the bot handle to stop receiving reply reactions. The bot confirms with a DM and stops replying. DM `start` to re-enable. Opted-out players still appear in all leaderboards and standings.

### Routlers list
Automatically adds every new player to a Bluesky curated list. Opted-out players are excluded. Run once to create the list, paste the URI into config, and the bot handles the rest.

### Admin DM notification
DMs a configurable handle whenever a leaderboard or standings post goes out, with a link to the post.

### Feed polling
Polls the feed every N minutes for near-realtime reactions. Leaderboards post on a separate scheduled cadence — daily, weekly (configurable day), monthly (1st of month, covers previous month), yearly (Jan 1, covers previous year).

---

## Requirements

- Python 3.10+
- A Bluesky account for the bot
- A Bluesky App Password with **DM access enabled**

---

## Setup

### 1. Clone and install

```bash
git clone https://github.com/yourname/routle-bot.git
cd routle-bot
./run_bot.sh install
```

### 2. Configure

```bash
cp config.example.py config.py
```

Edit `config.py`. Required fields:

```python
BOT_HANDLE          = "your-bot.bsky.social"
BOT_PASSWORD        = "xxxx-xxxx-xxxx-xxxx"   # App Password with DM access
FEED_CREATOR_HANDLE = "rockom.bsky.social"     # Owner of the Bluesky feed
FEED_SLUG           = "routle"                 # Slug from the feed URL
```

> **App Password:** Bluesky → Settings → Privacy and Security → App Passwords → Create new → **check "Allow access to your direct messages"**

### 3. Create the Routlers list *(optional)*

```bash
./run_bot.sh create-list
```

Copy the printed URI into `config.py` as `ROUTLERS_LIST_URI`.

### 4. Test without posting

```bash
./run_bot.sh dry-run
./run_bot.sh standings weekly --dry-run
./run_bot.sh standings custom --dry-run   # all history to now
```

### 5. First run — import history and backfill reactions

```bash
./run_bot.sh collect              # import existing results silently
./run_bot.sh backfill --dry-run   # preview what reactions would fire
./run_bot.sh backfill             # fire reactions for existing results
```

### 6. Start the scheduler

```bash
./run_bot.sh start   # polls feed + posts leaderboards on schedule
./run_bot.sh logs    # follow live output
```

---

## Shell script reference

```
run          Fetch results + post today's leaderboard (once)
dry-run      Fetch results + print leaderboard (don't post)
collect      Fetch & save results only, no leaderboard or reactions
standings    Post an ad-hoc standings (see examples below)
backfill     Fire reactions for all results already in scores.json
start        Start the scheduler in the background
stop         Stop the background scheduler
status       Show scheduler status + score stats
logs         Tail the bot log (Ctrl+C to exit)
install      Set up virtual environment + install dependencies
create-list  Create the Routlers Bluesky list and print URI for config
help         Show help
```

### Standings examples

```bash
# Preview without posting
./run_bot.sh standings weekly --dry-run
./run_bot.sh standings monthly --dry-run
./run_bot.sh standings yearly --dry-run

# Post immediately
./run_bot.sh standings weekly
./run_bot.sh standings monthly
./run_bot.sh standings yearly

# Custom date range
./run_bot.sh standings custom                               # all history to now
./run_bot.sh standings custom --from 2026-04-01            # from date to now
./run_bot.sh standings custom --from 2026-04-01 --to 2026-04-09
./run_bot.sh standings custom --from 2026-04-01 --dry-run  # preview
```

---

## Configuration reference

### Core

| Setting | Default | Description |
|---|---|---|
| `BOT_HANDLE` | — | Bluesky handle of the bot account |
| `BOT_PASSWORD` | — | App Password (must have DM access) |
| `FEED_CREATOR_HANDLE` | — | Handle of the Bluesky feed generator owner |
| `FEED_SLUG` | — | Slug from the feed URL (`/feed/<slug>`) |
| `GAME_NAME` | `Routle` | Game name — matched in post text |
| `MAX_SQUARES` | `5` | Number of guess squares in the game |

### Schedule

| Setting | Default | Description |
|---|---|---|
| `LEADERBOARD_TIME` | `21:00` | Time for daily leaderboard and period standings (24h local) |
| `WEEKLY_LEADERBOARD_DAY` | `6` | Day of week for weekly standings (0=Mon … 6=Sun) |
| `POLL_INTERVAL_MINUTES` | `5` | How often to check the feed for new results |

### Standings

| Setting | Default | Description |
|---|---|---|
| `STANDINGS_SPOTS` | `10` | Players shown per standings (0 or None = all) |
| `RANKING_METHOD` | `best_n` | Ranking algorithm — see below |
| `MIN_DAYS_THRESHOLD` | `3` | Min days to qualify (used by `avg` only) |
| `BEST_OF_N_DAYS` | `5` | Best N days counted (used by `best_n`; 0 = all days) |

### Ranking methods

| Method | How it works | Best for |
|---|---|---|
| `total` | Raw total guesses. Lower = better. | Simple transparency |
| `avg` | Average guesses per day played. Players below `MIN_DAYS_THRESHOLD` are shown but unranked (—). | Skill-first with a fairness floor |
| `adjusted` | Average across all days. Unplayed days count as DNF. | Monthly/yearly — balances skill and consistency |
| `best_n` | Average of best `BEST_OF_N_DAYS` scores. Off days and absences forgiven. | Weekly — "your best 5 of 7 count" |
| `weighted` | Inverted points × participation rate. | Smooth skill + attendance blend |

### Storage & integrations

| Setting | Default | Description |
|---|---|---|
| `NOTIFY_HANDLE` | `""` | Handle to DM when a leaderboard posts (set `""` to disable) |
| `ROUTLERS_LIST_URI` | `""` | AT-URI of the Routlers curated list (set `""` to disable) |
| `SCORES_FILE` | `scores.json` | Daily scores |
| `ACES_FILE` | `aces.json` | All-time ace counts |
| `STREAKS_FILE` | `streaks.json` | Consecutive day streaks |
| `OPTOUTS_FILE` | `optouts.json` | Opted-out handles |
| `KNOWN_PLAYERS_FILE` | `known_players.json` | Players already added to Routlers list |

---

## Customizing messages

All reaction messages live at the bottom of `config.py`. Edit freely — the bot picks randomly from each list on every reaction. Add entries for variety, remove any you don't want. No code changes needed.

| List | Fired when | Placeholders |
|---|---|---|
| `ACE_MESSAGES` | First-guess ace | `{display_name}`, `{handle}`, `{aces_line}` |
| `ACE_COUNT_LINES` | Appended to ace messages | `{aces}` |
| `DNF_MESSAGES` | All guesses wrong (all 🟥) | `{display_name}`, `{handle}` |
| `SCORE_MESSAGES[2]` | Got it on guess 2 | `{display_name}`, `{handle}` |
| `SCORE_MESSAGES[3]` | Got it on guess 3 | `{display_name}`, `{handle}` |
| `SCORE_MESSAGES[4]` | Got it on guess 4 | `{display_name}`, `{handle}` |
| `SCORE_MESSAGES[5]` | Got it on guess 5 | `{display_name}`, `{handle}` |

Streak suffixes are appended automatically when relevant — you don't need to add them to messages.

---

## Data files

All files are created automatically on first run. Safe to edit manually to correct mistakes.

| File | Contents |
|---|---|
| `scores.json` | `{"YYYY-MM-DD": {"handle": guess_number}}` |
| `aces.json` | `{"handle": total_ace_count}` |
| `streaks.json` | `{"handle": {"current": N, "best": N, "last_date": "YYYY-MM-DD"}}` |
| `optouts.json` | `["handle", ...]` |
| `known_players.json` | `{"handle": "did:plc:..."}` |

---

## Running with systemd

```ini
[Unit]
Description=Routle Bot
After=network.target

[Service]
WorkingDirectory=/path/to/routle-bot
ExecStart=/path/to/routle-bot/.venv/bin/python run_scheduler.py
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
```

---

## Adapting to another city

```python
FEED_CREATOR_HANDLE = "feedowner.bsky.social"
FEED_SLUG           = "routle-chicago"
GAME_NAME           = "Routle"
GAME_DOMAIN         = "routle.city"
```

Then update the message lists in `config.py` with your city's local references.

---

## File structure

```
routle-bot/
├── routle_bot.py        # Core bot — scoring, reactions, leaderboards, DM handling
├── run_scheduler.py     # Continuous scheduler — polls feed + fires leaderboards
├── run_bot.sh           # Shell interface for all commands
├── config.example.py    # Template — copy to config.py and fill in
├── requirements.txt     # requests>=2.31.0
├── .gitignore           # Excludes config.py, *.json data files, .venv, logs
├── LICENSE              # MIT
└── README.md
```

---

## License

MIT — see [LICENSE](LICENSE).
