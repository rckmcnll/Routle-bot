# 🚌 Routle Leaderboard Bot — v2

A Bluesky bot that monitors a [Routle](https://routle.city) feed, tracks scores, and posts daily leaderboards and standings — with reactions, streaks, opt-out support, and a growing Routlers list.

Built for the [Portland TriMet Routle community](https://bsky.app/profile/pdxroutl.bsky.social) but easily adaptable to any Routle city feed.

---

## Features

**Scoring & Leaderboards**
- Monitors any Bluesky custom feed for Routle result posts
- Parses emoji grids (`🟩 🟥 ⬛`) to determine guess number — lower is better
- Posts a daily leaderboard with score distribution histogram
- Posts weekly, monthly, and yearly standings as threaded posts
- Standings show short handles in aligned columns with `🟩` score, days played, DNFs, and ⭐ for aces

**Reactions** *(replies to each player's result post)*
- 🟩 Guess 1 — ace congratulations with all-time ace count
- 🟥🟩 Guesses 2–5 — score-specific commentary
- 🟥🟥🟥🟥🟥 DNF — commiseration
- 🔥 Streak callouts for consecutive daily play
- All messages are Portland-flavored and fully configurable in `config.py`

**Player tracking**
- `aces.json` — all-time first-guess ace counts per player
- `streaks.json` — current and best consecutive day streaks
- `known_players.json` — tracks who has been added to the Routlers list
- Automatically adds new players to a Bluesky curated list

**Opt-out**
- Players DM `stop` to the bot to stop receiving reply reactions
- Players DM `start` to re-enable
- Opted-out players are still tracked and appear in leaderboards
- Opted-out players are not added to the Routlers list

**Polling**
- Polls the feed every N minutes (configurable) for near-realtime reactions
- Leaderboards post on a separate daily/weekly/monthly/yearly schedule

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

Edit `config.py` and fill in at minimum:

```python
BOT_HANDLE   = "your-bot.bsky.social"
BOT_PASSWORD = "xxxx-xxxx-xxxx-xxxx"   # App Password with DM access
FEED_CREATOR_HANDLE = "rockom.bsky.social"
FEED_SLUG           = "routle"
```

> **App Password:** Bluesky → Settings → Privacy and Security → App Passwords
> → Create new → **check "Allow access to your direct messages"**

### 3. Create the Routlers list *(optional)*

```bash
./run_bot.sh create-list
```

Copy the printed URI into `config.py` as `ROUTLERS_LIST_URI`.

### 4. Test without posting

```bash
./run_bot.sh dry-run
./run_bot.sh dry-run --period weekly
```

### 5. First run — collect history then backfill reactions

```bash
./run_bot.sh collect              # Import existing results silently
./run_bot.sh backfill --dry-run   # Preview what reactions would fire
./run_bot.sh backfill             # Fire reactions for all existing results
```

### 6. Start the scheduler

```bash
./run_bot.sh start   # Runs in background, polls + posts on schedule
./run_bot.sh logs    # Follow live output
```

---

## Shell script commands

```
run          Fetch results + post today's leaderboard (once)
dry-run      Fetch results + print leaderboard (don't post)
collect      Fetch & save results only, no leaderboard post
standings    Post an ad-hoc standings (weekly/monthly/yearly/custom)
backfill     Fire reactions for all results already in scores.json
start        Start the daily scheduler in the background
stop         Stop the background scheduler
status       Show whether the bot is running + score stats
logs         Tail the bot log (Ctrl+C to exit)
install      Set up virtual environment + install dependencies
create-list  Create the Routlers Bluesky list and print URI for config
help         Show help
```

### Standings examples

```bash
./run_bot.sh standings weekly --dry-run
./run_bot.sh standings monthly
./run_bot.sh standings yearly
./run_bot.sh standings custom                          # all history to now
./run_bot.sh standings custom --from 2026-04-01        # from date to now
./run_bot.sh standings custom --from 2026-04-01 --to 2026-04-09
```

---

## Configuration reference

| Setting | Default | Description |
|---|---|---|
| `BOT_HANDLE` | — | Bluesky handle of the bot account |
| `BOT_PASSWORD` | — | App Password (needs DM access) |
| `FEED_CREATOR_HANDLE` | — | Handle of the feed generator owner |
| `FEED_SLUG` | — | Slug from the feed URL (`/feed/<slug>`) |
| `GAME_NAME` | `Routle` | Game name, matched in post text |
| `MAX_SQUARES` | `5` | Number of guess squares |
| `LEADERBOARD_TIME` | `21:00` | Daily leaderboard post time (24h local) |
| `WEEKLY_LEADERBOARD_DAY` | `6` | Day for weekly standings (0=Mon, 6=Sun) |
| `POLL_INTERVAL_MINUTES` | `5` | How often to check feed for new results |
| `STANDINGS_SPOTS` | `10` | Players shown in standings (0 = all) |
| `NOTIFY_HANDLE` | `""` | Handle to DM when a leaderboard posts |
| `ROUTLERS_LIST_URI` | `""` | AT-URI of the Routlers curated list |
| `SCORES_FILE` | `scores.json` | Daily scores storage |
| `ACES_FILE` | `aces.json` | All-time ace counts |
| `STREAKS_FILE` | `streaks.json` | Consecutive day streaks |
| `OPTOUTS_FILE` | `optouts.json` | Opted-out handles |
| `KNOWN_PLAYERS_FILE` | `known_players.json` | Players added to Routlers list |

---

## Customizing messages

All reaction messages live at the bottom of `config.py` — no code changes needed.

| List | When used | Placeholders |
|---|---|---|
| `ACE_MESSAGES` | First-guess ace | `{display_name}`, `{handle}`, `{aces_line}` |
| `ACE_COUNT_LINES` | Appended to ace messages | `{aces}` |
| `DNF_MESSAGES` | All guesses wrong | `{display_name}`, `{handle}` |
| `SCORE_MESSAGES[2..5]` | Guesses 2–5 | `{display_name}`, `{handle}` |

Add more entries to any list to increase variety. The bot picks randomly from each list.

---

## Post examples

**Daily leaderboard**
```
🏆 Routle Daily — April 9, 2026

🟩⬛⬛⬛⬛ 🥇 @busonly
🟩⬛⬛⬛⬛ 🥇 @willowashmaple
🟥🟩⬛⬛⬛ 🥉 @rockom
🟥🟥🟥🟩⬛ 4. @drmitchpdx

4 players today!

  1▸ ██ 2
  2▸ █ 1
  4▸ █ 1
```

**Weekly standings**
```
🏆 Routle Weekly Standings — Apr 7–13, 2026

🥇 busonly          12🟩  7/7d ⭐
🥈 willowashmaple   18🟩  7/7d ⭐
🥉 rockom           21🟩  6/7d 1✗
4. drmitchpdx        29🟩  5/7d 2✗

4 players · 7/7 days played
```

**Ace reaction** *(reply to player's post)*
```
🚨 STOP EVERYTHING. Rockom Sockom got a FIRST GUESS ACE.
The MAX has been rerouted in their honor.

Career ace #7! See you at the top of the leaderboard
and also Pittock Mansion. 🔥 3 days in a row!

DM 'stop' to discontinue replies
```

---

## Adapting to another city

Change these settings in `config.py`:

```python
FEED_CREATOR_HANDLE = "feedcreator.bsky.social"
FEED_SLUG           = "routle-seattle"
GAME_NAME           = "Routle"
GAME_DOMAIN         = "routle.city"
```

The message lists reference Portland landmarks — swap them out for your city's flavor.

---

## Data files

| File | Contents | Safe to edit? |
|---|---|---|
| `scores.json` | `{"YYYY-MM-DD": {"handle": guess_number}}` | Yes |
| `aces.json` | `{"handle": count}` | Yes |
| `streaks.json` | `{"handle": {"current": N, "best": N, "last_date": "..."}}` | Yes |
| `optouts.json` | `["handle", ...]` | Yes |
| `known_players.json` | `{"handle": "did:plc:..."}` | Yes |

All files are created automatically on first run.

---

## Running with systemd

```ini
[Unit]
Description=Routle Leaderboard Bot
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

## License

MIT — see [LICENSE](LICENSE).
