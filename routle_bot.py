#!/usr/bin/env python3
"""
Routle Leaderboard Bot for Bluesky
Monitors a Bluesky custom feed for Routle results, tallies scores,
and posts daily / weekly / monthly / yearly leaderboards.

Feed URL format:  https://bsky.app/profile/<creator>/feed/<slug>
e.g.              https://bsky.app/profile/rockom.bsky.social/feed/routle
"""

import re
import json
import os
import time
import random
import datetime
import logging
import requests
from collections import defaultdict
from config import (
    BOT_HANDLE, BOT_PASSWORD,
    FEED_CREATOR_HANDLE, FEED_SLUG,
    GAME_NAME, GAME_DOMAIN,
    MAX_SQUARES, LEADERBOARD_TIME,
    WEEKLY_LEADERBOARD_DAY,
    SCORES_FILE, ACES_FILE, STREAKS_FILE, OPTOUTS_FILE, DNF_COUNTS_FILE,
    ROUTLERS_LIST_URI, KNOWN_PLAYERS_FILE,
    PIN_LEADERBOARD,
    STANDINGS_SPOTS,
    RANKING_METHOD, MIN_DAYS_THRESHOLD, BEST_OF_N_DAYS,
    WEEKLY_RANKING_METHOD, MONTHLY_RANKING_METHOD,
    YEARLY_RANKING_METHOD, CUSTOM_RANKING_METHOD,
    ACE_MILESTONES, GAMES_MILESTONES, DNF_MILESTONE_EVERY,
)
import config as _config
LOG_FILE         = getattr(_config, "LOG_FILE",         "bot.log")
LOG_LEVEL        = getattr(_config, "LOG_LEVEL",        "INFO")
LOG_BACKUP_COUNT = getattr(_config, "LOG_BACKUP_COUNT", 3)
RECORDS_FILE       = getattr(_config, "RECORDS_FILE",       "records.json")
QUIET_HOURS_START  = getattr(_config, "QUIET_HOURS_START",  "23:00")
QUIET_HOURS_END    = getattr(_config, "QUIET_HOURS_END",    "07:00")
API_TIMEOUT        = getattr(_config, "API_TIMEOUT",        20)
API_RETRIES        = getattr(_config, "API_RETRIES",        3)
FUN_STANDINGS_TIME = getattr(_config, "FUN_STANDINGS_TIME", "")    # "" = disabled
FUN_HISTORY_FILE   = getattr(_config, "FUN_HISTORY_FILE",   "fun_history.json")

logger = logging.getLogger(__name__)

# ─── Logging setup ─────────────────────────────────────────────────────────────

def setup_logging(
    log_file: str | None = None,
    level: int | None = None,
    backup_count: int | None = None,
    dry_run: bool = False,
) -> None:
    """
    Configure root logger with a timestamped console handler and a rotating
    file handler. Defaults come from config.py (LOG_FILE, LOG_LEVEL,
    LOG_BACKUP_COUNT). Idempotent — safe to call more than once.

    When dry_run=True the console handler is forced to DEBUG so all output
    is visible regardless of LOG_LEVEL. The file handler always uses LOG_LEVEL.
    """
    from logging.handlers import RotatingFileHandler

    _file    = log_file      if log_file      is not None else LOG_FILE
    _level   = level         if level         is not None else getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    _backups = backup_count  if backup_count  is not None else LOG_BACKUP_COUNT

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)   # root passes everything; handlers filter

    # Clear any handlers Python added automatically (e.g. lastResort) before
    # setup was called, so we never end up with duplicates.
    root.handlers.clear()

    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    sh.setLevel(logging.DEBUG if dry_run else _level)
    root.addHandler(sh)

    fh = RotatingFileHandler(_file, maxBytes=5_000_000, backupCount=_backups)
    fh.setFormatter(fmt)
    fh.setLevel(_level)
    root.addHandler(fh)


def _in_quiet_hours() -> bool:
    """
    Return True if the current local time falls within the configured quiet window.
    Handles overnight ranges (e.g. 23:00–07:00) correctly.
    Returns False if start == end (quiet hours disabled).
    """
    if QUIET_HOURS_START == QUIET_HOURS_END:
        return False
    now  = datetime.datetime.now().strftime("%H:%M")
    s, e = QUIET_HOURS_START, QUIET_HOURS_END
    if s < e:                     # same-day range e.g. 01:00–06:00
        return s <= now < e
    else:                         # overnight range e.g. 23:00–07:00
        return now >= s or now < e


# ─── Bluesky API helpers ───────────────────────────────────────────────────────

BASE_URL = "https://bsky.social/xrpc"

# Transient errors that are safe to retry
_RETRYABLE = (
    requests.exceptions.ReadTimeout,
    requests.exceptions.ConnectTimeout,
    requests.exceptions.ConnectionError,
)


def _api_request(method: str, url: str, **kwargs) -> requests.Response:
    """
    Wrapper around requests.get/post with retry + exponential backoff on
    transient network errors (timeouts, connection resets).

    Timeout defaults to API_TIMEOUT; retries to API_RETRIES.
    Non-retryable HTTP errors (4xx/5xx) are raised immediately.
    """
    kwargs.setdefault("timeout", API_TIMEOUT)
    last_exc: Exception | None = None
    for attempt in range(1, API_RETRIES + 1):
        try:
            resp = requests.request(method, url, **kwargs)
            resp.raise_for_status()
            return resp
        except _RETRYABLE as exc:
            last_exc = exc
            if attempt < API_RETRIES:
                delay = 2 ** (attempt - 1)   # 1s, 2s, 4s …
                logger.warning(
                    "Network error (attempt %d/%d): %s — retrying in %ds",
                    attempt, API_RETRIES, exc, delay,
                )
                time.sleep(delay)
            else:
                logger.error(
                    "Network error after %d attempts: %s", API_RETRIES, exc
                )
        except requests.exceptions.HTTPError:
            raise   # don't retry 4xx/5xx — propagate immediately
    raise last_exc


def login(handle: str, password: str) -> dict:
    resp = _api_request(
        "POST",
        f"{BASE_URL}/com.atproto.server.createSession",
        json={"identifier": handle, "password": password},
    )
    return resp.json()


def resolve_did(handle: str, token: str) -> str:
    resp = _api_request(
        "GET",
        f"{BASE_URL}/com.atproto.identity.resolveHandle",
        params={"handle": handle},
        headers={"Authorization": f"Bearer {token}"},
    )
    return resp.json()["did"]


def build_feed_uri(creator_handle: str, slug: str, token: str) -> str:
    did = resolve_did(creator_handle, token)
    return f"at://{did}/app.bsky.feed.generator/{slug}"


def get_custom_feed(feed_uri: str, token: str, limit: int = 100) -> list:
    posts = []
    cursor = None
    while True:
        params = {"feed": feed_uri, "limit": min(limit - len(posts), 100)}
        if cursor:
            params["cursor"] = cursor
        resp = _api_request(
            "GET",
            f"{BASE_URL}/app.bsky.feed.getFeed",
            params=params,
            headers={"Authorization": f"Bearer {token}"},
        )
        data = resp.json()
        posts.extend(data.get("feed", []))
        if len(posts) >= limit or not data.get("cursor"):
            break
        cursor = data["cursor"]
    return posts[:limit]


def post_text(text: str, session: dict,
              reply_to: dict | None = None,
              root_ref: dict | None = None) -> dict:
    """
    Create a post.
    reply_to : the immediate parent post {"uri": ..., "cid": ...}
    root_ref : the thread root post (defaults to reply_to for direct replies,
               must be set explicitly for deeper thread replies)
    """
    now = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    record = {
        "$type": "app.bsky.feed.post",
        "text": text,
        "createdAt": now,
        "langs": ["en-US"],
    }
    if reply_to:
        parent = {"uri": reply_to["uri"], "cid": reply_to["cid"]}
        root   = {"uri": root_ref["uri"], "cid": root_ref["cid"]} if root_ref else parent
        record["reply"] = {"root": root, "parent": parent}
    resp = _api_request(
        "POST",
        f"{BASE_URL}/com.atproto.repo.createRecord",
        json={
            "repo": session["did"],
            "collection": "app.bsky.feed.post",
            "record": record,
        },
        headers={"Authorization": f"Bearer {session['accessJwt']}"},
    )
    return resp.json()


# ─── Bluesky List API ─────────────────────────────────────────────────────────

def create_list(session: dict, name: str, description: str = "") -> str:
    """
    Create a new curated list owned by the bot. Returns the list AT-URI.
    Call once manually via: ./run_bot.sh create-list
    """
    now = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    resp = requests.post(
        f"{BASE_URL}/com.atproto.repo.createRecord",
        json={
            "repo": session["did"],
            "collection": "app.bsky.graph.list",
            "record": {
                "$type": "app.bsky.graph.list",
                "purpose": "app.bsky.graph.defs#curatelist",
                "name": name,
                "description": description,
                "createdAt": now,
            },
        },
        headers={"Authorization": f"Bearer {session['accessJwt']}"},
    )
    resp.raise_for_status()
    return resp.json()["uri"]


def follow_player(session: dict, did: str) -> bool:
    """
    Follow a player DID from the bot account.
    Returns True on success, False if already following or on error.
    """
    now = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    try:
        _api_request(
            "POST",
            f"{BASE_URL}/com.atproto.repo.createRecord",
            json={
                "repo": session["did"],
                "collection": "app.bsky.graph.follow",
                "record": {
                    "$type": "app.bsky.graph.follow",
                    "subject": did,
                    "createdAt": now,
                },
            },
            headers={"Authorization": f"Bearer {session['accessJwt']}"},
        )
        return True
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 400:
            return False   # likely already following
        logger.warning("Could not follow %s: %s", did, e)
        return False
    except Exception as e:
        logger.warning("Could not follow %s: %s", did, e)
        return False
    """Add a DID to a list. Returns True on success, False if already a member."""
    now = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    try:
        requests.post(
            f"{BASE_URL}/com.atproto.repo.createRecord",
            json={
                "repo": session["did"],
                "collection": "app.bsky.graph.listitem",
                "record": {
                    "$type": "app.bsky.graph.listitem",
                    "subject": member_did,
                    "list": list_uri,
                    "createdAt": now,
                },
            },
            headers={"Authorization": f"Bearer {session['accessJwt']}"},
        ).raise_for_status()
        return True
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 400:
            return False   # likely already a member
        raise


# ─── Known players tracking ────────────────────────────────────────────────────

def load_known_players() -> dict:
    """Load known players. Structure: {"handle": "did"}"""
    if os.path.exists(KNOWN_PLAYERS_FILE):
        with open(KNOWN_PLAYERS_FILE) as f:
            return json.load(f)
    return {}


def save_known_players(known: dict):
    _tmp = KNOWN_PLAYERS_FILE + ".tmp"
    with open(_tmp, "w") as f:
        json.dump(known, f, indent=2, sort_keys=True)
    os.replace(_tmp, KNOWN_PLAYERS_FILE)


def maybe_add_to_routlers(session: dict, handle: str, did: str,
                           known: dict, optouts: set, dry_run: bool = False):
    """
    Follow the player and add them to the Routlers list if they're new.
    Updates `known` in-place. Skips list add (but still follows) for opted-out players.
    """
    if handle in known:
        return

    # Follow the player from the bot account
    logger.info("➕ Following @%s", handle)
    if not dry_run:
        follow_player(session, did)

    if not ROUTLERS_LIST_URI:
        known[handle] = did
        return

    if handle in optouts:
        logger.debug("Skipping list add — @%s opted out", handle)
        known[handle] = did   # still record as known so we don't check again
        return

    logger.info("➕ Adding @%s to Routlers list", handle)
    if not dry_run:
        try:
            add_to_list(session, ROUTLERS_LIST_URI, did)
        except Exception as e:
            logger.warning("Could not add @%s to list: %s", handle, e)
            return
    known[handle] = did


# ─── Score parsing ─────────────────────────────────────────────────────────────

# Real post format (newline-separated):
#   Routle - TriMet
#   04/08/2026
#   🟩 ⬛ ⬛ ⬛ ⬛
#   www.routle.city/trimet
# Tolerant match: allows extra spaces, \r\n line endings, and minor formatting
# variations between the game name, date, and emoji grid lines.
RESULT_RE = re.compile(
    rf"{re.escape(GAME_NAME)}[^\n]*\r?\n"
    r"[ \t]*(\d{2}/\d{2}/\d{4})[ \t]*\r?\n"
    r"([ \t\U0001F7E9\u2B1B\U0001F7E8\U0001F7E5\U0001F7EA]+)",
    re.IGNORECASE,
)

GREEN = "🟩"  # correct guess
RED   = "🟥"  # wrong guess (attempted)
BLACK = "⬛"  # not attempted (remaining slots after a DNF)

# Sentinel score for a DNF (used all guesses without getting it, or abandoned).
# Sorts last in all leaderboards.
DNF = MAX_SQUARES + 1


def parse_result(text: str) -> tuple[str | None, int | None]:
    """
    Returns (date_str "YYYY-MM-DD", guess_number) or (None, None).

    guess_number = position of the 🟩 square (1 = got it first try = best).
    Wrong guesses are 🟥; unused slots are ⬛.
    If there is no 🟩, the player did not finish → score is DNF (MAX_SQUARES+1).
    Lower score is always better.

    Example grids:
      🟩 ⬛ ⬛ ⬛ ⬛  → guess 1 (got it first try)
      🟥 🟥 🟩 ⬛ ⬛  → guess 3
      🟥 🟥 🟥 🟥 🟥  → DNF (used all guesses, never got it)
      🟥 🟥 ⬛ ⬛ ⬛  → DNF (gave up early)
    """
    m = RESULT_RE.search(text)
    if not m:
        return None, None
    raw_date, grid_section = m.group(1), m.group(2)

    squares = grid_section.split()
    if not squares:
        return None, None

    if GREEN in squares:
        guess_num = squares.index(GREEN) + 1           # 1-indexed position
    elif RED in squares or BLACK in squares:
        guess_num = DNF                                 # played but didn't get it
    else:
        return None, None                       # not a result post

    try:
        date_obj = datetime.datetime.strptime(raw_date, "%m/%d/%Y")
        return date_obj.strftime("%Y-%m-%d"), guess_num
    except ValueError:
        return None, None


