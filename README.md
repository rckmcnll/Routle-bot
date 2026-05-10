# 🚌 Routle Bot — v6.5

A Bluesky bot for [Routle](https://routle.city) transit guessing games. Monitors a custom feed, tracks scores, posts daily leaderboards and threaded period standings, reacts to individual results with Portland-flavored commentary, tracks streaks, aces, DNFs, and milestones, manages a Routlers player list, follows new players, and supports a full suite of player DM commands.

Built for the [Portland TriMet Routle community](https://bsky.app/profile/pdxroutl.bsky.social). Easily adaptable to any Routle city or similar game.

---

## What's new in v6.5

### Head-to-head challenges
Players can now challenge each other to private 1-week tournaments entirely via DM. The bot handles the full lifecycle: invite code generation, a ready-to-forward invite message, accept notifications to the creator, daily standings DMs to all participants throughout the week, and a final report with champion on conclusion. Scoring uses best-of-5-of-7 days (configurable), with DNF counting as 7. Late joiners are supported — only scores from their join date onward count. Two new DM commands: `CHALLENGE` to start a contest, `MYSTATUS` to check active challenges and current rank.

---

## Features

### Daily leaderboard
Posted every day at a configured time. Shows each player's emoji result grid, rank, and a score distribution histogram. Tied players are broken by all-time average score. Handles Bluesky's 300-character limit — long player lists split across continuation posts automatically.

```
🏆 Routle Daily — April 9, 2026

🟩⬛⬛⬛⬛ 1. @𝚋𝚞𝚜𝚘𝚗𝚕𝚢
🟩⬛⬛⬛⬛ 1. @𝚠𝚒𝚕𝚕𝚘𝚠𝚊𝚜𝚑𝚖𝚊𝚙𝚕𝚎
🟥🟩⬛⬛⬛ 9. @𝚛𝚘𝚌𝚔𝚘𝚖

12 players today!

  1▸ ███████ 8
  2▸ █ 1
  5▸ █ 1
  ✗▸ █ 2
```

### Period standings (weekly / monthly / yearly)
Posted on a schedule as correctly threaded reply chains. Uses Unicode Mathematical Monospace formatting with figure-space padding for aligned columns. Long standings split across multiple posts automatically. Uses configurable ranking methods per period.

```
𝟷. 𝚖𝚒𝚌𝚔𝚓𝚙𝚐         ⌀𝟷.𝟶𝟶 (𝚋𝟻)  𝟽/𝟽𝚍 ⭐
𝟷. 𝚠𝚒𝚕𝚕𝚘𝚠𝚊𝚜𝚑𝚖𝚊𝚙𝚕𝚎  ⌀𝟷.𝟶𝟶 (𝚋𝟻)  𝟼/𝟽𝚍 ⭐
𝟹. 𝚔𝚑𝚛𝚒𝚜𝚜𝚘𝚍𝚎𝚗      ⌀𝟷.𝟶𝟶 (𝚋𝟸)  𝟸/𝟽𝚍 ⭐
𝟷𝟶. 𝚋𝚞𝚜𝚘𝚗𝚕𝚢        ⌀𝟷.𝟸𝟶 (𝚋𝟻)  𝟼/𝟽𝚍 ⭐
```

### Reactions
The bot replies to each player's score post with Portland-flavored commentary:
- **First ace ever** — special one-time celebratory message from `FIRST_ACE_MESSAGES`
- **Subsequent aces** — celebratory message with all-time ace count
- **Guesses 2–5** — score-appropriate commentary
- **DNF** — commiseration
- **Streaks** — 🔥 suffix for consecutive days, new personal bests called out

Reactions are suppressed during configurable quiet hours. Opted-out players still appear in leaderboards.

### Milestones
Separate additional reply when a player hits configurable thresholds:
- **Ace milestones** — at 5, 10, 25, 50, 100, 200, 500 (and every 100 thereafter)
- **Games played milestones** — at 3, 7, 25, 50, 100, 200, 300, 365
- **DNF milestones** — every 5 DNFs (celebrating persistence)

### Auto-follow
The bot follows each new player from the bot account on their first result, and adds them to the Routlers curated list (opt-outs excluded from list but still followed).

### Fun standings
Ad-hoc novelty categories posted on demand as a threaded reply chain, each with a description post appended. A random category can also be scheduled daily. Available categories:

**Day of week** — `dow_monday` through `dow_sunday` — best avg score per player on that weekday.

**Score counts** — `score_2` through `score_5` — most times a player scored that exact value.

**Streaks** (minimum 3 consecutive days) — `ace_streak`, `no_dnf_streak`, `sub3_streak` (scores 1–2), `struggle_streak` (scores 4–5 or DNF).

**Yahtzee-style** (all require consecutive calendar days, no DNFs except Straight which is implicitly DNF-safe):
- `three_kind` — 3 identical scores on 3 consecutive days
- `four_kind` — 4 identical scores on 4 consecutive days (four-of-a-kind windows excluded from three-of-a-kind count)
- `full_house` — all 5 score values (1–5) across 5 consecutive days
- `straight` — scores 1, 2, 3, 4, 5 in any order across 5 consecutive days
- `yahtzee` — 5 identical scores on 5 consecutive days
- `full_card` — players who have achieved at least one of every Yahtzee category, ranked by total combined hits

All Yahtzee categories use non-overlapping windows (10 consecutive aces = 2 Yahtzees).

**Comedy** — `dnf_royalty` (most DNFs, celebrated), `eternal_3` (most scores of exactly 3), `clutch_rate` (% of plays that were guess-5), `variance` (most chaotic scoring), `most_improved` (biggest avg drop from first 7 to last 7 games).

Each fun standings post ends with a light, Portland-flavored description of the methodology.

### Community records
After each daily, weekly, and monthly leaderboard, the bot checks for new records across daily/weekly/monthly player counts, per-score daily highs (most aces, 2s, 3s, 4s, 5s, or DNFs in a day), and most new players in a day. Records are posted as a nested reply under the leaderboard when broken.

### Reliable threaded posting
Multi-page standings use correct Bluesky thread structure (`root` always points to page 1, `parent` to the immediately preceding post). Each post is confirmed as indexed in the AppView before the next reply is posted. Failed posts are retried up to `API_RETRIES` times.

### Feed polling
Polls the feed every N minutes for near-realtime reactions. Leaderboards post on a separate scheduled cadence.

### Head-to-head challenges

Players can challenge each other to private 1-week tournaments via DM. The bot manages the full lifecycle — registration, daily standings, and a final report.

**How it works:**
1. A player DMs `CHALLENGE` to start a new challenge. The bot replies with a 6-character invite code and a pre-formatted invite message ready to copy and send.
2. The creator shares the code. Invited players DM the code to the bot to enroll.
3. The bot notifies the creator each time someone accepts.
4. The challenge activates the next day and a start notice goes to all participants.
5. Daily standings DMs are sent at `CHALLENGE_REPORT_TIME` throughout the week.
6. On the morning after the final day, the bot sends a final report with champion and full results to everyone.

**Scoring:** best `CHALLENGE_BEST_OF` scores (default: 5) of 7 days, lowest total wins. DNF counts as 7. Late joiners are welcome — only scores from their join date onward count.

**Invite flow example:**

Creator DMs `CHALLENGE`, receives a confirmation followed immediately by a ready-to-forward invite:
```
I'm challenging you to a 1-week Routle - TriMet tournament!

It begins tomorrow, Thursday, May 8 and runs until Thursday, May 15, 2026.

To accept, DM AB3X7K to @pdxroutl.bsky.social
```

When an invitee accepts, the creator is notified:
```
@busonly just accepted your challenge AB3X7K! 3 players are now registered. Contest starts 2026-05-08. 🚊
```

Final report sent to all participants on conclusion:
```
🏁 FINAL RESULTS — Challenge AB3X7K
📅 2026-05-08 → 2026-05-15  |  4 players
Scoring: best 5 of 7 days  (DNF = 7)
─────────────────────
🥇 @busonly        [1+1+2+1+2]=7   avg 1.40  (7 days played)
🥈 @willowashmaple [1+2+2+3+3]=11  avg 2.20  (6 days played)
🥉 @khrisoden      [2+2+3+3+4]=14  avg 2.80  (5 days played)
4. @rockom         [1+2+3+4+5]=15  avg 3.00  (7 days played)
─────────────────────
🎉 Congratulations @busonly — champion of challenge AB3X7K!
Thanks for playing, Routlers. 🚋
```

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
./run_bot.sh fun --dry-run
```

### 5. First run — import history and backfill reactions

```bash
./run_bot.sh collect              # import existing results silently
./run_bot.sh rebuild-records      # build records.json from scores.json
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
fun              Pick and post a random fun report (--dry-run to preview)
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
./run_bot.sh standings full_card              # Full Scorecard Club
./run_bot.sh standings struggle_streak        # Struggle Bus Streak
./run_bot.sh standings dnf_royalty            # DNF leaderboard only

# Random fun report
./run_bot.sh fun                              # pick and post
./run_bot.sh fun --dry-run                    # pick and preview

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
| `RECORDS_FILE` | `records.json` | Community records (player count highs, per-score highs) |
| `FUN_HISTORY_FILE` | `fun_history.json` | Last posted date per fun category (14-day repeat guard) |
| `CHALLENGES_FILE` | `challenges.json` | All challenge state |

### Challenges

| Setting | Default | Description |
|---|---|---|
| `CHALLENGE_REPORT_TIME` | `None` | Time (HH:MM, 24h local) to run the daily challenge tick — activates new challenges, sends standings DMs, finalizes completed ones. `None` disables automatic challenge management |
| `CHALLENGE_BEST_OF` | `5` | Number of best daily scores counted toward the final ranking (of 7 days) |
| `CHALLENGE_CODE_LENGTH` | `6` | Characters in a generated invite code |
| `CHALLENGE_MAX_PARTICIPANTS` | `20` | Max players per challenge (`None` = unlimited) |

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
| `hist` or `history` | Receive your score history for the current year, grouped by month. |
| `wins` | Receive your daily win rate vs the community average — all-time, this month, last 7 days. |
| `yahtzee` | Receive a personal Yahtzee scorecard (see below). |
| `challenge` | Start a new head-to-head challenge. Returns an invite code and a ready-to-forward invite message. |
| `mystatus` | See your active challenges and your current rank in each. |
| `help` | Receive a list of all available DM commands. |

Unknown DMs receive a friendly driver-announcement reply with the full command list embedded.

#### Stats card

Sending `stats` triggers a DM with a full personal breakdown — games, streaks, aces, DNFs, average score (excl. DNFs), all-time rank, and a score distribution histogram.

```
📊 Routle stats — @𝚋𝚞𝚜𝚘𝚗𝚕𝚢

🎮 𝟺𝟽 games  🔥 streak 𝟻d  (best 𝟷𝟸d)
⭐ 𝟾 aces  💀 𝟹 DNFs
⌀ avg 𝟸.𝟹𝟾  ·  best 𝟷  (excl. DNFs)  ·  rank 𝟹 of 𝟸𝟺

𝟷▸ ████ 𝟾
𝟸▸ ████████ 𝟷𝟼
𝟹▸ ███████ 𝟷𝟻
𝟺▸ ██ 𝟻
𝟻▸ 𝟶
✗▸ 𝟹
```

#### History card

Sending `hist` or `history` triggers a DM with all scores for the current year, grouped by month:

```
📅 Routle history 2026 — @𝚛𝚘𝚌𝚔𝚘𝚖

── April ──
❌  𝟾  DNF
💀  𝟿  5
🟧 𝟷𝟶  3
🟩 𝟷𝟾  1

13 games played  ·  ⌀3.17 (excl. DNFs)  ·  7 DNFs
```

#### Yahtzee card

Sending `yahtzee` triggers a DM with the player's personal Yahtzee scorecard. Each category shows count and most recent date achieved:

```
🎲 Routle Yahtzee Card — @𝚠𝚒𝚕𝚕𝚘𝚠𝚊𝚜𝚑𝚖𝚊𝚙𝚕𝚎

⚀ Three of a Kind: 𝟺× (last 4/20)
⚁ Four of a Kind: 𝟸× (last 4/20)
⚂ Full House: —
⚃ The Straight: —
⚄ Yahtzee!: —

2/5 categories unlocked. 3 to go!
```

Players with all five categories unlocked receive a special full scorecard message.

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

All data files live in the `data/` subdirectory. Log files live in `logs/`. Both directories are created automatically on `./run_bot.sh install` or `./run_bot.sh start`.

| File | Contents |
|---|---|
| `data/scores.json` | `{"YYYY-MM-DD": {"handle": guess_number}}` |
| `data/aces.json` | `{"handle": total_ace_count}` |
| `data/streaks.json` | `{"handle": {"current": N, "best": N, "last_date": "YYYY-MM-DD"}}` |
| `data/optouts.json` | `["handle", ...]` |
| `data/known_players.json` | `{"handle": "did:plc:..."}` |
| `data/dnf_counts.json` | `{"handle": total_dnf_count}` |
| `data/records.json` | `{"daily_players": {"record": N, "date": "..."}, "weekly_players": {...}, "monthly_players": {...}, "new_players_day": {...}, "new_players": {"YYYY-MM-DD": N}, "daily_score_1": {...}, ...}` |
| `data/fun_history.json` | `{"category_key": "YYYY-MM-DD", ...}` — last posted date per fun category, enforces the 14-day no-repeat window |
| `data/challenges.json` | All challenge state — code, creator, status, start/end dates, participants, last report date. Created automatically on first `CHALLENGE` DM. |
| `data/reactions.json` | Set of post URIs the bot has already reacted to. Prevents duplicate reactions across restarts or concurrent runs. |
| `logs/bot.log` | Rotating log file (5 MB cap, up to `LOG_BACKUP_COUNT` backups) |

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
- **Configurable timeout** — `API_TIMEOUT` (default 20s) applies to every Bluesky API call
- **Read-confirm** — after posting, the bot polls `app.bsky.feed.getPosts` until the post is confirmed visible in the AppView before continuing
- **Correct threading** — multi-page standings use `root` (always page 1) and `parent` (immediately preceding post) as required by the AT Protocol
- **Atomic writes** — all JSON data files use write-then-rename to prevent corruption
- **Rotating log file** — `bot.log` is capped at 5 MB with up to `LOG_BACKUP_COUNT` backups, managed automatically via `logging.handlers.RotatingFileHandler`
- **Quiet hours** — reactions suppressed between `QUIET_HOURS_START` and `QUIET_HOURS_END`; scores are still recorded

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
├── requirements.txt     # Python 3.10+ required; requests>=2.31.0
├── .gitignore
├── LICENSE              # MIT
├── README.md
├── data/                # All JSON data files (created on first run)
│   ├── scores.json
│   ├── aces.json
│   ├── streaks.json
│   ├── optouts.json
│   ├── known_players.json
│   ├── dnf_counts.json
│   ├── records.json
│   ├── fun_history.json
│   └── challenges.json
└── logs/                # Rotating log files (created on first run)
    └── bot.log
```

---

## License

MIT — see [LICENSE](LICENSE).
