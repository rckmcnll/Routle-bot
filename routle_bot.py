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
import datetime
import requests
from collections import defaultdict
from config import (
    BOT_HANDLE, BOT_PASSWORD,
    FEED_CREATOR_HANDLE, FEED_SLUG,
    GAME_NAME, GAME_DOMAIN,
    MAX_SQUARES, LEADERBOARD_TIME,
    WEEKLY_LEADERBOARD_DAY,
    SCORES_FILE, ACES_FILE, STREAKS_FILE, OPTOUTS_FILE,
    ROUTLERS_LIST_URI, KNOWN_PLAYERS_FILE,
    STANDINGS_SPOTS,
)

# ─── Bluesky API helpers ───────────────────────────────────────────────────────

BASE_URL = "https://bsky.social/xrpc"


def login(handle: str, password: str) -> dict:
    resp = requests.post(
        f"{BASE_URL}/com.atproto.server.createSession",
        json={"identifier": handle, "password": password},
    )
    resp.raise_for_status()
    return resp.json()


def resolve_did(handle: str, token: str) -> str:
    resp = requests.get(
        f"{BASE_URL}/com.atproto.identity.resolveHandle",
        params={"handle": handle},
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
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
        resp = requests.get(
            f"{BASE_URL}/app.bsky.feed.getFeed",
            params=params,
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()
        data = resp.json()
        posts.extend(data.get("feed", []))
        if len(posts) >= limit or not data.get("cursor"):
            break
        cursor = data["cursor"]
    return posts[:limit]


def post_text(text: str, session: dict, reply_to: dict | None = None) -> dict:
    """
    Create a post. If reply_to is provided, post as a reply.
    reply_to should be {"uri": "at://...", "cid": "..."} from the parent post.
    """
    now = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    record = {
        "$type": "app.bsky.feed.post",
        "text": text,
        "createdAt": now,
        "langs": ["en-US"],
    }
    if reply_to:
        ref = {"uri": reply_to["uri"], "cid": reply_to["cid"]}
        record["reply"] = {"root": ref, "parent": ref}
    resp = requests.post(
        f"{BASE_URL}/com.atproto.repo.createRecord",
        json={
            "repo": session["did"],
            "collection": "app.bsky.feed.post",
            "record": record,
        },
        headers={"Authorization": f"Bearer {session['accessJwt']}"},
    )
    resp.raise_for_status()
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


def add_to_list(session: dict, list_uri: str, member_did: str) -> bool:
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
    with open(KNOWN_PLAYERS_FILE, "w") as f:
        json.dump(known, f, indent=2, sort_keys=True)


def maybe_add_to_routlers(session: dict, handle: str, did: str,
                           known: dict, optouts: set, dry_run: bool = False):
    """
    Add a player to the Routlers list if they're new and haven't opted out.
    Updates `known` in-place.
    """
    if not ROUTLERS_LIST_URI:
        return
    if handle in known:
        return
    if handle in optouts:
        print(f"  (skipping list add — @{handle} opted out)")
        known[handle] = did   # still record as known so we don't check again
        return

    print(f"  ➕ Adding @{handle} to Routlers list")
    if not dry_run:
        try:
            add_to_list(session, ROUTLERS_LIST_URI, did)
        except Exception as e:
            print(f"    ⚠ Could not add @{handle} to list: {e}")
            return
    known[handle] = did


# ─── Score parsing ─────────────────────────────────────────────────────────────

# Real post format (newline-separated):
#   Routle - TriMet
#   04/08/2026
#   🟩 ⬛ ⬛ ⬛ ⬛
#   www.routle.city/trimet
RESULT_RE = re.compile(
    rf"{re.escape(GAME_NAME)}[^\n]*\n"
    r"(\d{2}/\d{2}/\d{4})\n"
    r"([\U0001F7E9\u2B1B\U0001F7E8\U0001F7E5\U0001F7EA\s]+)",
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
    with open(SCORES_FILE, "w") as f:
        json.dump(scores, f, indent=2, sort_keys=True)


# ─── Score aggregation ─────────────────────────────────────────────────────────

def scores_for_period(scores: dict, date_keys: list[str]) -> dict:
    """
    Aggregate daily scores across a period.
    score = guess number (lower is better); DNF = MAX_SQUARES+1.
    Returns {handle: {"total": int, "days": int, "avg": float, "best": int, "dnf": int}}.
    """
    agg: dict[str, dict] = defaultdict(
        lambda: {"total": 0, "days": 0, "best": DNF, "dnf": 0}
    )
    for dk in date_keys:
        for handle, score in scores.get(dk, {}).items():
            agg[handle]["total"] += score
            agg[handle]["days"] += 1
            agg[handle]["best"] = min(agg[handle]["best"], score)   # lower = better
            if score == DNF:
                agg[handle]["dnf"] += 1
    for handle in agg:
        d = agg[handle]["days"]
        agg[handle]["avg"] = round(agg[handle]["total"] / d, 2) if d else 0.0
    return dict(agg)


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


BSKY_LIMIT = 300  # Bluesky grapheme limit per post


def _graphemes(s: str) -> int:
    """Count graphemes (one per code point — accurate for our emoji/ASCII content)."""
    return len(s)


def format_daily_leaderboard(date_str: str, day_scores: dict) -> str:
    if not day_scores:
        return f"No {GAME_NAME} results for {date_str} yet!"

    ranked = sorted(day_scores.items(), key=lambda x: (x[1], x[0]))
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
        player_lines.append(f"{_grid_display(score)} {_medal(rank)} @{_short_handle(handle)}")

    omitted = 0
    while player_lines:
        omit_note = f"\n  …and {omitted} more" if omitted else ""
        candidate = header + "\n" + "\n".join(player_lines) + omit_note + footer
        if _graphemes(candidate) <= BSKY_LIMIT:
            return candidate
        player_lines.pop()
        omitted += 1

    return header + footer  # extreme fallback


def format_period_leaderboard(title: str, agg: dict, scores: dict, date_keys: list[str]) -> list[str]:
    """
    Format a period standings post, split into pages of STANDINGS_PAGE_SIZE players.
    Returns a list of strings — first is the main post, rest are continuation replies.
    """
    if not agg:
        return [f"No {GAME_NAME} results for {title} yet!"]

    all_ranked = sorted(
        agg.items(),
        key=lambda x: (x[1]["total"], x[1]["dnf"], x[1]["avg"], x[0]),
    )

    # Truncate to configured number of spots (0 or None = all players)
    total_players = len(all_ranked)
    ranked = all_ranked if not STANDINGS_SPOTS else all_ranked[:STANDINGS_SPOTS]

    active_days = sum(1 for dk in date_keys if scores.get(dk))
    total_days = len(date_keys)
    n = len(ranked)
    shown_note = f" (top {n} of {total_players})" if total_players > n else ""
    footer = f"\n{total_players} player{'s' if total_players != 1 else ''} · {active_days}/{total_days} days played{shown_note}"

    # Build all player rows with rank
    # Use short handle (first segment) and dynamic-width name column for alignment
    short_names = [_short_handle(h) for h, _ in ranked]
    name_w = max((len(n) for n in short_names), default=8)

    player_rows = []
    prev_total = None
    rank = 0
    for i, ((handle, s), short) in enumerate(zip(ranked, short_names)):
        if s["total"] != prev_total:
            rank = i + 1
            prev_total = s["total"]
        dnf_str  = f" {s['dnf']}\u2717" if s["dnf"] else ""   # N✗
        ace_str  = " \u2b50" if s["best"] == 1 else ""         # ⭐
        player_rows.append(
            f"{_medal(rank)} {short:<{name_w}}  "
            f"{s['total']:>3}🟩  "
            f"{s['days']}/{active_days}d"
            f"{dnf_str}{ace_str}"
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
    return format_period_leaderboard(label, scores_for_period(scores, keys), scores, keys)


def format_monthly_leaderboard(ref: datetime.date, scores: dict) -> list[str]:
    keys = date_keys_for_month(ref)
    label = f"Monthly Standings — {ref.strftime('%B %Y')}"
    return format_period_leaderboard(label, scores_for_period(scores, keys), scores, keys)


def format_yearly_leaderboard(ref: datetime.date, scores: dict) -> list[str]:
    keys = date_keys_for_year(ref)
    label = f"Yearly Standings — {ref.year}"
    return format_period_leaderboard(label, scores_for_period(scores, keys), scores, keys)


# ─── Ace tracking ─────────────────────────────────────────────────────────────

def load_aces() -> dict:
    """Load ace counts. Structure: {"handle": int}"""
    if os.path.exists(ACES_FILE):
        with open(ACES_FILE) as f:
            return json.load(f)
    return {}


def save_aces(aces: dict):
    with open(ACES_FILE, "w") as f:
        json.dump(aces, f, indent=2, sort_keys=True)


# ─── Streak tracking ──────────────────────────────────────────────────────────

def load_streaks() -> dict:
    """Load streaks. Structure: {"handle": {"current": N, "best": N, "last_date": "YYYY-MM-DD"}}"""
    if os.path.exists(STREAKS_FILE):
        with open(STREAKS_FILE) as f:
            return json.load(f)
    return {}


def save_streaks(streaks: dict):
    with open(STREAKS_FILE, "w") as f:
        json.dump(streaks, f, indent=2, sort_keys=True)


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
    with open(OPTOUTS_FILE, "w") as f:
        json.dump(sorted(optouts), f, indent=2)


def check_dms_for_optouts(session: dict, dry_run: bool = False) -> list[str]:
    """
    Poll the bot's DM inbox for messages containing STOP.
    Adds senders to the optout list and sends a confirmation DM.
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
        print(f"  ⚠ Could not fetch DMs: {e}")
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

        is_stop  = "STOP"  in msg_text
        is_start = "START" in msg_text

        if not is_stop and not is_start:
            continue

        # Find the sender (the non-bot member)
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
                print(f"    ⚠ Could not send DM: {e}")

        if is_stop and sender_handle not in optouts:
            print(f"  🛑 Opt-out received from @{sender_handle}")
            optouts.add(sender_handle)
            newly_opted_out.append(sender_handle)
            if not dry_run:
                _send_dm(
                    "You will no longer receive replies to your "
                    "Routle - TriMet posts. "
                    "DM START anytime to opt back in. 🚌"
                )

        elif is_start and sender_handle in optouts:
            print(f"  ✅ Opt-in received from @{sender_handle}")
            optouts.discard(sender_handle)
            if not dry_run:
                _send_dm("Welcome back! Routle bot replies are back on for you. 🟩")

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
        print(f"  ⚠ Could not send DM to @{to_handle}: {e}")
        return False


def record_ace(aces: dict, handle: str) -> int:
    """Increment ace count for handle, return new total."""
    aces[handle] = aces.get(handle, 0) + 1
    return aces[handle]


# ─── Reaction messages ─────────────────────────────────────────────────────────

import random

# Messages are defined in config.py — edit them there.
# Templates support: {handle}, {aces_line} (ace messages) or {handle} (DNF messages).
# ACE_COUNT_LINES support: {aces}

def _ace_count_line(aces: int) -> str:
    from config import ACE_COUNT_LINES
    return random.choice(ACE_COUNT_LINES).format(aces=aces)


def _streak_suffix(current_streak: int, is_new_best: bool) -> str:
    """Return a streak note to append to reactions, or empty string."""
    if current_streak >= 2 and is_new_best:
        return f" 🔥 New best streak: {current_streak} days in a row!"
    if current_streak >= 7:
        return f" 🔥 {current_streak}-day streak!!"
    if current_streak >= 3:
        return f" 🔥 {current_streak} days in a row!"
    if current_streak == 2:
        return " 🔥 2 days running!"
    return ""


def make_ace_post(handle: str, display_name: str, ace_count: int,
                  current_streak: int = 0, is_new_best: bool = False) -> str:
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
    print(f"→ Fetching custom feed: {feed_uri}")
    feed = get_custom_feed(feed_uri, token, limit=100)
    print(f"  Retrieved {len(feed)} post(s).")

    aces = load_aces()
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
            print(f"  ✓ {author}: {score}/{MAX_SQUARES} on {date_str}")

            # Add to Routlers list if new player
            maybe_add_to_routlers(session, author, author_did, known, optouts, dry_run)

            # Update streak
            current_streak, best_streak, is_new_best = update_streak(streaks, author, date_str)

            # Skip reactions for opted-out users
            if author in optouts:
                print(f"  (skipping reaction — @{author} opted out)")
                continue

            if score == 1:
                # Ace! Update count and post congratulations as a reply
                ace_count = record_ace(aces, author)
                reaction = make_ace_post(author, display_name, ace_count, current_streak, is_new_best)
                _post_and_print(f"Ace reaction for @{author}", reaction, session, dry_run, reply_to=post_ref)

            elif score == DNF:
                # Missed every stop — commiserate as a reply
                reaction = make_dnf_post(author, display_name)
                _post_and_print(f"DNF reaction for @{author}", reaction, session, dry_run, reply_to=post_ref)

            elif 2 <= score <= MAX_SQUARES:
                # Score-specific reaction for guesses 2–5
                reaction = make_score_post(author, display_name, score, current_streak, is_new_best)
                if reaction:
                    _post_and_print(f"Score {score} reaction for @{author}", reaction, session, dry_run, reply_to=post_ref)

    save_aces(aces)
    save_streaks(streaks)
    save_known_players(known)
    print(f"  {new_entries} new result(s) recorded.")
    return new_entries


# ─── Posting helpers ───────────────────────────────────────────────────────────

OPTOUT_TAG = "\n\nDM 'stop' to discontinue replies"


def _post_and_print(label: str, text: str, session: dict, dry_run: bool,
                    reply_to: dict | None = None) -> dict | None:
    """Post text and print to log. Returns {"uri": ..., "cid": ...} on success, else None."""
    # Append opt-out instructions to reaction replies (not leaderboard posts)
    if reply_to:
        text = text + OPTOUT_TAG
    print(f"\n── {label} ──\n{text}\n" + "─" * 40)
    if not dry_run:
        result = post_text(text, session, reply_to=reply_to)
        uri = result.get("uri", "")
        cid = result.get("cid", "")
        print(f"✅ Posted! URI: {uri}")
        # DM the notify handle when a top-level leaderboard post goes out
        if not reply_to:
            from config import NOTIFY_HANDLE
            if NOTIFY_HANDLE:
                rkey = uri.split("/")[-1] if uri else ""
                post_url = f"https://bsky.app/profile/{BOT_HANDLE}/post/{rkey}" if rkey else ""
                dm_text = f"📋 {label} standings posted!"
                if post_url:
                    dm_text += f"\n{post_url}"
                send_dm(session, NOTIFY_HANDLE, dm_text)
                print(f"  📨 Notified @{NOTIFY_HANDLE}")
        return {"uri": uri, "cid": cid}
    else:
        print("  (dry run — not posted)")
        return None


def _post_standings(label: str, pages: list[str], session: dict, dry_run: bool):
    """
    Post a period standings. First page is a top-level post;
    subsequent pages are threaded as replies, each replying to the previous.
    """
    if not pages:
        return
    result = _post_and_print(label, pages[0], session, dry_run)
    if len(pages) == 1:
        return
    # Thread continuation pages as replies to the previous post
    prev_ref = result  # {"uri": ..., "cid": ...} or None in dry_run
    for i, page in enumerate(pages[1:], 2):
        cont_label = f"{label} cont. ({i}/{len(pages)})"
        prev_ref = _post_and_print(cont_label, page, session, dry_run, reply_to=prev_ref)


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
    print(f"🤖 {GAME_NAME} Bot — period={period}  ref={ref}")
    print(f"→ Logging in as @{BOT_HANDLE}...")
    session = login(BOT_HANDLE, BOT_PASSWORD)
    print("  ✓ Logged in.")

    scores = load_scores()
    collect_results(session, scores, dry_run=dry_run)
    save_scores(scores)

    if period in ("daily", "all"):
        _post_and_print("Daily", format_daily_leaderboard(ref.isoformat(), scores.get(ref.isoformat(), {})), session, dry_run)

    for label, pages in [
        ("Weekly",  format_weekly_leaderboard(ref, scores)),
        ("Monthly", format_monthly_leaderboard(ref, scores)),
        ("Yearly",  format_yearly_leaderboard(ref, scores)),
    ]:
        if period not in (label.lower(), "all"):
            continue
        _post_standings(label, pages, session, dry_run)


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
        print("  No scores on record — nothing to backfill.")
        return 0

    token = session["accessJwt"]
    feed_uri = build_feed_uri(FEED_CREATOR_HANDLE, FEED_SLUG, token)
    print(f"→ Fetching feed for backfill: {feed_uri}")
    feed = get_custom_feed(feed_uri, token, limit=100)
    print(f"  Retrieved {len(feed)} post(s).")

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
        print(f"  ↺ Backfilling {author}: {score}/{MAX_SQUARES} on {date_str}")

        if score == 1:
            ace_count = record_ace(aces, author)
            reaction = make_ace_post(author, display_name, ace_count)
            _post_and_print(f"Ace backfill for @{author}", reaction, session, dry_run, reply_to=post_ref)
            fired += 1

        elif score == DNF:
            reaction = make_dnf_post(author, display_name)
            _post_and_print(f"DNF backfill for @{author}", reaction, session, dry_run, reply_to=post_ref)
            fired += 1

        elif 2 <= score <= MAX_SQUARES:
            reaction = make_score_post(author, display_name, score)
            if reaction:
                _post_and_print(f"Score {score} backfill for @{author}", reaction, session, dry_run, reply_to=post_ref)
                fired += 1

    save_aces(aces)
    print(f"  {fired} reaction(s) fired.")
    return fired


def poll(session: dict | None = None, dry_run: bool = False) -> int:
    """
    Lightweight poll: fetch the feed, record new results, fire reactions,
    and check DMs for STOP/START opt-out requests.
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

    period    : "weekly" | "monthly" | "yearly" | "custom"
    from_date : "YYYY-MM-DD" start of custom range (required if period="custom")
    to_date   : "YYYY-MM-DD" end of custom range (defaults to today if period="custom")
    """
    print(f"→ Logging in as @{BOT_HANDLE}...")
    session = login(BOT_HANDLE, BOT_PASSWORD)
    print("  ✓ Logged in.")
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
                print("❌ No scores on record yet.")
                return
            start = datetime.date.fromisoformat(all_dates[0])
            print(f"  No --from date given — using earliest recorded date: {start}")
        delta = (end - start).days + 1
        date_keys = [(start + datetime.timedelta(days=i)).isoformat() for i in range(delta)]
        label = f"Standings — {start.strftime('%b %-d')} to {end.strftime('%b %-d, %Y')}"
        agg = scores_for_period(scores, date_keys)
        pages = format_period_leaderboard(label, agg, scores, date_keys)
    elif period == "weekly":
        ref = datetime.date.fromisoformat(to_date) if to_date else today
        pages = format_weekly_leaderboard(ref, scores)
    elif period == "monthly":
        ref = datetime.date.fromisoformat(to_date) if to_date else today
        pages = format_monthly_leaderboard(ref, scores)
    elif period == "yearly":
        ref = datetime.date.fromisoformat(to_date) if to_date else today
        pages = format_yearly_leaderboard(ref, scores)
    else:
        print(f"❌ Unknown period: {period}")
        return

    _post_standings(period.capitalize(), pages, session, dry_run)


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
        choices=["weekly", "monthly", "yearly", "custom"],
        help="Post an ad-hoc standings. Use with --from / --to for custom ranges.",
    )
    parser.add_argument("--from", dest="from_date", help="Start date for custom standings (YYYY-MM-DD).")
    parser.add_argument("--to", dest="to_date", help="End date for custom standings (YYYY-MM-DD, default: today).")
    args = parser.parse_args()

    if args.create_list:
        session = login(BOT_HANDLE, BOT_PASSWORD)
        uri = create_list(
            session,
            name="Routlers",
            description="Players of Routle - TriMet on Bluesky 🚌",
        )
        print(f"\n✅ List created!")
        print(f"   URI: {uri}")
        print(f"\n   Add this to config.py:")
        print(f'   ROUTLERS_LIST_URI = "{uri}"')
        print(f"\n   View it at:")
        rkey = uri.split("/")[-1]
        print(f"   https://bsky.app/profile/{BOT_HANDLE}/lists/{rkey}")

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