# ─── Score persistence ─────────────────────────────────────────────────────────

def load_scores() -> dict:
    """Load scores. Structure: {"YYYY-MM-DD": {"handle": score}}"""
    if os.path.exists(SCORES_FILE):
        with open(SCORES_FILE) as f:
            return json.load(f)
    return {}


def save_scores(scores: dict):
    _tmp = SCORES_FILE + ".tmp"
    with open(_tmp, "w") as f:
        json.dump(scores, f, indent=2, sort_keys=True)
    os.replace(_tmp, SCORES_FILE)


# ─── Score aggregation ─────────────────────────────────────────────────────────

def scores_for_period(scores: dict, date_keys: list[str]) -> dict:
    """
    Aggregate raw daily scores across a period.
    Returns {handle: {"total": int, "days": int, "avg": float, "best": int,
                       "dnf": int, "daily_scores": list[int]}}.
    daily_scores preserves each result in date order for Best-N computation.
    """
    agg: dict[str, dict] = defaultdict(
        lambda: {"total": 0, "days": 0, "best": DNF, "dnf": 0, "daily_scores": []}
    )
    for dk in date_keys:
        for handle, score in scores.get(dk, {}).items():
            agg[handle]["total"] += score
            agg[handle]["days"] += 1
            agg[handle]["best"] = min(agg[handle]["best"], score)
            agg[handle]["daily_scores"].append(score)
            if score == DNF:
                agg[handle]["dnf"] += 1
    for handle in agg:
        d = agg[handle]["days"]
        agg[handle]["avg"] = round(agg[handle]["total"] / d, 2) if d else 0.0
    return dict(agg)


def rank_period_agg(agg: dict, date_keys: list[str], method: str | None = None) -> dict:
    """
    Apply ranking to enrich each player's agg entry with sort key and display stats.
    method overrides RANKING_METHOD when provided (used for per-period config).

    Methods:
      "total"         — raw total guesses (current behaviour, lower = better)
      "avg"           — average guess with MIN_DAYS_THRESHOLD floor
      "adjusted"      — average over ALL days, treating unplayed days as DNF
      "best_n"        — average of best BEST_OF_N_DAYS scores
      "weighted"      — inverted points × participation rate
      "participation" — most days played (ties broken by avg score)
    """
    total_days = len(date_keys)
    effective_method = method or RANKING_METHOD

    for handle, s in agg.items():
        days     = s["days"]
        daily    = sorted(s["daily_scores"])          # ascending = best first

        if effective_method == "avg":
            # Exclude players below minimum threshold
            if MIN_DAYS_THRESHOLD and days < MIN_DAYS_THRESHOLD:
                s["rank_key"]   = (999, 0)            # sorts to bottom
                s["rank_stat"]  = f"({days}d — min {MIN_DAYS_THRESHOLD})"
                s["eligible"]   = False
            else:
                s["rank_key"]   = (round(s["avg"], 4), -days)
                s["rank_stat"]  = f"⌀{s['avg']:.2f}"
                s["eligible"]   = True

        elif effective_method == "adjusted":
            # Treat unplayed days as DNF (MAX_SQUARES+1)
            missing = total_days - days
            adj_total = s["total"] + missing * DNF
            adj_avg   = round(adj_total / total_days, 4) if total_days else 0
            s["rank_key"]  = (adj_avg, -days)
            s["rank_stat"] = f"⌀{adj_avg:.2f}"
            s["eligible"]  = True

        elif effective_method == "best_n":
            n = BEST_OF_N_DAYS or total_days
            best_scores = daily[:n]                   # n lowest (best) scores
            avg = round(sum(best_scores) / len(best_scores), 4) if best_scores else 0
            s["rank_key"]  = (avg, -days)
            s["rank_stat"] = f"⌀{avg:.2f} (b{len(best_scores)})"
            s["eligible"]  = True

        elif effective_method == "weighted":
            # Points = sum(MAX_SQUARES+1 - score) for each day played; DNF = 0 pts
            pts = sum(max(0, DNF - sc) for sc in s["daily_scores"])
            rate = days / total_days if total_days else 0
            weighted = round(pts * rate, 4)
            s["rank_key"]  = (-weighted, -days)       # higher weighted = better
            s["rank_stat"] = f"{pts}pts×{rate:.0%}"
            s["eligible"]  = True

        elif effective_method == "participation":
            # Most days played; ties broken by avg score (lower = better)
            s["rank_key"]  = (-days, round(s["avg"], 4))
            s["rank_stat"] = f"{days}gp"
            s["eligible"]  = True

        else:  # "total" (default) or unrecognised
            s["rank_key"]  = (s["total"], s["dnf"], s["avg"])
            s["rank_stat"] = None                     # use default display
            s["eligible"]  = True

    return agg


def date_keys_for_week(ref: datetime.date) -> list[str]:
    monday = ref - datetime.timedelta(days=ref.weekday())
    return [(monday + datetime.timedelta(days=i)).isoformat() for i in range(7)]


def date_keys_for_month(ref: datetime.date) -> list[str]:
    import calendar
    _, last_day = calendar.monthrange(ref.year, ref.month)
    return [datetime.date(ref.year, ref.month, d).isoformat() for d in range(1, last_day + 1)]


def date_keys_for_year(ref: datetime.date) -> list[str]:
    start = datetime.date(ref.year, 1, 1)
    end = datetime.date(ref.year, 12, 31)
    return [(start + datetime.timedelta(days=i)).isoformat() for i in range((end - start).days + 1)]


# ─── Leaderboard formatting ────────────────────────────────────────────────────

MEDALS = ["🥇", "🥈", "🥉"]


def _grid_display(guess_num: int) -> str:
    """
    Reconstruct the emoji grid from a guess number.
      - Guesses before the correct one → 🟥 (wrong)
      - The correct guess → 🟩
      - Remaining slots → ⬛ (not attempted)
      - DNF (guess_num > MAX_SQUARES) → all 🟥
    """
    if guess_num > MAX_SQUARES:
        return RED * MAX_SQUARES   # used all guesses, never got it
    squares = [RED] * (guess_num - 1) + [GREEN] + [BLACK] * (MAX_SQUARES - guess_num)
    return "".join(squares)


def _medal(rank: int) -> str:
    return MEDALS[rank - 1] if rank <= 3 else f"{rank}."


def _short_handle(handle: str) -> str:
    """Return just the first segment: 'busonly.bsky.social' → 'busonly'."""
    return handle.split(".")[0]


# Unicode Mathematical Monospace block offsets
_MONO_UPPER = 0x1D670 - ord('A')   # 𝙰–𝚉
_MONO_LOWER = 0x1D68A - ord('a')   # 𝚊–𝚣
_MONO_DIGIT = 0x1D7F6 - ord('0')   # 𝟶–𝟿


def _mono(text: str) -> str:
    """
    Convert ASCII letters and digits to their Unicode Mathematical Monospace
    equivalents so tabular columns align in Bluesky posts regardless of client
    font. Spaces are mapped to figure space (U+2007) which is defined as the
    same width as a digit — matching the monospace glyph width precisely.
    Non-ASCII characters (emoji, symbols) are passed through unchanged.
    """
    out = []
    for ch in text:
        if 'A' <= ch <= 'Z':
            out.append(chr(ord(ch) + _MONO_UPPER))
        elif 'a' <= ch <= 'z':
            out.append(chr(ord(ch) + _MONO_LOWER))
        elif '0' <= ch <= '9':
            out.append(chr(ord(ch) + _MONO_DIGIT))
        elif ch == ' ':
            out.append('\u2007')   # figure space — same width as a digit
        else:
            out.append(ch)
    return "".join(out)


BSKY_LIMIT = 300  # Bluesky grapheme limit per post


def _graphemes(s: str) -> int:
    """Count graphemes (one per code point — accurate for our emoji/ASCII content)."""
    return len(s)


def format_daily_leaderboard(date_str: str, day_scores: dict,
                             scores: dict | None = None) -> str:
    if not day_scores:
        return f"No {GAME_NAME} results for {date_str} yet!"

    # Compute all-time avg per player for tiebreaking (lower = better)
    # Only uses scores from before or on the current date to avoid lookahead
    def _alltime_avg(handle: str) -> float:
        if not scores:
            return 0.0
        all_sc = [
            scores[d][handle]
            for d in scores
            if handle in scores[d] and d <= date_str
        ]
        non_dnf = [s for s in all_sc if s != DNF]
        return round(sum(non_dnf) / len(non_dnf), 4) if non_dnf else 9.0

    ranked = sorted(
        day_scores.items(),
        key=lambda x: (x[1], _alltime_avg(x[0]), x[0]),
    )
    date_display = datetime.datetime.strptime(date_str, "%Y-%m-%d").strftime("%B %-d, %Y")
    header = f"🏆 {GAME_NAME} Daily — {date_display}\n"

    # Score distribution histogram
    score_counts: dict[int, int] = {}
    for _, score in ranked:
        score_counts[score] = score_counts.get(score, 0) + 1
    dist_parts = []
    for g in range(1, MAX_SQUARES + 1):
        count = score_counts.get(g, 0)
        if count:
            dist_parts.append(f"  {g}▸ {'█' * count} {count}")
    dnf_count = score_counts.get(DNF, 0)
    if dnf_count:
        dist_parts.append(f"  ✗▸ {'█' * dnf_count} {dnf_count}")

    n = len(ranked)
    footer = f"\n{n} player{'s' if n != 1 else ''} today!"
    if dist_parts:
        footer += "\n\n" + "\n".join(dist_parts)

    # Build player rows; trim from the bottom if needed to fit BSKY_LIMIT
    player_lines = []
    prev_score = None
    rank = 0
    for i, (handle, score) in enumerate(ranked):
        if score != prev_score:
            rank = i + 1
            prev_score = score
        player_lines.append(f"{_grid_display(score)} {_medal(rank)} @{_mono(_short_handle(handle))}")

    omitted = 0
    while player_lines:
        omit_note = f"\n  …and {omitted} more" if omitted else ""
        candidate = header + "\n" + "\n".join(player_lines) + omit_note + footer
        if _graphemes(candidate) <= BSKY_LIMIT:
            return candidate
        player_lines.pop()
        omitted += 1

    return header + footer  # extreme fallback


def format_period_leaderboard(title: str, agg: dict, scores: dict, date_keys: list[str], method: str | None = None) -> list[str]:
    """
    Format a period standings post, split into pages of STANDINGS_PAGE_SIZE players.
    Returns a list of strings — first is the main post, rest are continuation replies.
    """
    if not agg:
        return [f"No {GAME_NAME} results for {title} yet!"]

    # Enrich agg with ranking keys for the configured method
    agg = rank_period_agg(agg, date_keys, method=method)

    # Sort: eligible players first by rank_key, ineligible at bottom
    all_ranked = sorted(
        agg.items(),
        key=lambda x: (
            0 if x[1].get("eligible", True) else 1,
            x[1]["rank_key"],
            x[0],
        ),
    )

    eligible_all   = [r for r in all_ranked if r[1].get("eligible", True)]
    ineligible_all = [r for r in all_ranked if not r[1].get("eligible", True)]
    total_players  = len(all_ranked)
    if STANDINGS_SPOTS:
        ranked = eligible_all[:STANDINGS_SPOTS] + ineligible_all
    else:
        ranked = all_ranked

    active_days = sum(1 for dk in date_keys if scores.get(dk))
    total_days  = len(date_keys)
    n_shown     = len([r for r in ranked if r[1].get("eligible", True)])
    shown_note  = f" (top {n_shown} of {total_players})" if total_players > n_shown else ""
    _eff = agg[next(iter(agg))].get("_method", RANKING_METHOD) if agg else RANKING_METHOD
    method_note = {
        "avg":           f" · min {MIN_DAYS_THRESHOLD}d to qualify",
        "adjusted":      " · unplayed=DNF",
        "best_n":        f" · best {BEST_OF_N_DAYS or active_days}/{active_days}d",
        "weighted":      " · pts×participation",
        "participation": " · most games played",
    }.get(RANKING_METHOD, "")
    footer = (
        f"\n{total_players} player{'s' if total_players != 1 else ''}"
        f" · {active_days}/{total_days} days played"
        f"{shown_note}{method_note}"
    )

    short_names = [_short_handle(h) for h, _ in ranked]
    name_w = max((len(sn) for sn in short_names), default=8)

    # Pre-compute all row strings so we can measure column widths before rendering
    row_data = []
    prev_key   = None
    rank       = 0
    elig_count = 0
    for (handle, s), short in zip(ranked, short_names):
        eligible_row = s.get("eligible", True)
        if eligible_row:
            if s["rank_key"] != prev_key:
                rank     = elig_count + 1
                prev_key = s["rank_key"]
            elig_count += 1
            rank_label = f"{rank}."
        else:
            rank_label = "—"                   # below threshold, shown but unranked

        dnf_str  = f" {s['dnf']}✗" if s["dnf"] else ""
        ace_str  = " ⭐" if s["best"] == 1 else ""
        stat     = s.get("rank_stat")
        stat_col = stat if stat else f"{s['total']}🟩"
        days_str = f"{s['days']}/{active_days}d"
        row_data.append((rank_label, short, stat_col, days_str, dnf_str, ace_str))

    rank_w = max((len(r[0]) for r in row_data), default=2)
    stat_w = max((len(r[2]) for r in row_data), default=0)
    days_w = max((len(r[3]) for r in row_data), default=0)

    player_rows = []
    for rank_label, short, stat_col, days_str, dnf_str, ace_str in row_data:
        player_rows.append(
            f"{_mono(f'{rank_label:>{rank_w}}')} {_mono(f'{short:<{name_w}}')}  "
            f"{_mono(f'{stat_col:<{stat_w}}')}  "
            f"{_mono(f'{days_str:>{days_w}}')}"
            f"{_mono(dnf_str)}{ace_str}"
        )

    # Split into pages fitting within BSKY_LIMIT
    pages = []
    remaining = list(player_rows)
    page_num = 0
    while remaining:
        is_last_page = True  # assume until proven otherwise
        # Try to fit as many rows as possible into this page
        chunk = []
        while remaining:
            candidate_chunk = chunk + [remaining[0]]
            is_last = len(remaining) == 1
            total_pages_est = page_num + (2 if not is_last else 1)
            if page_num == 0:
                header = f"🏆 {GAME_NAME} {title}\n"
            else:
                header = f"({page_num + 1}/?) {GAME_NAME} {title} cont.\n"
            page_footer = footer if is_last and len(remaining) == 1 else ""
            candidate = header + "\n" + "\n".join(candidate_chunk) + page_footer
            if _graphemes(candidate) <= BSKY_LIMIT:
                chunk.append(remaining.pop(0))
            else:
                break
            if not remaining:
                break

        if not chunk:
            # Single row too long — force-add it anyway
            chunk = [remaining.pop(0)]

        is_last_page = not remaining
        if page_num == 0:
            header = f"🏆 {GAME_NAME} {title}\n"
        else:
            header = f"({page_num + 1}) {GAME_NAME} {title} cont.\n"
        page_footer = footer if is_last_page else ""
        pages.append(header + "\n" + "\n".join(chunk) + page_footer)
        page_num += 1

    return pages


