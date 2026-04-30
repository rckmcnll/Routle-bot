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

import time
import datetime
import logging
from config import LEADERBOARD_TIME, WEEKLY_LEADERBOARD_DAY, POLL_INTERVAL_MINUTES
from routle_bot import (
    login, poll, run, BOT_HANDLE, BOT_PASSWORD, setup_logging,
    load_scores, pick_fun_category, post_fun_category, FUN_STANDINGS_TIME,
)

logger = logging.getLogger(__name__)

TICK_SECONDS = 15   # Main loop resolution — how often we check timers


# ─── Leaderboard scheduler helpers ────────────────────────────────────────────

def _hhmm(dt: datetime.datetime) -> str:
    return dt.strftime("%H:%M")


def _should_fire(now: datetime.datetime, last_fired: dict, period: str) -> bool:
    """True if this period should post right now and hasn't already this window."""
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

    last_leaderboard_fired: dict[str, str] = {}
    last_poll_time: datetime.datetime | None = None
    poll_interval = datetime.timedelta(minutes=POLL_INTERVAL_MINUTES)

    while True:
        now = datetime.datetime.now()

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
            except Exception:
                logger.exception("Poll failed:")
                # Re-authenticate in case the session expired
                try:
                    session = login(BOT_HANDLE, BOT_PASSWORD)
                    logger.info("Re-authenticated.")
                except Exception:
                    logger.exception("Re-auth also failed. Will retry next tick.")

        # ── Fire leaderboards on schedule ──────────────────────────────────────
        for period in ("daily", "weekly", "monthly", "yearly"):
            if _should_fire(now, last_leaderboard_fired, period):
                ref = _ref_date_for(period, now)
                logger.info("🔔 Firing %s leaderboard (ref=%s)", period, ref)
                try:
                    run(post_date=ref, period=period)
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
            except Exception:
                logger.exception("Fun standings failed:")

        time.sleep(TICK_SECONDS)


if __name__ == "__main__":
    main()
