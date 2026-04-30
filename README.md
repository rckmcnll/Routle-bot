# 🚌 Routle Bot — v5

A Bluesky bot for [Routle](https://routle.city) transit guessing games. Monitors a custom feed, tracks scores, posts daily leaderboards and threaded period standings, reacts to individual results with Portland-flavored commentary, tracks streaks, aces, DNFs, and milestones, manages a Routlers player list, and lets players opt out via DM.

Built for the [Portland TriMet Routle community](https://bsky.app/profile/pdxroutl.bsky.social). Easily adaptable to any Routle city or similar game.

---

## Features

### Daily leaderboard
Posted every day at a configured time. Shows each player's emoji result grid, rank, and a score distribution histogram. Handles Bluesky's 300-character limit — long player lists trim with `…and N more`.

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
Posted on a schedule as correctly threaded reply chains. Uses short handles and aligned columns. Long standings split across multiple posts automatically. Uses configurable ranking methods per period.

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
- **Guesses 2–5** — score-appropriate commentary
- **DNF** — commiseration
- **Streaks** — 🔥 suffix for consecutive days, new personal bests called out

### Milestones
Separate additional reply when a player hits:
- **Ace milestones** — at 5, 10, 25, 50, 100, 200, 500
- **Games played milestones** — at 3, 7, 25, 50, 100, 200, 300, 365
- **DNF milestones** — every 5 DNFs (celebrating persistence)

### Opt-out via DM
Players DM `stop` to the bot handle to stop receiving reply reactions. DM `start` to re-enable. Opted-out players still appear in leaderboards and standings.

### Personal stats via DM
Players DM `stats` to receive a personal stats card — games played, current and best streaks, aces, DNFs, average score, and a score distribution histogram. Works for all players regardless of opt-out status.

### Routlers list
Automatically adds every new player to a Bluesky curated list. Opted-out players are excluded.

### Fun standings
Ad-hoc novelty categories posted on demand as a threaded reply chain. Run `./run_bot.sh standings fun` to post all categories with enough data, or name a specific category. Available categories:

**Day of week** — `dow_monday` through `dow_sunday` — best avg score per player on that weekday.

**Score counts** — `score_2` through `score_5` — most times a player scored that exact value.

**Streaks** — `ace_streak` (longest consecutive ace run), `no_dnf_streak` (longest DNF-free run), `sub3_streak` (longest streak of scores under 3).

**Yahtzee-style** — `yahtzee` (5 identical scores in a row), `four_kind` (4 identical in any 7-day window), `three_kind` (3 identical in any 5-day window), `full_house` (all values 1–5 in a week), `straight` (scored 1,2,3,4,5 in order across 5 consecutive days).

**Comedy** — `dnf_royalty` (most DNFs, celebrated), `eternal_3` (most scores of exactly 3), `clutch_rate` (% of plays that were a guess-5 survival), `variance` (most chaotic scoring), `most_improved` (biggest avg drop from first 7 to last 7 games).

### Community records
After each daily, weekly, and monthly leaderboard post, the bot checks whether any records were broken — most players in a single day, week, or month, and most new players joining in a single day. If a record falls, a reply is posted as a nested thread under the leaderboard announcing the new high. Previous record and date are included for context. Records are stored in `records.json` and accumulate automatically from first run.
Multi-page standings use correct Bluesky thread structure (`root` always points to page 1, `parent` to the immediately preceding post). Each post is confirmed as indexed in the AppView before the next reply is posted. Failed posts are retried up to 3 times.

### Feed polling
Polls the feed every N minutes for near-realtime reactions. Leaderboards post on a separate scheduled cadence.

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
FEED_CREATOR_HANDLE = "feedowner.bsky.social"  # Owner of the Bluesky feed
FEED_SLUG           = "your-feed-slug"         # Slug from the feed URL
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
run              Fetch results + post today's leaderboard (once)
dry-run          Fetch results + print leaderboard (don't post)
collect          Fetch & save results only, no leaderboard or reactions
standings        Post an ad-hoc standings (see examples below)
backfill         Fire reactions for all results already in scores.json
rebuild-records  Recompute records.json from scratch using scores.json
announce         Post a freeform message from the bot account
start            Start the scheduler in the background
stop             Stop the background scheduler
status           Show scheduler status + score stats
logs             Tail the bot log (Ctrl+C to exit)
install          Set up virtual environment + install dependencies
create-list      Create the Routlers Bluesky list and print URI for config
help             Show help
```

### Standings examples

```bash
# Preview without posting
./run_bot.sh standings weekly --dry-run
./run_bot.sh standings monthly --dry-run

# Post immediately
./run_bot.sh standings weekly
./run_bot.sh standings monthly
./run_bot.sh standings yearly
./run_bot.sh standings participation

# Fun categories
./run_bot.sh standings fun                    # all fun categories as a thread
./run_bot.sh standings fun --dry-run          # preview
./run_bot.sh standings dow_tuesday            # Tuesday standings only
./run_bot.sh standings yahtzee                # Yahtzee Club only
./run_bot.sh standings dnf_royalty            # DNF leaderboard only

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
| `FUN_STANDINGS_TIME` | `""` | Time to post a random fun category daily. Empty string disables. DOW categories only fire on their matching weekday. No repeat within 14 days |
| `QUIET_HOURS_START` | `23:00` | Start of quiet window — reactions suppressed, scores still recorded |
| `QUIET_HOURS_END` | `07:00` | End of quiet window. Overnight ranges (e.g. 23:00–07:00) work correctly. Set both to `00:00` to disable |

### Standings

| Setting | Default | Description |
|---|---|---|
| `STANDINGS_SPOTS` | `0` | Players shown per standings (0 or None = all) |
| `RANKING_METHOD` | `adjusted` | Global default ranking algorithm |
| `WEEKLY_RANKING_METHOD` | `best_n` | Weekly override (None = use global) |
| `MONTHLY_RANKING_METHOD` | `adjusted` | Monthly override |
| `YEARLY_RANKING_METHOD` | `adjusted` | Yearly override |
| `CUSTOM_RANKING_METHOD` | `total` | Ad-hoc standings override |
| `MIN_DAYS_THRESHOLD` | `3` | Min days to qualify (used by `avg` only) |
| `BEST_OF_N_DAYS` | `5` | Best N days counted (used by `best_n`; 0 = all days) |

### Ranking methods

| Method | How it works | Best for |
|---|---|---|
| `total` | Raw total guesses. Lower = better. | Simple transparency |
| `avg` | Average guesses per day played. Players below `MIN_DAYS_THRESHOLD` shown but unranked. | Skill-first with a fairness floor |
| `adjusted` | Average across all days. Unplayed days count as DNF. | Monthly/yearly — balances skill and consistency |
| `best_n` | Average of best `BEST_OF_N_DAYS` scores. Off days and absences forgiven. | Weekly — "your best 5 of 7 count" |
| `weighted` | Inverted points × participation rate. | Smooth skill + attendance blend |
| `participation` | Most days played. Ties broken by average score. | Celebrating consistency over skill |

### Storage & integrations

| Setting | Default | Description |
|---|---|---|
| `NOTIFY_HANDLE` | `""` | Handle to DM when a leaderboard posts |
| `PIN_LEADERBOARD` | `True` | Pin each leaderboard to the bot's profile |
| `ROUTLERS_LIST_URI` | `""` | AT-URI of the Routlers curated list |
| `SCORES_FILE` | `scores.json` | Daily scores |
| `ACES_FILE` | `aces.json` | All-time ace counts |
| `STREAKS_FILE` | `streaks.json` | Consecutive day streaks |
| `OPTOUTS_FILE` | `optouts.json` | Opted-out handles |
| `KNOWN_PLAYERS_FILE` | `known_players.json` | Players added to Routlers list |
| `DNF_COUNTS_FILE` | `dnf_counts.json` | All-time DNF counts |
| `RECORDS_FILE` | `records.json` | Community records (player count highs, new player highs) |

### Logging

| Setting | Default | Description |
|---|---|---|
| `LOG_FILE` | `bot.log` | Path to the rotating log file |
| `LOG_LEVEL` | `INFO` | Verbosity — `DEBUG`, `INFO`, `WARNING`, or `ERROR` |
| `LOG_BACKUP_COUNT` | `3` | Rotated backups to keep (`bot.log.1` … `.N`). Each file is capped at 5 MB |

### Network

| Setting | Default | Description |
|---|---|---|
| `API_TIMEOUT` | `20` | Seconds before a Bluesky API request times out |
| `API_RETRIES` | `3` | Attempts on transient errors before giving up. Uses exponential backoff (1s, 2s, 4s …) |

### DM commands

Players can DM the bot handle with these keywords:

| Command | Action |
|---|---|
| `stop` | Stop receiving reply reactions. Still appears in leaderboards. |
| `start` | Re-enable reply reactions. |
| `stats` | Receive a personal stats card (see below). |
| `help` | Receive a list of all available DM commands. |

#### Stats card

Sending `stats` triggers a DM reply with a full personal breakdown:

```
📊 Routle stats — @busonly

🎮 47 games  🔥 streak 5d  (best 12d)
⭐ 8 aces  💀 3 DNFs
⌀ avg 2.38  ·  best 1

1▸ ████ 8
2▸ ████████ 16
3▸ ███████ 15
4▸ ██ 5
5▸ 0
✗▸ 3
```

Stats are drawn from all data files and work regardless of opt-out status.

---

## Customizing messages

All reaction and milestone messages live at the bottom of `config.py`. Edit freely — the bot picks randomly from each list. No code changes needed.

| List | Fired when | Placeholders |
|---|---|---|
| `FIRST_ACE_MESSAGES` | Player's very first ace (once, ever) | `{display_name}`, `{handle}` |
| `ACE_MESSAGES` | Every subsequent ace | `{display_name}`, `{handle}`, `{aces_line}` |
| `ACE_COUNT_LINES` | Appended to every ace message | `{aces}` |
| `DNF_MESSAGES` | All guesses wrong | `{display_name}`, `{handle}` |
| `SCORE_MESSAGES[2–5]` | Got it on guess 2–5 | `{display_name}`, `{handle}` |
| `MILESTONE_MESSAGES["ace"]` | Ace milestone hit | `{display_name}`, `{handle}`, `{count}` |
| `MILESTONE_MESSAGES["games"]` | Games played milestone | `{display_name}`, `{handle}`, `{count}` |
| `MILESTONE_MESSAGES["dnf"]` | DNF milestone (every 5) | `{display_name}`, `{handle}`, `{count}` |

Streak suffixes (🔥) are appended automatically — no need to add them to messages.

---

## Data files

All files created automatically on first run. Safe to edit manually.

| File | Contents |
|---|---|
| `scores.json` | `{"YYYY-MM-DD": {"handle": guess_number}}` |
| `aces.json` | `{"handle": total_ace_count}` |
| `streaks.json` | `{"handle": {"current": N, "best": N, "last_date": "YYYY-MM-DD"}}` |
| `optouts.json` | `["handle", ...]` |
| `known_players.json` | `{"handle": "did:plc:..."}` |
| `dnf_counts.json` | `{"handle": total_dnf_count}` |
| `records.json` | `{"daily_players": {"record": N, "date": "..."}, "weekly_players": {...}, "monthly_players": {...}, "new_players_day": {...}, "new_players": {"YYYY-MM-DD": N}}` |
| `fun_history.json` | `{"category_key": "YYYY-MM-DD", ...}` — last posted date per fun category, used to enforce the 14-day no-repeat window |

All saves are **atomic** — written to a `.tmp` file then renamed, so a crash mid-write never corrupts live data.

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

## Reliability notes

- **Retry logic** — each post is attempted up to `API_RETRIES` times before giving up, with exponential backoff (1s, 2s, 4s …). All API calls — feed fetches, logins, DM sends — share the same retry wrapper, so transient timeouts and connection resets recover automatically rather than killing the poll cycle
- **Configurable timeout** — `API_TIMEOUT` (default 20s) applies to every Bluesky API call. The previous 10s default was too tight for feed fetches returning up to 100 posts
- **Read-confirm** — after posting, the bot polls `app.bsky.feed.getPosts` until the post is confirmed visible in the AppView before continuing
- **Correct threading** — multi-page standings use `root` (always page 1) and `parent` (immediately preceding post) as required by the AT Protocol
- **Atomic writes** — all JSON data files use write-then-rename to prevent corruption
- **Request timeouts** — all Bluesky API calls have a 10-second timeout
- **Rotating log file** — `bot.log` is capped at 5 MB with up to `LOG_BACKUP_COUNT` backups (`bot.log.1`, `bot.log.2`, …), managed automatically via `logging.handlers.RotatingFileHandler`

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
├── routle_bot.py        # Core bot
├── run_scheduler.py     # Continuous scheduler
├── run_bot.sh           # Shell interface for all commands
├── config.example.py    # Template — copy to config.py and fill in
├── requirements.txt     # requests>=2.31.0
├── .gitignore
├── LICENSE              # MIT
└── README.md
```

---

## License

MIT — see [LICENSE](LICENSE).