def format_weekly_leaderboard(ref: datetime.date, scores: dict) -> list[str]:
    keys = date_keys_for_week(ref)
    monday = ref - datetime.timedelta(days=ref.weekday())
    sunday = monday + datetime.timedelta(days=6)
    label = f"Weekly Standings — {monday.strftime('%b %-d')}–{sunday.strftime('%-d, %Y')}"
    return format_period_leaderboard(label, scores_for_period(scores, keys), scores, keys, method=WEEKLY_RANKING_METHOD)


def format_monthly_leaderboard(ref: datetime.date, scores: dict) -> list[str]:
    keys = date_keys_for_month(ref)
    label = f"Monthly Standings — {ref.strftime('%B %Y')}"
    return format_period_leaderboard(label, scores_for_period(scores, keys), scores, keys, method=MONTHLY_RANKING_METHOD)


def format_yearly_leaderboard(ref: datetime.date, scores: dict) -> list[str]:
    keys = date_keys_for_year(ref)
    label = f"Yearly Standings — {ref.year}"
    return format_period_leaderboard(label, scores_for_period(scores, keys), scores, keys, method=YEARLY_RANKING_METHOD)


# ─── Fun standings ─────────────────────────────────────────────────────────────

def _player_dated_scores(scores: dict) -> dict[str, list[tuple[str, int]]]:
    """Return {handle: [(date_str, score), ...]} sorted by date for all players."""
    result: dict[str, list] = {}
    for date_str in sorted(scores.keys()):
        for handle, score in scores[date_str].items():
            result.setdefault(handle, []).append((date_str, score))
    return result


def _fun_page(title: str, rows: list[tuple[str, str]], emoji: str = "🎲",
              description: str | None = None) -> list[str]:
    """
    Format a fun standings into Bluesky-sized pages.
    rows: [(rank_label, handle_short, stat_str), ...]
    If description is provided it is appended as a final reply page.
    """
    header = f"{emoji} {GAME_NAME} {title}\n"
    player_rows = []
    for rank_label, handle_short, stat in rows:
        rank_w  = max(len(r[0]) for r in rows)
        name_w  = max(len(r[1]) for r in rows)
        player_rows.append(
            f"{_mono(f'{rank_label:>{rank_w}}')} {_mono(f'{handle_short:<{name_w}}')}  {_mono(stat)}"
        )

    pages = []
    remaining = list(player_rows)
    page_num = 0
    while remaining:
        chunk = []
        while remaining:
            candidate = (
                (header if page_num == 0 else f"({page_num + 1}) {GAME_NAME} {title} cont.\n")
                + "\n" + "\n".join(chunk + [remaining[0]])
            )
            if _graphemes(candidate) <= BSKY_LIMIT:
                chunk.append(remaining.pop(0))
            else:
                break
        if not chunk:
            chunk = [remaining.pop(0)]
        hdr = header if page_num == 0 else f"({page_num + 1}) {GAME_NAME} {title} cont.\n"
        pages.append(hdr + "\n" + "\n".join(chunk))
        page_num += 1

    if not pages:
        pages = [header + "\nNo data yet!"]

    if description:
        pages.append(description)

    return pages


def _rank_rows(items: list[tuple[str, int | float]], fmt: str = "{}",
               higher_is_better: bool = True,
               player_dates: dict[str, str] | None = None) -> list[tuple[str, str, str]]:
    """
    Given [(handle, value), ...] produce ranked (rank_label, short_handle, stat_str) rows.
    Ties share the same rank label.
    If player_dates is provided, the most recent date is appended to each row's stat.
    """
    if not items:
        return []
    items = sorted(items, key=lambda x: -x[1] if higher_is_better else x[1])
    rows = []
    prev_val = None
    rank = 0
    for i, (handle, val) in enumerate(items):
        if val != prev_val:
            rank = i + 1
            prev_val = val
        stat = fmt.format(val)
        if player_dates and handle in player_dates:
            last = player_dates[handle]
            last_fmt = datetime.datetime.strptime(last, "%Y-%m-%d").strftime("%-m/%-d")
            stat = f"{stat} {last_fmt}"
        rows.append((f"{rank}.", _short_handle(handle), stat))
    return rows


def compute_fun_stats(scores: dict) -> tuple[dict[str, list], dict[str, dict[str, str]]]:
    """
    Compute all fun category stats from scores.json.
    Returns a tuple of:
      - stats:      {category_key: [(handle, value), ...]} unsorted
      - last_dates: {yahtzee_category_key: {handle: "YYYY-MM-DD"}} most recent date achieved
    """
    dated = _player_dated_scores(scores)
    stats: dict[str, dict[str, int | float]] = {
        # Day-of-week bests (avg score on that day, lower = better → stored as negative)
        "dow_monday":    {}, "dow_tuesday":  {}, "dow_wednesday": {},
        "dow_thursday":  {}, "dow_friday":   {}, "dow_saturday":  {},
        "dow_sunday":    {},
        # Score count categories
        "score_2": {}, "score_3": {}, "score_4": {}, "score_5": {},
        # Streak & pattern
        "ace_streak": {}, "no_dnf_streak": {}, "sub3_streak": {}, "struggle_streak": {},
        # Yahtzee
        "yahtzee": {}, "four_kind": {}, "three_kind": {},
        "full_house": {}, "straight": {},
        # Comedy
        "dnf_royalty": {}, "eternal_3": {},
        "clutch_rate": {}, "variance": {},
        "most_improved": {},
        # Derived
        "full_card": {},
    }

    # Tracks the most recent date each yahtzee category was achieved per player
    last_dates: dict[str, dict[str, str]] = {
        "yahtzee": {}, "four_kind": {}, "three_kind": {},
        "full_house": {}, "straight": {},
    }

    # ── Day-of-week accumulation ───────────────────────────────────────────────
    dow_names = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]
    dow_acc: dict[str, dict[str, list[int]]] = {d: {} for d in dow_names}
    for handle, dated_scores in dated.items():
        for date_str, score in dated_scores:
            dow = datetime.date.fromisoformat(date_str).strftime("%A").lower()
            dow_acc[dow].setdefault(handle, []).append(score)

    for dow in dow_names:
        key = f"dow_{dow}"
        for handle, sc_list in dow_acc[dow].items():
            non_dnf = [s for s in sc_list if s != DNF]
            if non_dnf:
                stats[key][handle] = round(sum(non_dnf) / len(non_dnf), 2)

    # ── Score count categories (2–5) ───────────────────────────────────────────
    for handle, dated_scores in dated.items():
        sc_list = [s for _, s in dated_scores]
        for val in (2, 3, 4, 5):
            cnt = sc_list.count(val)
            if cnt:
                stats[f"score_{val}"][handle] = cnt

    # ── Streaks ────────────────────────────────────────────────────────────────
    def _max_streak(dated_scores: list[tuple[str, int]], pred) -> int:
        best = cur = 0
        for _, s in dated_scores:
            if pred(s):
                cur += 1
                best = max(best, cur)
            else:
                cur = 0
        return best

    for handle, dated_scores in dated.items():
        ace_s    = _max_streak(dated_scores, lambda s: s == 1)
        no_dnf   = _max_streak(dated_scores, lambda s: s != DNF)
        sub3     = _max_streak(dated_scores, lambda s: s < 3)
        struggle = _max_streak(dated_scores, lambda s: s >= 4)
        if ace_s    >= 3: stats["ace_streak"][handle]      = ace_s
        if no_dnf   >= 3: stats["no_dnf_streak"][handle]   = no_dnf
        if sub3     >= 3: stats["sub3_streak"][handle]      = sub3
        if struggle >= 3: stats["struggle_streak"][handle]  = struggle

    # ── Yahtzee-style ──────────────────────────────────────────────────────────
    for handle, dated_scores in dated.items():
        sc_list = [s for _, s in dated_scores]
        n = len(sc_list)

        def _is_consecutive(dated_scores: list, start: int, length: int) -> bool:
            """True if the `length` entries starting at `start` span consecutive calendar dates."""
            for j in range(start, start + length - 1):
                d1 = datetime.date.fromisoformat(dated_scores[j][0])
                d2 = datetime.date.fromisoformat(dated_scores[j + 1][0])
                if (d2 - d1).days != 1:
                    return False
            return True

        # Yahtzee — 5 identical scores on 5 consecutive calendar days (DNFs excluded)
        # Non-overlapping: once a Yahtzee is found, advance past the full window
        yahtzee = 0
        yahtzee_last = ""
        i = 0
        while i <= n - 5:
            if _is_consecutive(dated_scores, i, 5):
                window = sc_list[i:i+5]
                if DNF not in window and len(set(window)) == 1:
                    yahtzee += 1
                    yahtzee_last = dated_scores[i + 4][0]
                    i += 5   # skip past this window — no overlapping Yahtzees
                    continue
            i += 1
        if yahtzee:
            stats["yahtzee"][handle] = yahtzee
            last_dates["yahtzee"][handle] = yahtzee_last

        # Four of a kind — 4 identical scores on 4 consecutive calendar days (DNFs excluded)
        # Non-overlapping: skip past the window on a hit.
        four = 0
        four_last = ""
        four_consumed: set[int] = set()   # start indices consumed by four_kind
        i = 0
        while i <= n - 4:
            if _is_consecutive(dated_scores, i, 4):
                window = sc_list[i:i+4]
                if DNF not in window and len(set(window)) == 1:
                    four += 1
                    four_last = dated_scores[i + 3][0]
                    for j in range(i, i + 4):
                        four_consumed.add(j)
                    i += 4   # skip past this window
                    continue
            i += 1
        if four:
            stats["four_kind"][handle] = four
            last_dates["four_kind"][handle] = four_last

        # Three of a kind — 3 identical scores on 3 consecutive calendar days (DNFs excluded)
        # Non-overlapping, and windows already consumed by four_kind are excluded.
        three = 0
        three_last = ""
        i = 0
        while i <= n - 3:
            # Skip any index that's inside a four_kind window
            if i in four_consumed:
                i += 1
                continue
            if _is_consecutive(dated_scores, i, 3):
                window = sc_list[i:i+3]
                if DNF not in window and len(set(window)) == 1:
                    three += 1
                    three_last = dated_scores[i + 2][0]
                    i += 3   # skip past this window
                    continue
            i += 1
        if three:
            stats["three_kind"][handle] = three
            last_dates["three_kind"][handle] = three_last

        # Full house — all 5 score values (1–5) in any order across 5 consecutive calendar days (DNFs excluded)
        # Non-overlapping: skip past the window on a hit.
        full = 0
        full_last = ""
        i = 0
        while i <= n - 5:
            if _is_consecutive(dated_scores, i, 5):
                window = sc_list[i:i+5]
                if DNF not in window and all(v in window for v in range(1, MAX_SQUARES + 1)):
                    full += 1
                    full_last = dated_scores[i + 4][0]
                    i += 5   # skip past this window
                    continue
            i += 1
        if full:
            stats["full_house"][handle] = full
            last_dates["full_house"][handle] = full_last

        # Straight — all 5 values (1–5) in any order across 5 consecutive calendar days
        # Non-overlapping: skip past the window on a hit. DNF implicitly excluded (sorted != [1-5]).
        straight = 0
        straight_last = ""
        i = 0
        while i <= n - 5:
            if _is_consecutive(dated_scores, i, 5):
                window = sc_list[i:i+5]
                if sorted(window) == list(range(1, MAX_SQUARES + 1)):
                    straight += 1
                    straight_last = dated_scores[i + 4][0]
                    i += 5   # skip past this window
                    continue
            i += 1
        if straight:
            stats["straight"][handle] = straight
            last_dates["straight"][handle] = straight_last

    # ── Comedy ────────────────────────────────────────────────────────────────
    for handle, dated_scores in dated.items():
        sc_list = [s for _, s in dated_scores]
        non_dnf = [s for s in sc_list if s != DNF]

        dnf_cnt = sc_list.count(DNF)
        if dnf_cnt:
            stats["dnf_royalty"][handle] = dnf_cnt

        eternal = sc_list.count(3)
        if eternal:
            stats["eternal_3"][handle] = eternal

        # Clutch rate — % of plays that were exactly guess 5
        if len(sc_list) >= 3:
            clutch = round(sc_list.count(5) / len(sc_list) * 100, 1)
            if clutch > 0:
                stats["clutch_rate"][handle] = clutch

        # Variance — how chaotic is their scoring (higher = more dramatic)
        if len(non_dnf) >= 3:
            mean = sum(non_dnf) / len(non_dnf)
            var  = round(sum((x - mean) ** 2 for x in non_dnf) / len(non_dnf), 3)
            if var > 0:
                stats["variance"][handle] = var

        # Most improved — avg of last 7 games vs first 7 (need at least 14)
        if len(non_dnf) >= 14:
            first7 = non_dnf[:7]
            last7  = non_dnf[-7:]
            improvement = round(sum(first7)/7 - sum(last7)/7, 2)
            if improvement > 0:
                stats["most_improved"][handle] = improvement

    # ── Full card — players who have achieved all 5 Yahtzee categories ────────
    # Value = total count of all five category occurrences combined (more = more dominant)
    # Only players with at least 1 of each of the 5 categories qualify.
    _yahtzee_cats = ("yahtzee", "four_kind", "three_kind", "full_house", "straight")
    all_handles = {h for cat in _yahtzee_cats for h in stats[cat]}
    for handle in all_handles:
        if all(handle in stats[cat] for cat in _yahtzee_cats):
            total_hits = sum(stats[cat][handle] for cat in _yahtzee_cats)
            stats["full_card"][handle] = total_hits
            # Last date = most recent across all five categories
            cat_dates = [
                last_dates[cat][handle]
                for cat in _yahtzee_cats
                if handle in last_dates.get(cat, {})
            ]
            if cat_dates:
                last_dates.setdefault("full_card", {})[handle] = max(cat_dates)

    return (
        {k: list(v.items()) for k, v in stats.items()},
        last_dates,
    )


