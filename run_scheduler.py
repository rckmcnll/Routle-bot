#!/usr/bin/env python3
"""
run_scheduler.py — runs two concurrent loops:

  POLLER  — checks the feed every POLL_INTERVAL_MINUTES and fires
             ace / score / DNF reaction replies immediately on new results.

  SCHEDULER — posts leaderboards on their cadence:
    • Daily   — every day at LEADERBOARD_TIME
    • Weekly  — at LEADERBOARD_TIME on WEEKLY_LEADERBOARD_DAY (default Sunday)
    • Monthly — at LEADERBOARD_TIME on the 1st of each month (posts prior month)
    • Yearly  — at LEADERBOARD_TIME on January 1st (posts prior year)

Run with:  python run_scheduler.py
Background: nohup python run_scheduler.py > bot.log 2>&1 &
"""

import os
import json
import time
import datetime
import logging
from config import LEADERBOARD_TIME, WEEKLY_LEADERBOARD_DAY, POLL_INTERVAL_MINUTES
from routle_bot import (
    login, poll, run, BOT_HANDLE, BOT_PASSWORD, setup_logging,
    load_scores, pick_fun_category, post_fun_category, FUN_STANDINGS_TIME,
    tick_challenges, CHALLENGE_REPORT_TIME,
)

logger = logging.getLogger(__name__)

TICK_SECONDS = 15   # Main loop resolution — how often we check timers

# Persists last-fired keys across restarts so catch-up logic works correctly.
SCHEDULER_STATE_FILE = "data/scheduler_state.json"


# ─── Scheduler state persistence ──────────────────────────────────────────────