# Fun category metadata: (title, emoji, higher_is_better, format_string, min_value, description)
_FUN_CATEGORIES: dict[str, tuple] = {
    # Day of week (lower avg = better, so higher_is_better=False)
    "dow_monday":    ("Monday Standings",    "📅", False, "⌀{}",  0,
        "📅 Monday methodology: who scores best when the week is brand new and full of terrible promise. Ranked by average score, DNFs not counted. Bus schedule not consulted."),
    "dow_tuesday":   ("Tuesday Standings",   "📅", False, "⌀{}",  0,
        "📅 Tuesday methodology: the most overlooked day of the week deserves its own leaderboard. Ranked by average score. Tuesday did nothing wrong."),
    "dow_wednesday": ("Wednesday Standings", "📅", False, "⌀{}",  0,
        "📅 Wednesday methodology: hump day Routle performance, ranked by average score. The week is half over. So is your patience. Shine anyway."),
    "dow_thursday":  ("Thursday Standings",  "📅", False, "⌀{}",  0,
        "📅 Thursday methodology: so close to Friday. Ranked by average score. The MAX runs on Thursdays. So do you."),
    "dow_friday":    ("Friday Standings",    "📅", False, "⌀{}",  0,
        "📅 Friday methodology: end-of-week Routle energy, ranked by average score. Whether you're celebrating or commiserating, the 14 still runs."),
    "dow_saturday":  ("Saturday Standings",  "📅", False, "⌀{}",  0,
        "📅 Saturday methodology: weekend warrior edition. Average score on Saturdays only. The Saturday bus runs less often. Your focus does not."),
    "dow_sunday":    ("Sunday Standings",    "📅", False, "⌀{}",  0,
        "📅 Sunday methodology: the day of rest, ranked by who rests least. Average Sunday score. The weekly leaderboard resets at midnight. This does not."),
    # Score counts
    "score_2":       ("Most Guess-2s",       "🟨", True,  "{}×2", 1,
        "🟨 Methodology: total all-time count of scores that were exactly 2 guesses. Got it on the second try. Confident. Controlled. Not quite an ace but we see you."),
    "score_3":       ("Most Guess-3s",       "🟧", True,  "{}×3", 1,
        "🟧 Methodology: total count of scores that were exactly 3 guesses. The Switzerland of Routle scores — not too proud, not too ashamed, perfectly reasonable."),
    "score_4":       ("Most Guess-4s",       "🟥", True,  "{}×4", 1,
        "🟥 Methodology: total count of scores that were exactly 4 guesses. You were sweating a little. The route did not make it easy. You made it anyway."),
    "score_5":       ("Most Guess-5s",       "💀", True,  "{}×5", 1,
        "💀 Methodology: total count of scores that were exactly 5 guesses — the last-stop survival. One guess left. Pure adrenaline. Ranked by how many times you lived to tell it."),
    # Streaks
    "ace_streak":    ("Longest Ace Streak",  "⭐", True,  "{}d",  1,
        "⭐ Methodology: longest unbroken run of consecutive days with a first-guess ace. Miss a day, the streak ends. Like a bus that didn't wait."),
    "no_dnf_streak": ("Longest No-DNF Streak","🛡️", True, "{}d",  1,
        "🛡️ Methodology: longest stretch of consecutive days played without a single DNF. Any score 1–5 keeps it alive. A DNF breaks it. The route breaks no one twice."),
    "sub3_streak":      ("Longest Sub-3 Streak","🔥", True,  "{}d",  1,
        "🔥 Methodology: longest run of consecutive days where every score was 1 or 2 guesses. Ruthless consistency. The express service of Routle performance."),
    "struggle_streak":  ("Longest Struggle Bus Streak", "🚌", True, "{}d", 1,
        "🚌 Methodology: longest run of consecutive days scoring 4, 5, or DNF. The route was not cooperating. Neither was the schedule. You rode it anyway. Every. Single. Day."),
    # Yahtzee
    "yahtzee":       ("Yahtzee Club",        "🎲", True,  "{}×",  1,
        "🎲 Methodology: five identical scores on five consecutive calendar days. No DNFs. No gaps. Counted by occurrences. If you've done this once, you are built different. If you've done it twice — are you okay?"),
    "four_kind":     ("Four of a Kind",      "🎲", True,  "{}×",  1,
        "🎲 Methodology: four identical scores on four consecutive calendar days. No DNFs. A remarkable pattern that the route probably did not intend."),
    "three_kind":    ("Three of a Kind",     "🎲", True,  "{}×",  1,
        "🎲 Methodology: three identical scores on three consecutive calendar days. No DNFs. A coincidence the first time. A lifestyle after that."),
    "full_house":    ("Full House",          "🎲", True,  "{}×",  1,
        "🎲 Methodology: all five score values (1–5) in any order across five consecutive calendar days. No DNFs. A complete emotional journey in one work week."),
    "straight":      ("The Straight",        "🎲", True,  "{}×",  1,
        "🎲 Methodology: scores of 1, 2, 3, 4, and 5 — all five values, any order — across five consecutive calendar days. No DNFs. A perfectly balanced week, as all things should be."),
    "full_card":     ("Full Scorecard Club", "🎊", True,  "{}pts", 1,
        "🎊 Methodology: players who have achieved at least one of every Yahtzee category (Three of a Kind, Four of a Kind, Full House, Straight, and Yahtzee). Ranked by total combined hits across all five. This is an extremely short list. Probably."),
    # Comedy
    "dnf_royalty":   ("DNF Royalty 👑",      "💀", True,  "{}✗",  1,
        "💀 Methodology: all-time total DNFs, ranked highest to lowest and celebrated not shamed. The route is hard. You showed up anyway. Every single time. That's actually kind of heroic."),
    "eternal_3":     ("The Eternal 3",       "🟧", True,  "{}×3", 1,
        "🟧 Methodology: total all-time scores of exactly 3 guesses. A 3 is the bus arriving right on schedule — technically fine, spiritually neutral. Ranked by how many times you achieved this perfect mediocrity."),
    "clutch_rate":   ("Clutch Rate",         "😬", True,  "{}%",  0,
        "😬 Methodology: percentage of all plays that were exactly a guess-5 — the one-stop-left survival. Minimum 3 games to qualify. The higher your clutch rate, the more dramatic your commute."),
    "variance":      ("Most Dramatic",       "🎭", True,  "σ²={}", 0,
        "🎭 Methodology: score variance across all non-DNF plays. Higher variance means wilder swings between great days and bad ones. This is not a criticism. Portland runs on chaos and so do you."),
    "most_improved": ("Most Improved",       "📈", True,  "+{}⌀", 0,
        "📈 Methodology: average of first 7 non-DNF games vs last 7 non-DNF games. Requires at least 14 games. The bigger the drop, the more you've levelled up. The route didn't get easier. You got better."),
}


def format_fun_standings(category: str, scores: dict) -> list[str]:
    """Format a single fun standings category as Bluesky-sized pages."""
    if category not in _FUN_CATEGORIES:
        return [f"Unknown fun category: {category}"]

    title, emoji, higher, fmt, _, desc = _FUN_CATEGORIES[category]
    all_stats, last_dates = compute_fun_stats(scores)
    items = all_stats.get(category, [])

    if not items:
        return [f"{emoji} {GAME_NAME} {title}\n\nNo data yet — keep playing!"]

    player_dates = last_dates.get(category) if category in last_dates else None
    rows = _rank_rows(items, fmt=fmt, higher_is_better=higher, player_dates=player_dates)
    return _fun_page(title, rows, emoji=emoji, description=desc)


def format_fun_all(scores: dict, categories: list[str] | None = None) -> dict[str, list[str]]:
    """
    Format all (or a subset of) fun categories.
    Returns {category_key: [page1, page2, ...]} for each category with data.
    """
    cats = categories or list(_FUN_CATEGORIES.keys())
    all_stats, last_dates = compute_fun_stats(scores)
    result = {}
    for cat in cats:
        if cat not in _FUN_CATEGORIES:
            continue
        title, emoji, higher, fmt, min_val, desc = _FUN_CATEGORIES[cat]
        items = [(h, v) for h, v in all_stats.get(cat, []) if v > min_val]
        if not items:
            continue
        player_dates = last_dates.get(cat) if cat in last_dates else None
        rows = _rank_rows(items, fmt=fmt, higher_is_better=higher, player_dates=player_dates)
        result[cat] = _fun_page(title, rows, emoji=emoji, description=desc)
    return result


# ── Fun history (no-repeat tracking) ──────────────────────────────────────────

def load_fun_history() -> dict:
    """Load fun post history. Structure: {"category": "YYYY-MM-DD", ...}"""
    if os.path.exists(FUN_HISTORY_FILE):
        with open(FUN_HISTORY_FILE) as f:
            return json.load(f)
    return {}


def save_fun_history(history: dict) -> None:
    _tmp = FUN_HISTORY_FILE + ".tmp"
    with open(_tmp, "w") as f:
        json.dump(history, f, indent=2, sort_keys=True)
    os.replace(_tmp, FUN_HISTORY_FILE)


# Day-of-week categories keyed by Python weekday() index (0=Mon … 6=Sun)
_DOW_BY_WEEKDAY = {
    0: "dow_monday", 1: "dow_tuesday", 2: "dow_wednesday",
    3: "dow_thursday", 4: "dow_friday", 5: "dow_saturday", 6: "dow_sunday",
}


def pick_fun_category(now: datetime.datetime, scores: dict) -> str | None:
    """
    Pick a random fun category to post, subject to:
      - Must have data (at least one player with a qualifying value)
      - Has not been posted within the last 14 days
      - DOW categories only eligible on their matching day of the week

    Returns the category key, or None if nothing is eligible.
    """
    history = load_fun_history()
    cutoff  = (now.date() - datetime.timedelta(days=14)).isoformat()
    today_dow = now.weekday()   # 0=Mon … 6=Sun

    # Build eligible pool
    all_stats, _ = compute_fun_stats(scores)
    eligible  = []

    for cat, (title, emoji, higher, fmt, min_val, desc) in _FUN_CATEGORIES.items():
        # Skip if no data
        items = [(h, v) for h, v in all_stats.get(cat, []) if v > min_val]
        if not items:
            continue

        # DOW categories only on their matching weekday
        if cat.startswith("dow_"):
            if _DOW_BY_WEEKDAY.get(today_dow) != cat:
                continue

        # Skip if posted within the last 14 days
        last_posted = history.get(cat, "")
        if last_posted and last_posted > cutoff:
            continue

        eligible.append(cat)

    if not eligible:
        logger.info("No eligible fun categories today (all recently posted or no data).")
        return None

    chosen = random.choice(eligible)
    logger.info("🎲 Picked fun category: %s (eligible pool: %d)", chosen, len(eligible))
    return chosen


def post_fun_category(chosen: str, scores: dict, session: dict,
                      dry_run: bool = False) -> None:
    """Post a fun category and record it in fun_history.json."""
    pages = format_fun_standings(chosen, scores)
    _post_standings(chosen, pages, session, dry_run, pin=False)
    if not dry_run:
        history = load_fun_history()
        history[chosen] = datetime.date.today().isoformat()
        save_fun_history(history)
        logger.info("Recorded %s in fun history.", chosen)

def load_aces() -> dict:
    """Load ace counts. Structure: {"handle": int}"""
    if os.path.exists(ACES_FILE):
        with open(ACES_FILE) as f:
            return json.load(f)
    return {}


def save_aces(aces: dict):
    _tmp = ACES_FILE + ".tmp"
    with open(_tmp, "w") as f:
        json.dump(aces, f, indent=2, sort_keys=True)
    os.replace(_tmp, ACES_FILE)


# ─── Streak tracking ──────────────────────────────────────────────────────────

def load_streaks() -> dict:
    """Load streaks. Structure: {"handle": {"current": N, "best": N, "last_date": "YYYY-MM-DD"}}"""
    if os.path.exists(STREAKS_FILE):
        with open(STREAKS_FILE) as f:
            return json.load(f)
    return {}


def save_streaks(streaks: dict):
    _tmp = STREAKS_FILE + ".tmp"
    with open(_tmp, "w") as f:
        json.dump(streaks, f, indent=2, sort_keys=True)
    os.replace(_tmp, STREAKS_FILE)


def update_streak(streaks: dict, handle: str, date_str: str) -> tuple[int, int, bool]:
    """
    Update the streak for handle given a new result on date_str.
    Returns (current_streak, best_streak, is_new_best).
    """
    entry = streaks.get(handle, {"current": 0, "best": 0, "last_date": None})
    last = entry.get("last_date")

    if last:
        last_date = datetime.date.fromisoformat(last)
        this_date = datetime.date.fromisoformat(date_str)
        delta = (this_date - last_date).days
        if delta == 1:
            entry["current"] += 1          # consecutive day
        elif delta == 0:
            pass                           # same day duplicate, no change
        else:
            entry["current"] = 1           # streak broken
    else:
        entry["current"] = 1               # first ever result

    entry["last_date"] = date_str
    is_new_best = entry["current"] > entry.get("best", 0)
    if is_new_best:
        entry["best"] = entry["current"]

    streaks[handle] = entry
    return entry["current"], entry["best"], is_new_best


# ─── Opt-out management ────────────────────────────────────────────────────────

CHAT_URL = "https://api.bsky.chat/xrpc"
CHAT_PROXY = "did:web:api.bsky.chat#bsky_chat"


def load_optouts() -> set:
    """Load set of opted-out handles."""
    if os.path.exists(OPTOUTS_FILE):
        with open(OPTOUTS_FILE) as f:
            return set(json.load(f))
    return set()


def save_optouts(optouts: set):
    _tmp = OPTOUTS_FILE + ".tmp"
    with open(_tmp, "w") as f:
        json.dump(sorted(optouts), f, indent=2)
    os.replace(_tmp, OPTOUTS_FILE)


def format_player_yahtzee(handle: str, scores: dict) -> str:
    """
    Build a personal Yahtzee scorecard DM.
    Shows each of the five Yahtzee categories with a die face emoji,
    the player's count, most recent date achieved (or — if not yet achieved),
    and a special bonus message if they have unlocked all five categories.
    """
    all_stats, last_dates = compute_fun_stats(scores)
    short = _short_handle(handle)

    # (die_face, category_key, label)
    scorecard = [
        ("⚀", "three_kind", "Three of a Kind"),
        ("⚁", "four_kind",  "Four of a Kind"),
        ("⚂", "full_house", "Full House"),
        ("⚃", "straight",   "The Straight"),
        ("⚄", "yahtzee",    "Yahtzee!"),
    ]

    lines = [f"🎲 {GAME_NAME} Yahtzee Card — @{_mono(short)}", ""]

    achieved = []
    for die, cat, label in scorecard:
        player_val = dict(all_stats.get(cat, [])).get(handle)
        if player_val:
            count = _mono(str(int(player_val))) + "×"
            last  = last_dates.get(cat, {}).get(handle, "")
            if last:
                last_fmt = datetime.datetime.strptime(last, "%Y-%m-%d").strftime("%-m/%-d")
                stat = f"{count} (last {last_fmt})"
            else:
                stat = count
            achieved.append(cat)
        else:
            stat = "—"
        lines.append(f"{die} {label}: {stat}")

    lines.append("")
    total = len(achieved)

    if total == 5:
        # Full scorecard — special reward
        lines.append("🎊 FULL SCORECARD! You've hit every category.")
        lines.append("You are the dice. The dice are you. 🚌🎲")
    elif total == 0:
        lines.append("No categories yet — keep rolling! 🎲")
    else:
        remaining = 5 - total
        lines.append(f"{total}/5 categories unlocked. {remaining} to go!")

    return "\n".join(lines)


def format_player_history(handle: str, scores: dict) -> str:
    """
    Build a this-year score history DM for a player.
    One row per day played, grouped by month, with a score glyph.
    """
    year = datetime.date.today().year
    year_prefix = str(year)

    glyphs = {1: "🟩", 2: "🟨", 3: "🟧", 4: "🟥", 5: "💀", DNF: "❌"}

    # Gather this year's scores sorted by date
    days = sorted(
        ((d, scores[d][handle]) for d in scores if d.startswith(year_prefix) and handle in scores[d]),
        key=lambda x: x[0],
    )

    short = _short_handle(handle)
    if not days:
        return f"📅 No {GAME_NAME} scores for @{short} in {year} yet!"

    lines = [f"📅 {GAME_NAME} history {year} — @{_mono(short)}", ""]

    current_month = None
    for date_str, score in days:
        month = datetime.datetime.strptime(date_str, "%Y-%m-%d").strftime("%B")
        if month != current_month:
            if current_month is not None:
                lines.append("")
            lines.append(f"── {month} ──")
            current_month = month
        day_num = datetime.datetime.strptime(date_str, "%Y-%m-%d").strftime("%-d")
        glyph   = glyphs.get(score, "❓")
        score_display = "DNF" if score == DNF else str(score)
        lines.append(f"{glyph} {_mono(day_num.rjust(2))}  {score_display}")

    # Summary line
    non_dnf = [s for _, s in days if s != DNF]
    dnf_cnt = sum(1 for _, s in days if s == DNF)
    avg     = round(sum(non_dnf) / len(non_dnf), 2) if non_dnf else None
    lines.append("")
    summary = f"{len(days)} games played"
    if avg is not None:
        summary += f"  ·  ⌀{avg} (excl. DNFs)"
    if dnf_cnt:
        summary += f"  ·  {dnf_cnt} DNF{'s' if dnf_cnt != 1 else ''}"
    lines.append(summary)

    return "\n".join(lines)


def format_player_stats(handle: str, scores: dict, aces: dict,
                        streaks: dict, dnf_counts: dict) -> str:
    """
    Build a personal stats DM for a player. Fits within Bluesky's 300-char limit.
    Called when a player DMs the bot with the word STATS.
    """
    # ── Gather raw numbers ────────────────────────────────────────────────────
    all_dates = sorted(scores.keys())
    player_scores = [scores[d][handle] for d in all_dates if handle in scores[d]]

    games       = len(player_scores)
    aces_count  = aces.get(handle, 0)
    dnfs        = dnf_counts.get(handle, 0)
    streak_data = streaks.get(handle, {})
    current_str = streak_data.get("current", 0)
    best_str    = streak_data.get("best", 0)

    if not games:
        return f"📊 No {GAME_NAME} results on record for @{_short_handle(handle)} yet!"

    # ── Derived stats ─────────────────────────────────────────────────────────
    non_dnf   = [s for s in player_scores if s != DNF]
    avg_score = round(sum(non_dnf) / len(non_dnf), 2) if non_dnf else None
    best      = min(non_dnf) if non_dnf else None

    # ── All-time avg rank (among players with at least 3 games) ──────────────
    all_avgs = {}
    for h in {h for day in scores.values() for h in day}:
        h_scores = [scores[d][h] for d in all_dates if h in scores.get(d, {})]
        h_non_dnf = [s for s in h_scores if s != DNF]
        if len(h_scores) >= 3 and h_non_dnf:
            all_avgs[h] = sum(h_non_dnf) / len(h_non_dnf)
    rank_str = None
    if handle in all_avgs and len(all_avgs) >= 2:
        sorted_handles = sorted(all_avgs, key=lambda h: all_avgs[h])
        rank_pos  = sorted_handles.index(handle) + 1
        rank_str  = f"{rank_pos} of {len(all_avgs)}"

    # Score distribution (1–MAX_SQUARES + DNF)
    dist = {i: 0 for i in range(1, MAX_SQUARES + 1)}
    dist["✗"] = 0
    for s in player_scores:
        if s == DNF:
            dist["✗"] += 1
        elif s in dist:
            dist[s] += 1

    # Histogram bar (max 7 chars wide so lines stay short)
    max_count = max((v for v in dist.values()), default=1) or 1
    count_w   = len(str(max_count))
    def _bar(n: int) -> str:
        filled = round(n / max_count * 7)
        return "█" * filled if filled else ("▏" if n > 0 else " " * 0)

    # ── Build lines, stay under 300 chars ─────────────────────────────────────
    short = _short_handle(handle)
    lines = [
        f"📊 {GAME_NAME} stats — @{_mono(short)}",
        "",
        f"🎮 {_mono(str(games))} games  🔥 streak {_mono(str(current_str))}d  (best {_mono(str(best_str))}d)",
        f"⭐ {_mono(str(aces_count))} aces  💀 {_mono(str(dnfs))} DNFs",
    ]
    if avg_score is not None:
        avg_line = f"⌀ avg {_mono(str(avg_score))}  ·  best {_mono(str(best))}  (excl. DNFs)"
        if rank_str:
            avg_line += f"  ·  rank {_mono(rank_str)}"
        lines.append(avg_line)
    lines.append("")
    for key in list(range(1, MAX_SQUARES + 1)) + ["✗"]:
        n = dist[key]
        label = str(key) if key != "✗" else "✗"
        lines.append(f"{_mono(label)}▸ {_bar(n)} {_mono(f'{n:>{count_w}}')}")

    return "\n".join(lines)


def check_dms_for_optouts(session: dict, dry_run: bool = False) -> list[str]:
    """
    Poll the bot's DM inbox for messages containing STOP, START, STATS, HELP, YAHTZEE, HISTORY, or HIST.
    - STOP          : adds sender to optout list, sends confirmation DM.
    - START         : removes sender from optout list, sends welcome-back DM.
    - STATS         : sends sender a personal stats card DM.
    - YAHTZEE       : sends sender their personal Yahtzee scorecard DM.
    - HISTORY/HIST  : sends sender their score history for the current year.
    - HELP          : sends sender the command list.
    - unknown       : sends a friendly "missed that" reply pointing to HELP.
    Returns list of newly opted-out handles.
    """
    token = session["accessJwt"]
    headers = {
        "Authorization": f"Bearer {token}",
        "atproto-proxy": CHAT_PROXY,
    }

    try:
        resp = requests.get(
            f"{CHAT_URL}/chat.bsky.convo.listConvos",
            headers=headers,
            params={"limit": 50},
        )
        resp.raise_for_status()
        convos = resp.json().get("convos", [])
    except Exception as e:
        logger.warning("Could not fetch DMs: %s", e)
        return []

    optouts = load_optouts()
    newly_opted_out = []

    bot_did = session.get("did")

    for convo in convos:
        convo_id = convo.get("id")
        last_msg = convo.get("lastMessage", {})

        # Skip messages the bot itself sent — otherwise our own confirmation
        # DMs (which contain "START") trigger a spurious welcome-back reply.
        if last_msg.get("sender", {}).get("did") == bot_did:
            continue

        msg_text = last_msg.get("text", "").strip().upper()

        is_stop    = "STOP"    in msg_text
        is_start   = "START"   in msg_text
        is_stats   = msg_text == "STATS"
        is_help    = msg_text == "HELP"
        is_yahtzee = msg_text == "YAHTZEE"
        is_history = msg_text in ("HISTORY", "HIST")
        is_known   = is_stop or is_start or is_stats or is_help or is_yahtzee or is_history

        # Find the sender (the non-bot member) — needed for all branches
        sender_handle = None
        for m in convo.get("members", []):
            if m.get("did") != bot_did:
                sender_handle = m.get("handle")
                break

        if not sender_handle:
            continue

        def _send_dm(text: str):
            try:
                requests.post(
                    f"{CHAT_URL}/chat.bsky.convo.sendMessage",
                    headers=headers,
                    json={"convoId": convo_id, "message": {"text": text}},
                ).raise_for_status()
            except Exception as e:
                logger.warning("Could not send DM: %s", e)

        if is_stop and sender_handle not in optouts:
            logger.info("🛑 Opt-out received from @%s", sender_handle)
            optouts.add(sender_handle)
            newly_opted_out.append(sender_handle)
            if not dry_run:
                _send_dm(
                    "You will no longer receive replies to your "
                    "Routle - TriMet posts. "
                    "DM START anytime to opt back in. 🚌"
                )

        elif is_stop:
            logger.debug("STOP from @%s (already opted out — no action needed)", sender_handle)
            if not dry_run:
                _send_dm("You're already opted out. DM START anytime to opt back in. 🚌")

        elif is_start and sender_handle in optouts:
            logger.info("✅ Opt-in received from @%s", sender_handle)
            optouts.discard(sender_handle)
            if not dry_run:
                _send_dm("Welcome back! Routle bot replies are back on for you. 🟩")

        elif is_start:
            logger.debug("START from @%s (not opted out — no action needed)", sender_handle)
            if not dry_run:
                _send_dm("You're already receiving replies — no changes made. 🟩")

        elif is_stats:
            logger.info("📊 Stats request from @%s", sender_handle)
            if not dry_run:
                scores     = load_scores()
                aces       = load_aces()
                streaks    = load_streaks()
                dnf_counts = load_dnf_counts()
                stats_msg  = format_player_stats(
                    sender_handle, scores, aces, streaks, dnf_counts
                )
                _send_dm(stats_msg)

        elif is_yahtzee:
            logger.info("🎲 Yahtzee card request from @%s", sender_handle)
            if not dry_run:
                scores = load_scores()
                _send_dm(format_player_yahtzee(sender_handle, scores))

        elif is_history:
            logger.info("📅 History request from @%s", sender_handle)
            if not dry_run:
                scores = load_scores()
                _send_dm(format_player_history(sender_handle, scores))

        elif is_help:
            logger.info("❓ Help request from @%s", sender_handle)
            if not dry_run:
                _send_dm(
                    f"👋 {GAME_NAME} bot commands — DM any of these words:\n\n"
                    "STATS   — your personal stats card (games, avg, rank, streaks, aces)\n"
                    "HIST    — your score history for this year\n"
                    "YAHTZEE — your personal Yahtzee scorecard 🎲\n"
                    "STOP    — turn off reply reactions\n"
                    "START   — turn reply reactions back on\n"
                    "HELP    — show this message"
                )

        elif not is_known:
            logger.info("❓ Unknown DM from @%s: %s", sender_handle, msg_text[:40])
            if not dry_run:
                _send_dm(
                    "Sorry, I missed that while the driver was making an announcement. 🚌\n\n"
                    f"👋 {GAME_NAME} bot commands — DM any of these words:\n\n"
                    "STATS   — your personal stats card (games, avg, rank, streaks, aces)\n"
                    "HIST    — your score history for this year\n"
                    "YAHTZEE — your personal Yahtzee scorecard 🎲\n"
                    "STOP    — turn off reply reactions\n"
                    "START   — turn reply reactions back on\n"
                    "HELP    — show this message"
                )

    save_optouts(optouts)
    return newly_opted_out