def _load_state() -> dict:
    """Load last_fired dict from disk, or return empty dict if missing."""
    if os.path.exists(SCHEDULER_STATE_FILE):
        try:
            with open(SCHEDULER_STATE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_state(last_fired: dict) -> None:
    """Atomically persist last_fired dict to disk."""
    os.makedirs(os.path.dirname(SCHEDULER_STATE_FILE), exist_ok=True)
    _tmp = SCHEDULER_STATE_FILE + ".tmp"
    with open(_tmp, "w") as f:
        json.dump(last_fired, f, indent=2)
    os.replace(_tmp, SCHEDULER_STATE_FILE)


# ─── Leaderboard scheduler helpers ────────────────────────────────────────────

def _hhmm(dt: datetime.datetime) -> str:
    return dt.strftime("%H:%M")


def _should_fire(now: datetime.datetime, last_fired: dict, period: str) -> bool:
    """
    True if this period should post right now and hasn't already this window.
    Fires at the exact configured minute only.
    """
    if _hhmm(now) != LEADERBOARD_TIME:
        return False

    if period == "daily":
        key = now.strftime("%Y-%m-%d")
    elif period == "weekly":
        if now.weekday() != WEEKLY_LEADERBOARD_DAY:
            return False
        key = now.strftime("%Y-W%W")
    elif period == "monthly":
        if now.day != 1:
            return False
        key = now.strftime("%Y-%m")
    elif period == "yearly":
        if now.month != 1 or now.day != 1:
            return False
        key = str(now.year)
    else:
        return False

    if last_fired.get(period) == key:
        return False

    last_fired[period] = key
    return True


def _catchup_check(now: datetime.datetime, last_fired: dict) -> list[tuple[str, str]]:
    """
    On startup (or any tick), detect schedules that were missed while the bot
    was offline and return a list of (period, ref_date) tuples to fire.

    Rules:
      - Only fires if we are PAST the scheduled time today (not before it).
      - Only fires for the most recent missed window — does not replay history.
      - Respects day boundaries: if the missed window was yesterday (e.g. bot
        restarts just after midnight), uses yesterday's ref date.
      - Never fires a period that already has its current-window key recorded.
    """
    today     = now.date()
    hhmm_now  = _hhmm(now)
    to_fire   = []

    # ── Daily ─────────────────────────────────────────────────────────────────
    # Missed if: past LEADERBOARD_TIME today AND today's key not in last_fired.
    daily_key = today.isoformat()
    if hhmm_now > LEADERBOARD_TIME and last_fired.get("daily") != daily_key:
        to_fire.append(("daily", today.isoformat()))
        last_fired["daily"] = daily_key

    # ── Weekly ────────────────────────────────────────────────────────────────
    # Only catch up if today IS the weekly leaderboard day and we're past the
    # scheduled time, OR today is past that day and the most recent occurrence
    # hasn't been recorded yet. Never fires on a non-weekly day mid-week.
    days_since = (today.weekday() - WEEKLY_LEADERBOARD_DAY) % 7
    last_weekly_day = today - datetime.timedelta(days=days_since)
    weekly_key = last_weekly_day.strftime("%Y-W%W")
    if last_fired.get("weekly") != weekly_key:
        # Only catch up if the missed day was today (and past time) or yesterday.
        # Anything older than 1 day we skip — too stale to be useful.
        days_old = (today - last_weekly_day).days
        if days_old == 0 and hhmm_now > LEADERBOARD_TIME:
            to_fire.append(("weekly", last_weekly_day.isoformat()))
            last_fired["weekly"] = weekly_key
        elif days_old == 1:
            to_fire.append(("weekly", last_weekly_day.isoformat()))
            last_fired["weekly"] = weekly_key

    # ── Monthly ───────────────────────────────────────────────────────────────
    # Fires on the 1st; ref_date is the last day of the prior month.
    if today.day == 1 and hhmm_now > LEADERBOARD_TIME:
        monthly_key = today.strftime("%Y-%m")
        if last_fired.get("monthly") != monthly_key:
            ref = (today - datetime.timedelta(days=1)).isoformat()
            to_fire.append(("monthly", ref))
            last_fired["monthly"] = monthly_key
    elif today.day > 1:
        # If the 1st was missed entirely (bot was down all of the 1st),
        # fire now using the last day of last month as ref.
        first_this_month = today.replace(day=1)
        monthly_key = first_this_month.strftime("%Y-%m")
        last_of_prev = (first_this_month - datetime.timedelta(days=1)).isoformat()
        if last_fired.get("monthly") != monthly_key:
            to_fire.append(("monthly", last_of_prev))
            last_fired["monthly"] = monthly_key

    # ── Yearly ────────────────────────────────────────────────────────────────
    yearly_key = str(today.year)
    if today.month == 1 and today.day == 1 and hhmm_now > LEADERBOARD_TIME:
        if last_fired.get("yearly") != yearly_key:
            ref = datetime.date(today.year - 1, 12, 31).isoformat()
            to_fire.append(("yearly", ref))
            last_fired["yearly"] = yearly_key
    elif not (today.month == 1 and today.day == 1):
        # If Jan 1st was missed, fire once on the next startup.
        if last_fired.get("yearly") != yearly_key:
            ref = datetime.date(today.year - 1, 12, 31).isoformat()
            to_fire.append(("yearly", ref))
            last_fired["yearly"] = yearly_key

    # ── Fun standings ─────────────────────────────────────────────────────────
    if FUN_STANDINGS_TIME:
        fun_key = f"fun_{today.isoformat()}"
        if hhmm_now > FUN_STANDINGS_TIME and last_fired.get("fun") != fun_key:
            to_fire.append(("fun", today.isoformat()))
            last_fired["fun"] = fun_key

    # ── Challenge tick ────────────────────────────────────────────────────────
    if CHALLENGE_REPORT_TIME:
        ch_key = f"challenge_{today.isoformat()}"
        if hhmm_now > CHALLENGE_REPORT_TIME and last_fired.get("challenge") != ch_key:
            to_fire.append(("challenge", today.isoformat()))
            last_fired["challenge"] = ch_key

    return to_fire


def _ref_date_for(period: str, now: datetime.datetime) -> str:
    today = now.date()
    if period == "monthly":
        first = today.replace(day=1)
        return (first - datetime.timedelta(days=1)).isoformat()
    if period == "yearly":
        return datetime.date(today.year - 1, 12, 31).isoformat()
    return today.isoformat()


def _should_fire_fun(now: datetime.datetime, last_fired: dict) -> bool:
    """True if the fun standings should fire right now (once per day at FUN_STANDINGS_TIME)."""
    if _hhmm(now) != FUN_STANDINGS_TIME:
        return False
    key = f"fun_{now.strftime('%Y-%m-%d')}"
    if last_fired.get("fun") == key:
        return False
    last_fired["fun"] = key
    return True


def _should_fire_challenge(now: datetime.datetime, last_fired: dict) -> bool:
    """True once per day at CHALLENGE_REPORT_TIME (handles activate, daily DMs, finalize)."""
    if not CHALLENGE_REPORT_TIME:
        return False
    if _hhmm(now) != CHALLENGE_REPORT_TIME:
        return False
    key = f"challenge_{now.strftime('%Y-%m-%d')}"
    if last_fired.get("challenge") == key:
        return False
    last_fired["challenge"] = key
    return True


# ─── Main loop ─────────────────────────────────────────────────────────────────

def main():
    setup_logging()
    logger.info("🤖 Bot started")
    logger.info("   Polling feed every %s minute(s) for new results", POLL_INTERVAL_MINUTES)
    logger.info("   Daily leaderboard  → every day at %s", LEADERBOARD_TIME)
    logger.info("   Weekly leaderboard → %ss at %s",
                ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][WEEKLY_LEADERBOARD_DAY],
                LEADERBOARD_TIME)
    logger.info("   Monthly leaderboard → 1st of each month at %s (posts previous month)", LEADERBOARD_TIME)
    logger.info("   Yearly leaderboard  → Jan 1st at %s (posts previous year)", LEADERBOARD_TIME)
    if FUN_STANDINGS_TIME:
        logger.info("   Fun standings      → daily at %s (random category, no repeat within 14d)", FUN_STANDINGS_TIME)
    else:
        logger.info("   Fun standings      → disabled (set FUN_STANDINGS_TIME in config to enable)")

    session = login(BOT_HANDLE, BOT_PASSWORD)
    logger.info("✓ Logged in as @%s", BOT_HANDLE)

    # Load persisted state so catch-up logic has a reliable baseline
    last_leaderboard_fired: dict[str, str] = _load_state()
    last_poll_time:   datetime.datetime | None = None
    last_reauth_time: datetime.datetime        = datetime.datetime.now()
    poll_interval  = datetime.timedelta(minutes=POLL_INTERVAL_MINUTES)
    reauth_interval = datetime.timedelta(hours=6)   # proactive token refresh

    # ── Catch-up: fire any schedules missed while the bot was offline ──────────
    now = datetime.datetime.now()
    missed = _catchup_check(now, last_leaderboard_fired)
    if missed:
        logger.info("⏰ Catching up %d missed schedule(s):", len(missed))
        for period, ref in missed:
            logger.info("   → %s (ref=%s)", period, ref)
            try:
                if period == "fun":
                    scores = load_scores()
                    chosen = pick_fun_category(now, scores)
                    if chosen:
                        logger.info("🎲 Catch-up fun standings: %s", chosen)
                        post_fun_category(chosen, scores, session)
                elif period == "challenge":
                    tick_challenges(session)
                else:
                    run(post_date=ref, period=period)
            except Exception:
                logger.exception("Catch-up failed for %s (ref=%s):", period, ref)
        _save_state(last_leaderboard_fired)
    else:
        logger.info("✓ No missed schedules detected.")

    while True:
        now = datetime.datetime.now()

        # ── Proactive re-authentication every 6 hours ──────────────────────────
        if (now - last_reauth_time) >= reauth_interval:
            try:
                session = login(BOT_HANDLE, BOT_PASSWORD)
                last_reauth_time = now
                logger.info("🔑 Proactive re-auth complete.")
            except Exception:
                logger.exception("Proactive re-auth failed — will retry next tick.")

        # ── Poll for new results & fire reactions ──────────────────────────────
        if last_poll_time is None or (now - last_poll_time) >= poll_interval:
            last_poll_time = now
            logger.info("Polling feed...")
            try:
                new = poll(session=session)
                if new:
                    logger.info("%d new result(s) processed.", new)
                else:
                    logger.debug("No new results.")
            except Exception as exc:
                logger.exception("Poll failed:")
                # Re-authenticate — 400/401 indicate a stale token; other errors
                # may also be resolved by a fresh session.
                try:
                    session = login(BOT_HANDLE, BOT_PASSWORD)
                    last_reauth_time = now
                    logger.info("Re-authenticated after poll failure.")
                except Exception:
                    logger.exception("Re-auth also failed. Will retry next tick.")

        # ── Fire leaderboards on schedule ──────────────────────────────────────
        state_changed = False
        for period in ("daily", "weekly", "monthly", "yearly"):
            if _should_fire(now, last_leaderboard_fired, period):
                ref = _ref_date_for(period, now)
                logger.info("🔔 Firing %s leaderboard (ref=%s)", period, ref)
                try:
                    run(post_date=ref, period=period)
                    state_changed = True
                except Exception:
                    logger.exception("%s leaderboard failed:", period)

        # ── Fire random fun standings on schedule ──────────────────────────────
        if FUN_STANDINGS_TIME and _should_fire_fun(now, last_leaderboard_fired):
            try:
                scores = load_scores()
                chosen = pick_fun_category(now, scores)
                if chosen:
                    logger.info("🎲 Posting fun standings: %s", chosen)
                    post_fun_category(chosen, scores, session)
                state_changed = True
            except Exception:
                logger.exception("Fun standings failed:")

        # ── Tick challenge system (activate, daily DMs, finalize) ──────────────
        if _should_fire_challenge(now, last_leaderboard_fired):
            logger.info("⚔️  Ticking challenge system...")
            try:
                tick_challenges(session)
                state_changed = True
            except Exception:
                logger.exception("Challenge tick failed:")

        # Persist state after any schedule fires so restarts have a fresh baseline
        if state_changed:
            _save_state(last_leaderboard_fired)

        time.sleep(TICK_SECONDS)


if __name__ == "__main__":
    main()