def send_dm(session: dict, to_handle: str, text: str) -> bool:
    """
    Send a DM to a specific handle. Returns True on success.
    Requires the App Password to have DM access enabled.
    """
    token = session["accessJwt"]
    headers = {
        "Authorization": f"Bearer {token}",
        "atproto-proxy": CHAT_PROXY,
    }
    try:
        # Resolve handle → DID
        did = resolve_did(to_handle, token)
        # Get or create conversation
        resp = requests.get(
            f"{CHAT_URL}/chat.bsky.convo.getConvoForMembers",
            headers=headers,
            params={"members": [did]},
        )
        resp.raise_for_status()
        convo_id = resp.json()["convo"]["id"]
        # Send message
        requests.post(
            f"{CHAT_URL}/chat.bsky.convo.sendMessage",
            headers=headers,
            json={"convoId": convo_id, "message": {"text": text}},
        ).raise_for_status()
        return True
    except Exception as e:
        logger.warning("Could not send DM to @%s: %s", to_handle, e)
        return False


def record_ace(aces: dict, handle: str) -> int:
    """Increment ace count for handle, return new total."""
    aces[handle] = aces.get(handle, 0) + 1
    return aces[handle]


# ─── DNF count tracking ───────────────────────────────────────────────────────

def load_dnf_counts() -> dict:
    """Load DNF counts. Structure: {"handle": int}"""
    if os.path.exists(DNF_COUNTS_FILE):
        with open(DNF_COUNTS_FILE) as f:
            return json.load(f)
    return {}


def save_dnf_counts(dnf_counts: dict):
    _tmp = DNF_COUNTS_FILE + ".tmp"
    with open(_tmp, "w") as f:
        json.dump(dnf_counts, f, indent=2, sort_keys=True)
    os.replace(_tmp, DNF_COUNTS_FILE)


def record_dnf(dnf_counts: dict, handle: str) -> int:
    """Increment DNF count for handle, return new total."""
    dnf_counts[handle] = dnf_counts.get(handle, 0) + 1
    return dnf_counts[handle]


def games_played_count(scores: dict, handle: str) -> int:
    """Count total games played by handle across all dates in scores.json."""
    return sum(1 for day in scores.values() if handle in day)


# ─── Community records tracking ───────────────────────────────────────────────
# records.json structure:
# {
#   "daily_players":    {"record": 12, "date": "2026-04-09"},
#   "weekly_players":   {"record": 18, "date": "2026-04-06"},   ← week start (Monday)
#   "monthly_players":  {"record": 22, "date": "2026-04"},
#   "new_players_day":  {"record": 5,  "date": "2026-04-01"},
#   "new_players":      {"YYYY-MM-DD": N, ...},                 ← daily new-player counts
#   "daily_score_1":    {"record": 7,  "date": "2026-04-09"},   ← most aces in a day
#   "daily_score_2":    {"record": 5,  "date": "2026-04-09"},   ← most guess-2s in a day
#   "daily_score_3":    {"record": 4,  "date": "2026-04-09"},
#   "daily_score_4":    {"record": 3,  "date": "2026-04-09"},
#   "daily_score_5":    {"record": 2,  "date": "2026-04-09"},
#   "daily_score_6":    {"record": 3,  "date": "2026-04-09"},   ← most DNFs (DNF = MAX_SQUARES+1)
# }

def load_records() -> dict:
    if os.path.exists(RECORDS_FILE):
        with open(RECORDS_FILE) as f:
            return json.load(f)
    return {}


def save_records(records: dict):
    _tmp = RECORDS_FILE + ".tmp"
    with open(_tmp, "w") as f:
        json.dump(records, f, indent=2, sort_keys=True)
    os.replace(_tmp, RECORDS_FILE)


def count_new_players(scores: dict, known_before: set, date_str: str) -> int:
    """
    Count players who appear for the first time on date_str
    (i.e. have no scores on any earlier date).
    known_before is the set of all handles seen before date_str.
    """
    today_handles = set(scores.get(date_str, {}).keys())
    return len(today_handles - known_before)


def check_and_update_records(
    scores: dict,
    date_str: str,
    period: str,
) -> list[str]:
    """
    Check whether today's/this week's/this month's player counts set new records.
    Updates records.json in place and returns a list of record-broken messages
    (empty if no records broken).

    period : "daily" | "weekly" | "monthly"
    """
    records  = load_records()
    broken   = []
    ref      = datetime.date.fromisoformat(date_str)

    if period == "daily":
        day_scores = scores.get(date_str, {})

        # ── Daily player count ────────────────────────────────────────────────
        day_count = len(day_scores)
        prev      = records.get("daily_players", {})
        if day_count > prev.get("record", 0):
            records["daily_players"] = {"record": day_count, "date": date_str}
            broken.append(
                f"📈 New daily record: {day_count} players today"
                + (f" (previous: {prev['record']} on {prev['date']})" if prev else "")
            )

        # ── Per-score daily records (1 ace through 5, plus DNF) ───────────────
        _score_meta = {
            1:   ("🟩", "aces"),
            2:   ("🟨", "guess-2s"),
            3:   ("🟧", "guess-3s"),
            4:   ("🟥", "guess-4s"),
            5:   ("💀", "guess-5s"),
            DNF: ("❌", "DNFs"),
        }
        score_counts: dict[int, int] = {}
        for sc in day_scores.values():
            score_counts[sc] = score_counts.get(sc, 0) + 1

        for score_val, (emoji, label) in _score_meta.items():
            count = score_counts.get(score_val, 0)
            if count == 0:
                continue
            key  = f"daily_score_{score_val}"
            prev = records.get(key, {})
            if count > prev.get("record", 0):
                records[key] = {"record": count, "date": date_str}
                broken.append(
                    f"{emoji} Most {label} in a day: {count}"
                    + (f" (previous: {prev['record']} on {prev['date']})" if prev else "")
                )

        # ── New players today ─────────────────────────────────────────────────
        all_dates      = sorted(scores.keys())
        prior_dates    = [d for d in all_dates if d < date_str]
        known_before   = {h for d in prior_dates for h in scores[d]}
        new_today      = count_new_players(scores, known_before, date_str)

        # Store per-day new-player count
        np = records.setdefault("new_players", {})
        np[date_str] = new_today

        prev_np = records.get("new_players_day", {})
        if new_today > prev_np.get("record", 0):
            records["new_players_day"] = {"record": new_today, "date": date_str}
            broken.append(
                f"👋 New players record: {new_today} new player{'s' if new_today != 1 else ''} today"
                + (f" (previous: {prev_np['record']} on {prev_np['date']})" if prev_np else "")
            )

    elif period == "weekly":
        # ── Weekly unique player count ────────────────────────────────────────
        monday   = ref - datetime.timedelta(days=ref.weekday())
        keys     = [(monday + datetime.timedelta(days=i)).isoformat() for i in range(7)]
        players  = {h for k in keys for h in scores.get(k, {})}
        count    = len(players)
        prev     = records.get("weekly_players", {})
        if count > prev.get("record", 0):
            records["weekly_players"] = {"record": count, "date": monday.isoformat()}
            broken.append(
                f"📈 New weekly record: {count} unique players this week"
                + (f" (previous: {prev['record']} w/c {prev['date']})" if prev else "")
            )

    elif period == "monthly":
        # ── Monthly unique player count ───────────────────────────────────────
        month_prefix = date_str[:7]   # "YYYY-MM"
        players      = {h for k, v in scores.items() if k.startswith(month_prefix) for h in v}
        count        = len(players)
        prev         = records.get("monthly_players", {})
        if count > prev.get("record", 0):
            records["monthly_players"] = {"record": count, "date": month_prefix}
            broken.append(
                f"📈 New monthly record: {count} unique players this month"
                + (f" (previous: {prev['record']} in {prev['date']})" if prev else "")
            )

    save_records(records)
    return broken


def format_records_reply(broken: list[str], date_str: str) -> str:
    """Format a reply post announcing broken records."""
    date_display = datetime.datetime.strptime(date_str, "%Y-%m-%d").strftime("%B %-d, %Y")
    lines = [f"🏅 {GAME_NAME} community records — {date_display}", ""] + broken
    return "\n".join(lines)



# Thresholds are configured in config.py:
#   ACE_MILESTONES      — set of ace counts that trigger a milestone reply
#   GAMES_MILESTONES    — set of games-played counts that trigger a milestone reply
#   DNF_MILESTONE_EVERY — fire every N DNFs (integer)


def is_ace_milestone(count: int) -> bool:
    return count in ACE_MILESTONES or (count >= 100 and count % 100 == 0)


def is_games_milestone(count: int) -> bool:
    return count in GAMES_MILESTONES


def is_dnf_milestone(count: int) -> bool:
    return count > 0 and count % DNF_MILESTONE_EVERY == 0


def _stars(count: int) -> str:
    """Return a star string for ace milestone messages.
    Up to 10: individual ⭐ icons. Above 10: ⭐×N."""
    if count <= 10:
        return "⭐" * count
    return f"⭐×{count}"


def make_milestone_post(handle: str, display_name: str,
                        kind: str, count: int) -> str:
    """
    Build a milestone message. kind is "ace", "games", or "dnf".
    Falls back gracefully if no messages configured.
    Placeholders: {display_name}, {handle}, {count}, {stars} (ace only).
    """
    from config import MILESTONE_MESSAGES
    pool = MILESTONE_MESSAGES.get(kind, [])
    if not pool:
        return ""
    return random.choice(pool).format(
        display_name=display_name,
        handle=handle,
        count=count,
        stars=_stars(count) if kind == "ace" else "",
    )


# ─── Reaction messages ─────────────────────────────────────────────────────────

# Messages are defined in config.py — edit them there.
# Templates support: {handle}, {aces_line} (ace messages) or {handle} (DNF messages).
# ACE_COUNT_LINES support: {aces}

def _ace_count_line(aces: int) -> str:
    from config import ACE_COUNT_LINES
    return random.choice(ACE_COUNT_LINES).format(aces=aces)


def _streak_suffix(current_streak: int, is_new_best: bool) -> str:
    """Return a streak note to append to reactions, or empty string."""
    if current_streak >= 2 and is_new_best:
        return f"\n\n🔥 New best streak: {current_streak} days in a row!"
    if current_streak >= 7:
        return f"\n\n🔥 {current_streak}-day streak!!"
    if current_streak >= 3:
        return f"\n\n🔥 {current_streak} days in a row!"
    if current_streak == 2:
        return "\n\n🔥 2 days running!"
    return ""


def make_ace_post(handle: str, display_name: str, ace_count: int,
                  current_streak: int = 0, is_new_best: bool = False) -> str:
    if ace_count == 1:
        from config import FIRST_ACE_MESSAGES
        msg = random.choice(FIRST_ACE_MESSAGES)
        text = msg.format(display_name=display_name, handle=handle)
    else:
        from config import ACE_MESSAGES
        msg = random.choice(ACE_MESSAGES)
        aces_line = _ace_count_line(ace_count)
        text = msg.format(display_name=display_name, handle=handle, aces_line=aces_line)
    return text + _streak_suffix(current_streak, is_new_best)


def make_dnf_post(handle: str, display_name: str) -> str:
    from config import DNF_MESSAGES
    return random.choice(DNF_MESSAGES).format(display_name=display_name, handle=handle)


def make_score_post(handle: str, display_name: str, score: int,
                    current_streak: int = 0, is_new_best: bool = False) -> str:
    """Return a reaction message for scores 2-5. Falls back silently if not configured."""
    from config import SCORE_MESSAGES
    messages = SCORE_MESSAGES.get(score, [])
    if not messages:
        return ""
    text = random.choice(messages).format(display_name=display_name, handle=handle)
    return text + _streak_suffix(current_streak, is_new_best)


# ─── Feed collection ───────────────────────────────────────────────────────────

def collect_results(session: dict, scores: dict, dry_run: bool = False) -> int:
    """
    Fetch the feed, record new results, and post ace/DNF reactions.
    Returns number of new entries recorded.
    """
    token = session["accessJwt"]
    feed_uri = build_feed_uri(FEED_CREATOR_HANDLE, FEED_SLUG, token)
    logger.info("Fetching custom feed: %s", feed_uri)
    feed = get_custom_feed(feed_uri, token, limit=100)
    logger.info("Retrieved %d post(s).", len(feed))

    aces = load_aces()
    dnf_counts = load_dnf_counts()
    streaks = load_streaks()
    optouts = load_optouts()
    known = load_known_players()
    new_entries = 0

    for item in feed:
        post = item.get("post", {})
        record = post.get("record", {})
        text = record.get("text", "")
        author_obj = post.get("author", {})
        author = author_obj.get("handle", "unknown")
        author_did = author_obj.get("did", "")
        display_name = author_obj.get("displayName") or author  # fall back to handle if unset

        date_str, score = parse_result(text)
        if date_str is None:
            continue

        # Grab the AT-URI and CID so we can reply to this specific post
        post_ref = {"uri": post.get("uri", ""), "cid": post.get("cid", "")}

        scores.setdefault(date_str, {})
        if author not in scores[date_str]:          # first submission per day wins
            scores[date_str][author] = score
            new_entries += 1
            logger.info("✓ %s: %s/%s on %s", author, score, MAX_SQUARES, date_str)

            # Add to Routlers list if new player
            maybe_add_to_routlers(session, author, author_did, known, optouts, dry_run)

            # Update streak
            current_streak, best_streak, is_new_best = update_streak(streaks, author, date_str)

            # Skip reactions for opted-out users
            if author in optouts:
                logger.debug("Skipping reaction — @%s opted out", author)
                continue

            # Skip reactions during quiet hours (scores already recorded above)
            if _in_quiet_hours():
                logger.debug("Skipping reaction — quiet hours (%s–%s)", QUIET_HOURS_START, QUIET_HOURS_END)
                continue

            # Games played milestone check (applies to all scores)
            total_games = games_played_count(scores, author)
            if is_games_milestone(total_games):
                milestone_msg = make_milestone_post(author, display_name, "games", total_games)
                if milestone_msg:
                    _post_and_print(f"Games milestone ({total_games}) for @{author}", milestone_msg, session, dry_run, reply_to=post_ref, is_reaction=True)

            if score == 1:
                # Ace! Update count and post congratulations as a reply
                ace_count = record_ace(aces, author)
                reaction = make_ace_post(author, display_name, ace_count, current_streak, is_new_best)
                _post_and_print(f"Ace reaction for @{author}", reaction, session, dry_run, reply_to=post_ref, is_reaction=True)
                # Ace milestone check
                if is_ace_milestone(ace_count):
                    milestone_msg = make_milestone_post(author, display_name, "ace", ace_count)
                    if milestone_msg:
                        _post_and_print(f"Ace milestone ({ace_count}) for @{author}", milestone_msg, session, dry_run, reply_to=post_ref, is_reaction=True)

            elif score == DNF:
                # Missed every stop — commiserate as a reply
                dnf_count = record_dnf(dnf_counts, author)
                reaction = make_dnf_post(author, display_name)
                _post_and_print(f"DNF reaction for @{author}", reaction, session, dry_run, reply_to=post_ref, is_reaction=True)
                # DNF milestone check
                if is_dnf_milestone(dnf_count):
                    milestone_msg = make_milestone_post(author, display_name, "dnf", dnf_count)
                    if milestone_msg:
                        _post_and_print(f"DNF milestone ({dnf_count}) for @{author}", milestone_msg, session, dry_run, reply_to=post_ref, is_reaction=True)

            elif 2 <= score <= MAX_SQUARES:
                # Score-specific reaction for guesses 2–5
                reaction = make_score_post(author, display_name, score, current_streak, is_new_best)
                if reaction:
                    _post_and_print(f"Score {score} reaction for @{author}", reaction, session, dry_run, reply_to=post_ref, is_reaction=True)

    save_aces(aces)
    save_dnf_counts(dnf_counts)
    save_streaks(streaks)
    save_known_players(known)
    logger.info("%d new result(s) recorded.", new_entries)
    return new_entries


# ─── Profile pin ──────────────────────────────────────────────────────────────

def pin_post(session: dict, post_uri: str, post_cid: str) -> bool:
    """
    Pin a post to the bot's Bluesky profile by updating the actor profile record.
    Returns True on success.
    """
    token = session["accessJwt"]
    did   = session["did"]

    # Fetch the current profile record so we don't overwrite other fields
    try:
        resp = requests.get(
            f"{BASE_URL}/com.atproto.repo.getRecord",
            params={"repo": did, "collection": "app.bsky.actor.profile", "rkey": "self"},
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()
        current = resp.json().get("value", {})
        swap_cid = resp.json().get("cid")          # needed for compare-and-swap
    except Exception as e:
        logger.warning("Could not fetch profile record: %s", e)
        return False

    # Merge pinnedPost into the existing profile record
    current["pinnedPost"] = {"uri": post_uri, "cid": post_cid}
    current.setdefault("$type", "app.bsky.actor.profile")

    try:
        body = {
            "repo": did,
            "collection": "app.bsky.actor.profile",
            "rkey": "self",
            "record": current,
        }
        if swap_cid:
            body["swapRecord"] = swap_cid          # atomic compare-and-swap

        requests.post(
            f"{BASE_URL}/com.atproto.repo.putRecord",
            json=body,
            headers={"Authorization": f"Bearer {token}"},
        ).raise_for_status()
        return True
    except Exception as e:
        logger.warning("Could not pin post: %s", e)
        return False


# ─── Posting helpers ───────────────────────────────────────────────────────────

OPTOUT_TAG   = "\n\nDM 'stop' to discontinue replies"
MAX_RETRIES  = 3     # attempts before giving up on a single post
RETRY_DELAY  = 3.0   # seconds between retry attempts


def _post_with_retry(text: str, session: dict,
                     reply_to: dict | None = None,
                     root_ref: dict | None = None) -> dict | None:
    """
    Call post_text with up to MAX_RETRIES attempts on transient errors.
    Returns the result dict on success, None if all attempts fail.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return post_text(text, session, reply_to=reply_to, root_ref=root_ref)
        except Exception as e:
            if attempt < MAX_RETRIES:
                logger.warning("Post attempt %d/%d failed: %s — retrying in %.0fs",
                               attempt, MAX_RETRIES, e, RETRY_DELAY)
                time.sleep(RETRY_DELAY)
            else:
                logger.error("Post failed after %d attempts: %s", MAX_RETRIES, e)
    return None


def _post_and_print(label: str, text: str, session: dict, dry_run: bool,
                    reply_to: dict | None = None,
                    root_ref: dict | None = None,
                    is_reaction: bool = False,
                    pin: bool = True) -> dict | None:
    """
    Post text, confirm it is indexed in the AppView, and return the ref.
    Returns {"uri": ..., "cid": ...} on success, None on failure or dry_run.
    """
    # Append opt-out instructions only to player reaction replies,
    # NOT to standings continuation posts which also use reply_to.
    if reply_to and is_reaction:
        text = text + OPTOUT_TAG
    logger.info("\n── %s ──\n%s\n%s", label, text, "─" * 40)
    if not dry_run:
        result = _post_with_retry(text, session, reply_to=reply_to, root_ref=root_ref)
        if not result:
            return None
        uri = result.get("uri", "")
        cid = result.get("cid", "")
        logger.info("✅ Posted! URI: %s", uri)

        # Read-confirm: verify the post is visible in the AppView before returning.
        # This is critical for threading — the next reply must be able to find its parent.
        if uri:
            confirmed = _await_indexed(uri, session["accessJwt"])
            if confirmed:
                logger.debug("Confirmed indexed: %s", uri)
            else:
                logger.warning("Could not confirm indexing (timed out) — thread may break: %s", uri)

        # For top-level leaderboard posts (not reactions or continuations)
        if not reply_to:
            from config import NOTIFY_HANDLE
            if NOTIFY_HANDLE:
                rkey = uri.split("/")[-1] if uri else ""
                post_url = f"https://bsky.app/profile/{BOT_HANDLE}/post/{rkey}" if rkey else ""
                dm_text = f"📋 {label} standings posted!"
                if post_url:
                    dm_text += f"\n{post_url}"
                send_dm(session, NOTIFY_HANDLE, dm_text)
                logger.info("📨 Notified @%s", NOTIFY_HANDLE)
            # Pin post to bot profile if configured and allowed
            if pin and PIN_LEADERBOARD and uri and cid:
                if pin_post(session, uri, cid):
                    logger.info("📌 Pinned to profile")
                # (failure already logged inside pin_post)
        return {"uri": uri, "cid": cid}
    else:
        logger.info("  (dry run — not posted)")
        return None


def _await_indexed(uri: str, token: str, timeout: int = 30, interval: float = 2.0) -> bool:
    """
    Poll app.bsky.feed.getPosts until the post appears in the AppView or timeout.
    Returns True if found, False if timed out.
    """
    deadline = time.time() + timeout
    headers = {"Authorization": f"Bearer {token}"}
    while time.time() < deadline:
        try:
            resp = _api_request(
                "GET",
                f"{BASE_URL}/app.bsky.feed.getPosts",
                params={"uris": uri},
                headers=headers,
                timeout=5,
            )
            if resp.json().get("posts"):
                return True
        except _RETRYABLE as exc:
            logger.debug("_await_indexed transient error: %s", exc)
        except Exception as exc:
            logger.debug("_await_indexed error: %s", exc)
        time.sleep(interval)
    return False


def _post_standings(label: str, pages: list[str], session: dict, dry_run: bool, pin: bool = True) -> dict | None:
    """
    Post a period standings. First page is a top-level post;
    subsequent pages are threaded as replies, each replying to the previous.
    pin: whether to pin the first page to the bot profile (False for ad-hoc posts).
    After each post we poll the AppView until it confirms the post is indexed
    before posting the next reply — this prevents broken thread chains.
    Returns the root post ref {"uri": ..., "cid": ...} or None on failure/dry_run.
    """
    if not pages:
        return None
    # Post page 1 — this becomes the thread root
    root_result = _post_and_print(label, pages[0], session, dry_run, pin=pin)
    if len(pages) == 1:
        return root_result

    # root_ref stays fixed as page 1 for the whole thread.
    # prev_ref advances to each new post so parent chains correctly.
    root_ref = root_result
    prev_ref = root_result

    for i, page in enumerate(pages[1:], 2):
        cont_label = f"{label} cont. ({i}/{len(pages)})"
        prev_ref = _post_and_print(
            cont_label, page, session, dry_run,
            reply_to=prev_ref, root_ref=root_ref,
        )

    return root_result


# ─── Public run functions (used by scheduler + CLI) ────────────────────────────

def run(
    post_date: str | None = None,
    dry_run: bool = False,
    period: str = "daily",
):
    """
    Collect results and post leaderboard(s).

    period : "daily" | "weekly" | "monthly" | "yearly" | "all"
    post_date : reference date "YYYY-MM-DD" (default: today)
    """
    ref = datetime.date.fromisoformat(post_date) if post_date else datetime.date.today()
    logger.info("🤖 %s Bot — period=%s  ref=%s", GAME_NAME, period, ref)
    logger.info("Logging in as @%s...", BOT_HANDLE)
    session = login(BOT_HANDLE, BOT_PASSWORD)
    logger.info("✓ Logged in.")

    scores = load_scores()
    collect_results(session, scores, dry_run=dry_run)
    save_scores(scores)

    if period in ("daily", "all"):
        daily_ref = _post_and_print(
            "Daily",
            format_daily_leaderboard(ref.isoformat(), scores.get(ref.isoformat(), {}), scores),
            session, dry_run,
        )
        # Check for community records and post as a nested reply if any were broken
        broken = check_and_update_records(scores, ref.isoformat(), "daily")
        if broken and daily_ref:
            records_text = format_records_reply(broken, ref.isoformat())
            _post_and_print(
                "Daily records",
                records_text,
                session, dry_run,
                reply_to=daily_ref,
                root_ref=daily_ref,
                pin=False,
            )

    for label, pages in [
        ("Weekly",  format_weekly_leaderboard(ref, scores)),
        ("Monthly", format_monthly_leaderboard(ref, scores)),
        ("Yearly",  format_yearly_leaderboard(ref, scores)),
    ]:
        if period not in (label.lower(), "all"):
            continue
        root_ref = _post_standings(label, pages, session, dry_run)
        # Check records for weekly and monthly periods
        if label in ("Weekly", "Monthly") and root_ref:
            broken = check_and_update_records(scores, ref.isoformat(), label.lower())
            if broken:
                records_text = format_records_reply(broken, ref.isoformat())
                _post_and_print(
                    f"{label} records",
                    records_text,
                    session, dry_run,
                    reply_to=root_ref,
                    root_ref=root_ref,
                    pin=False,
                )


def backfill(session: dict | None = None, dry_run: bool = False, date_filter: str | None = None) -> int:
    """
    Replay reactions for results already saved in scores.json.
    Fetches the live feed to get post URIs/CIDs and display names,
    then fires reactions for every matching entry without re-recording scores.

    date_filter: if set (YYYY-MM-DD), only backfill that specific date.
    Returns number of reactions fired.
    """
    if session is None:
        session = login(BOT_HANDLE, BOT_PASSWORD)

    scores = load_scores()
    if not scores:
        logger.info("No scores on record — nothing to backfill.")
        return 0

    token = session["accessJwt"]
    feed_uri = build_feed_uri(FEED_CREATOR_HANDLE, FEED_SLUG, token)
    logger.info("Fetching feed for backfill: %s", feed_uri)
    feed = get_custom_feed(feed_uri, token, limit=100)
    logger.info("Retrieved %d post(s).", len(feed))

    aces = load_aces()
    fired = 0

    for item in feed:
        post = item.get("post", {})
        record = post.get("record", {})
        text = record.get("text", "")
        author_obj = post.get("author", {})
        author = author_obj.get("handle", "unknown")
        display_name = author_obj.get("displayName") or author

        date_str, score = parse_result(text)
        if date_str is None:
            continue
        if date_filter and date_str != date_filter:
            continue

        # Only fire for entries already in scores.json
        if scores.get(date_str, {}).get(author) != score:
            continue

        post_ref = {"uri": post.get("uri", ""), "cid": post.get("cid", "")}
        logger.info("↺ Backfilling %s: %s/%s on %s", author, score, MAX_SQUARES, date_str)

        if score == 1:
            ace_count = record_ace(aces, author)
            reaction = make_ace_post(author, display_name, ace_count)
            _post_and_print(f"Ace backfill for @{author}", reaction, session, dry_run, reply_to=post_ref, is_reaction=True)
            fired += 1

        elif score == DNF:
            reaction = make_dnf_post(author, display_name)
            _post_and_print(f"DNF backfill for @{author}", reaction, session, dry_run, reply_to=post_ref, is_reaction=True)
            fired += 1

        elif 2 <= score <= MAX_SQUARES:
            reaction = make_score_post(author, display_name, score)
            if reaction:
                _post_and_print(f"Score {score} backfill for @{author}", reaction, session, dry_run, reply_to=post_ref, is_reaction=True)
                fired += 1

    save_aces(aces)
    logger.info("%d reaction(s) fired.", fired)
    return fired


def poll(session: dict | None = None, dry_run: bool = False) -> int:
    """
    Lightweight poll: fetch the feed, record new results, fire reactions,
    and check DMs for STOP/START/STATS/HELP requests.
    Does NOT post any leaderboard. Safe to call every few minutes.
    Returns number of new entries recorded.
    """
    if session is None:
        session = login(BOT_HANDLE, BOT_PASSWORD)
    check_dms_for_optouts(session, dry_run=dry_run)
    scores = load_scores()
    new = collect_results(session, scores, dry_run=dry_run)
    save_scores(scores)
    return new


def run_standings(
    period: str,
    from_date: str | None = None,
    to_date: str | None = None,
    dry_run: bool = False,
):
    """
    Post an ad-hoc standings for any period or custom date range.

    period    : "weekly" | "monthly" | "yearly" | "custom" | "participation"
    from_date : "YYYY-MM-DD" start of custom range (required if period="custom")
    to_date   : "YYYY-MM-DD" end of custom range (defaults to today if period="custom")
    """
    logger.info("Logging in as @%s...", BOT_HANDLE)
    session = login(BOT_HANDLE, BOT_PASSWORD)
    logger.info("✓ Logged in.")
    scores = load_scores()

    today = datetime.date.today()

    if period == "custom":
        end = datetime.date.fromisoformat(to_date) if to_date else today
        if from_date:
            start = datetime.date.fromisoformat(from_date)
        else:
            # No --from supplied — use the earliest date in scores.json
            all_dates = sorted(scores.keys())
            if not all_dates:
                logger.error("No scores on record yet.")
                return
            start = datetime.date.fromisoformat(all_dates[0])
            logger.info("No --from date given — using earliest recorded date: %s", start)
        delta = (end - start).days + 1
        date_keys = [(start + datetime.timedelta(days=i)).isoformat() for i in range(delta)]
        label = f"Standings — {start.strftime('%b %-d')} to {end.strftime('%b %-d, %Y')}"
        agg = scores_for_period(scores, date_keys)
        pages = format_period_leaderboard(label, agg, scores, date_keys, method=CUSTOM_RANKING_METHOD)
    elif period == "participation":
        # All-time participation — every date in scores.json
        all_dates = sorted(scores.keys())
        if not all_dates:
            logger.error("No scores on record yet.")
            return
        start = datetime.date.fromisoformat(all_dates[0])
        end   = datetime.date.fromisoformat(to_date) if to_date else today
        delta = (end - start).days + 1
        date_keys = [(start + datetime.timedelta(days=i)).isoformat() for i in range(delta)]
        label = f"Participation Standings — {start.strftime('%b %-d')} to {end.strftime('%b %-d, %Y')}"
        agg = scores_for_period(scores, date_keys)
        pages = format_period_leaderboard(label, agg, scores, date_keys, method="participation")
    elif period == "fun":
        # Post all fun categories that have data as a thread
        cat_filter = from_date.split(",") if from_date else None   # --from reused as comma-separated category list
        fun_pages = format_fun_all(scores, categories=cat_filter)
        if not fun_pages:
            logger.info("No fun stats available yet — keep playing!")
            return
        # Post each category's pages as its own mini-thread, all chained together
        root_ref = None
        prev_ref = None
        for cat, pages in fun_pages.items():
            for i, page in enumerate(pages):
                is_first = (root_ref is None)
                result = _post_and_print(
                    f"Fun — {cat}",
                    page,
                    session,
                    dry_run,
                    reply_to=prev_ref,
                    root_ref=root_ref,
                    pin=is_first,
                )
                if is_first:
                    root_ref = result
                prev_ref = result
        return
    elif period == "monthly":
        ref = datetime.date.fromisoformat(to_date) if to_date else today
        pages = format_monthly_leaderboard(ref, scores)
    elif period == "yearly":
        ref = datetime.date.fromisoformat(to_date) if to_date else today
        pages = format_yearly_leaderboard(ref, scores)
    elif period in _FUN_CATEGORIES:
        pages = format_fun_standings(period, scores)
        _post_standings(period, pages, session, dry_run, pin=False)
        return
    else:
        logger.error("Unknown period: %s", period)
        return

    _post_standings(period.capitalize(), pages, session, dry_run, pin=False)


def rebuild_records() -> None:
    """
    Recompute records.json from scratch using scores.json as the source of truth.
    Safe to run at any time — overwrites the existing records file.
    """
    scores = load_scores()
    if not scores:
        logger.info("No scores on record — records.json not written.")
        return

    all_dates = sorted(scores.keys())
    records: dict = {}

    # ── Daily player count ────────────────────────────────────────────────────
    best_day = max(all_dates, key=lambda d: len(scores[d]))
    records["daily_players"] = {"record": len(scores[best_day]), "date": best_day}

    # ── Per-score daily records ───────────────────────────────────────────────
    score_meta = {
        1: "aces", 2: "guess-2s", 3: "guess-3s",
        4: "guess-4s", 5: "guess-5s", DNF: "DNFs",
    }
    for sv in score_meta:
        best: dict[str, object] = {"record": 0, "date": ""}
        for d in all_dates:
            n = sum(1 for sc in scores[d].values() if sc == sv)
            if n > best["record"]:
                best = {"record": n, "date": d}
        if best["record"] > 0:
            records[f"daily_score_{sv}"] = best

    # ── New players per day ───────────────────────────────────────────────────
    new_players_per_day: dict[str, int] = {}
    known_before: set[str] = set()
    best_new: dict[str, object] = {"record": 0, "date": ""}
    for d in all_dates:
        today_handles = set(scores[d].keys())
        new_today = len(today_handles - known_before)
        new_players_per_day[d] = new_today
        if new_today > best_new["record"]:
            best_new = {"record": new_today, "date": d}
        known_before |= today_handles
    records["new_players"]     = new_players_per_day
    records["new_players_day"] = best_new

    # ── Weekly unique players ─────────────────────────────────────────────────
    best_week: dict[str, object] = {"record": 0, "date": ""}
    seen_mondays: set = set()
    for d in all_dates:
        ref    = datetime.date.fromisoformat(d)
        monday = ref - datetime.timedelta(days=ref.weekday())
        if monday in seen_mondays:
            continue
        seen_mondays.add(monday)
        keys    = [(monday + datetime.timedelta(days=i)).isoformat() for i in range(7)]
        players = {h for k in keys for h in scores.get(k, {})}
        if len(players) > best_week["record"]:
            best_week = {"record": len(players), "date": monday.isoformat()}
    records["weekly_players"] = best_week

    # ── Monthly unique players ────────────────────────────────────────────────
    best_month: dict[str, object] = {"record": 0, "date": ""}
    seen_months: set = set()
    for d in all_dates:
        month = d[:7]
        if month in seen_months:
            continue
        seen_months.add(month)
        players = {h for k, v in scores.items() if k.startswith(month) for h in v}
        if len(players) > best_month["record"]:
            best_month = {"record": len(players), "date": month}
    records["monthly_players"] = best_month

    save_records(records)
    logger.info("records.json rebuilt from %d days of scores.", len(all_dates))
    logger.info("  daily_players:   %s on %s", records["daily_players"]["record"], records["daily_players"]["date"])
    logger.info("  weekly_players:  %s w/c %s", records["weekly_players"]["record"], records["weekly_players"]["date"])
    logger.info("  monthly_players: %s in %s", records["monthly_players"]["record"], records["monthly_players"]["date"])
    logger.info("  new_players_day: %s on %s", records["new_players_day"]["record"], records["new_players_day"]["date"])


def announce(text: str, dry_run: bool = False) -> None:
    """Post a freeform announcement from the bot account."""
    if not text.strip():
        logger.error("Announce text is empty — nothing to post.")
        return
    logger.info("Logging in as @%s...", BOT_HANDLE)
    session = login(BOT_HANDLE, BOT_PASSWORD)
    logger.info("✓ Logged in.")
    _post_and_print("Announcement", text, session, dry_run, pin=False)


# ─── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=f"{GAME_NAME} Bluesky leaderboard bot")
    parser.add_argument(
        "--period",
        choices=["daily", "weekly", "monthly", "yearly", "all"],
        default="daily",
        help="Which leaderboard(s) to post (default: daily)",
    )
    parser.add_argument("--date", help="Reference date (YYYY-MM-DD). Defaults to today.")
    parser.add_argument("--dry-run", action="store_true", help="Print without posting.")
    parser.add_argument("--collect-only", action="store_true", help="Fetch & save only, no post.")
    parser.add_argument("--create-list", action="store_true", help="Create the Routlers list and print the URI to add to config.")
    parser.add_argument("--backfill", action="store_true",
        help="Fire reactions for all results already in scores.json. Run once after initial collect.")
    parser.add_argument(
        "--standings",
        choices=["weekly", "monthly", "yearly", "custom", "participation", "fun"]
                + list(_FUN_CATEGORIES.keys()),
        help="Post an ad-hoc standings. Use with --from / --to for custom ranges.",
    )
    parser.add_argument("--from", dest="from_date", help="Start date for custom standings (YYYY-MM-DD).")
    parser.add_argument("--to", dest="to_date", help="End date for custom standings (YYYY-MM-DD, default: today).")
    parser.add_argument("--rebuild-records", action="store_true",
        help="Recompute records.json from scratch using scores.json.")
    parser.add_argument("--announce", metavar="TEXT",
        help="Post a freeform announcement from the bot account.")
    parser.add_argument("--fun", action="store_true",
        help="Pick a random fun category and post it (ignores 14-day repeat filter).")
    args = parser.parse_args()
    setup_logging(dry_run=args.dry_run)

    if args.rebuild_records:
        rebuild_records()
    elif args.announce:
        announce(args.announce, dry_run=args.dry_run)
    elif args.fun:
        session = login(BOT_HANDLE, BOT_PASSWORD)
        scores  = load_scores()
        # Pick ignoring history so CLI always gets a result
        all_stats, _ = compute_fun_stats(scores)
        eligible = [
            cat for cat, (title, emoji, higher, fmt, min_val, desc)
            in _FUN_CATEGORIES.items()
            if [(h, v) for h, v in all_stats.get(cat, []) if v > min_val]
        ]
        if not eligible:
            logger.error("No fun categories have data yet.")
        else:
            chosen = random.choice(eligible)
            logger.info("🎲 Randomly picked: %s", chosen)
            post_fun_category(chosen, scores, session, dry_run=args.dry_run)
    elif args.create_list:
        session = login(BOT_HANDLE, BOT_PASSWORD)
        uri = create_list(
            session,
            name="Routlers",
            description="Players of Routle - TriMet on Bluesky 🚌",
        )
        rkey = uri.split("/")[-1]
        logger.info("✅ List created!")
        logger.info("   URI: %s", uri)
        logger.info("   Add this to config.py:")
        logger.info('   ROUTLERS_LIST_URI = "%s"', uri)
        logger.info("   View it at:")
        logger.info("   https://bsky.app/profile/%s/lists/%s", BOT_HANDLE, rkey)

    elif args.collect_only:
        session = login(BOT_HANDLE, BOT_PASSWORD)
        scores = load_scores()
        collect_results(session, scores, dry_run=False)
        save_scores(scores)
    elif args.backfill:
        backfill(dry_run=args.dry_run, date_filter=args.date)
    elif args.standings:
        run_standings(
            period=args.standings,
            from_date=args.from_date,
            to_date=args.to_date,
            dry_run=args.dry_run,
        )
    else:
        run(post_date=args.date, dry_run=args.dry_run, period=args.period)
