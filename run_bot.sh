#!/usr/bin/env bash
# ─── Routle Leaderboard Bot Runner ────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR="$SCRIPT_DIR/.venv"
LOG_FILE="$SCRIPT_DIR/$(python3 -c "import sys; sys.path.insert(0,'$SCRIPT_DIR'); import config; print(getattr(config,'LOG_FILE','logs/bot.log'))" 2>/dev/null || echo "logs/bot.log")"
PID_FILE="$SCRIPT_DIR/bot.pid"

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "${CYAN}▸${RESET} $*"; }
success() { echo -e "${GREEN}✓${RESET} $*"; }
warn()    { echo -e "${YELLOW}⚠${RESET}  $*"; }
error()   { echo -e "${RED}✗${RESET} $*" >&2; }
header()  { echo -e "\n${BOLD}$*${RESET}"; }

# ── Helpers ───────────────────────────────────────────────────────────────────
ensure_venv() {
    if [[ ! -d "$VENV_DIR" ]]; then
        info "Creating Python virtual environment..."
        python3 -m venv "$VENV_DIR"
        success "Virtual environment created at .venv/"
    fi
    # shellcheck source=/dev/null
    source "$VENV_DIR/bin/activate"
}

install_deps() {
    ensure_venv
    info "Installing dependencies..."
    pip install --quiet --upgrade pip
    pip install --quiet requests
    success "Dependencies installed."
    _setup_dirs
}

_setup_dirs() {
    info "Creating data/ and logs/ directories..."
    mkdir -p "$SCRIPT_DIR/data" "$SCRIPT_DIR/logs"
    success "Directories ready."

    # Initialise empty data files so the bot starts cleanly
    local data="$SCRIPT_DIR/data"
    for f in scores.json aces.json streaks.json optouts.json               known_players.json dnf_counts.json records.json               fun_history.json challenges.json reactions.json; do
        if [[ ! -f "$data/$f" ]]; then
            # optouts and reactions are arrays; everything else is an object
            if [[ "$f" == "optouts.json" || "$f" == "reactions.json" ]]; then
                echo "[]" > "$data/$f"
            else
                echo "{}" > "$data/$f"
            fi
            info "Created $data/$f"
        fi
    done

    # Pre-populate scheduler_state.json with today'''s keys so no schedules
    # fire immediately on first start (catch-up would otherwise trigger all of them).
    local state_file="$data/scheduler_state.json"
    if [[ ! -f "$state_file" ]]; then
        info "Writing initial scheduler state..."
        python3 - << PYEOF
import json, datetime, sys
sys.path.insert(0, '$SCRIPT_DIR')
try:
    import config as _c
    leaderboard_day = getattr(_c, 'WEEKLY_LEADERBOARD_DAY', 6)
    fun_time        = getattr(_c, 'FUN_STANDINGS_TIME', '')
    challenge_time  = getattr(_c, 'CHALLENGE_REPORT_TIME', None)
except Exception:
    leaderboard_day = 6
    fun_time        = ''
    challenge_time  = None

today = datetime.date.today()

# Compute the most recent occurrence of the weekly leaderboard day
days_since = (today.weekday() - leaderboard_day) % 7
last_weekly = today - datetime.timedelta(days=days_since)
weekly_key  = last_weekly.strftime('%Y-W%W')

state = {
    'daily':   today.isoformat(),
    'weekly':  weekly_key,
    'monthly': today.strftime('%Y-%m'),
    'yearly':  str(today.year),
}
if fun_time:
    state['fun'] = f'fun_{today.isoformat()}'
if challenge_time:
    state['challenge'] = f'challenge_{today.isoformat()}'

with open('$state_file', 'w') as f:
    json.dump(state, f, indent=2)
print(json.dumps(state, indent=2))
PYEOF
        success "Scheduler state initialised — no catch-up will fire on first start."
    else
        info "Scheduler state already exists — skipping."
    fi
}

check_config() {
    if [[ ! -f "$SCRIPT_DIR/config.py" ]]; then
        error "config.py not found!"
        echo "  Copy and edit the example config before running:"
        echo "    cp config.example.py config.py && nano config.py"
        exit 1
    fi
    # Warn if still using placeholder credentials
    if grep -q "your-bot.bsky.social\|your-app-password" "$SCRIPT_DIR/config.py"; then
        warn "config.py still contains placeholder values — please edit it first."
        exit 1
    fi
}

is_running() {
    [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null
}

# ── Commands ──────────────────────────────────────────────────────────────────

cmd_run() {
    header "🤖 Routle Bot — run once"
    check_config
    ensure_venv
    # Pass --period and --date if provided, e.g.: ./run_bot.sh run --period weekly
    python3 routle_bot.py "$@"
}

cmd_dry_run() {
    header "🤖 Routle Bot — dry run (no posting)"
    check_config
    ensure_venv
    python3 routle_bot.py --dry-run "$@"
}

cmd_collect() {
    header "🤖 Routle Bot — collect results only"
    check_config
    ensure_venv
    python3 routle_bot.py --collect-only
}

cmd_standings() {
    header "🤖 Routle Bot — ad-hoc standings"
    check_config
    ensure_venv
    # Examples:
    #   ./run_bot.sh standings weekly --dry-run
    #   ./run_bot.sh standings monthly
    #   ./run_bot.sh standings participation
    #   ./run_bot.sh standings fun
    #   ./run_bot.sh standings dow_tuesday
    #   ./run_bot.sh standings yahtzee
    #   ./run_bot.sh standings custom --from 2026-04-01 --to 2026-04-09
    PERIOD="${1:-weekly}"; shift || true
    python3 routle_bot.py --standings "$PERIOD" "$@"
}

cmd_create_list() {
    header "📋 Creating Routlers list"
    check_config
    ensure_venv
    python3 routle_bot.py --create-list
}

cmd_backfill() {
    header "🤖 Routle Bot — backfill reactions"
    check_config
    ensure_venv
    # Pass --date YYYY-MM-DD to limit to a specific day, e.g.:
    #   ./run_bot.sh backfill --date 2026-04-08
    python3 routle_bot.py --backfill "$@"
}

cmd_rebuild_records() {
    header "📊 Rebuilding records.json from scores.json"
    check_config
    ensure_venv
    python3 routle_bot.py --rebuild-records
}

cmd_fun() {
    header "🎲 Routle Bot — random fun report"
    check_config
    ensure_venv
    # Pick and post a random fun category (ignores 14-day repeat filter)
    # Usage:
    #   ./run_bot.sh fun            # pick and post
    #   ./run_bot.sh fun --dry-run  # pick and preview without posting
    DRY=""
    if [[ "${1:-}" == "--dry-run" ]]; then
        DRY="--dry-run"
    fi
    python3 routle_bot.py --fun $DRY
}

cmd_announce() {
    header "📣 Posting announcement"
    check_config
    ensure_venv
    # Usage: ./run_bot.sh announce "Your message here"
    #        ./run_bot.sh announce --dry-run "Preview only"
    DRY=""
    if [[ "${1:-}" == "--dry-run" ]]; then
        DRY="--dry-run"
        shift
    fi
    if [[ -z "${1:-}" ]]; then
        error "Usage: ./run_bot.sh announce [--dry-run] \"Your message\""
        exit 1
    fi
    python3 routle_bot.py --announce "$1" $DRY
}

cmd_start() {
    header "🤖 Routle Bot — starting scheduler"
    check_config

    if is_running; then
        warn "Bot is already running (PID $(cat "$PID_FILE"))."
        echo "  Use './run_bot.sh stop' to stop it first."
        exit 1
    fi

    ensure_venv
    _setup_dirs
    info "Starting scheduler in the background..."
    nohup python3 run_scheduler.py > /dev/null 2>&1 &
    echo $! > "$PID_FILE"
    success "Bot started (PID $!). Logs → bot.log"
    echo -e "  ${CYAN}tail -f bot.log${RESET}   to follow logs"
    echo -e "  ${CYAN}./run_bot.sh stop${RESET} to stop"
}

cmd_stop() {
    header "🛑 Stopping Routle Bot"
    if ! is_running; then
        warn "Bot is not running (no PID file or process not found)."
        rm -f "$PID_FILE"
        exit 0
    fi
    PID=$(cat "$PID_FILE")
    kill "$PID"
    rm -f "$PID_FILE"
    success "Bot stopped (was PID $PID)."
}

cmd_status() {
    header "📊 Routle Bot Status"
    if is_running; then
        success "Running (PID $(cat "$PID_FILE"))"
    else
        warn "Not running."
        rm -f "$PID_FILE" 2>/dev/null || true
    fi

    if [[ -f "$SCRIPT_DIR/scores.json" ]]; then
        DAYS=$(python3 -c "import json; d=json.load(open('scores.json')); print(len(d))" 2>/dev/null || echo "?")
        TOTAL=$(python3 -c "import json; d=json.load(open('scores.json')); print(sum(len(v) for v in d.values()))" 2>/dev/null || echo "?")
        info "Scores file: $DAYS day(s), $TOTAL total result(s) recorded."
    else
        info "No scores file yet."
    fi

    if [[ -f "$LOG_FILE" ]]; then
        info "Last 5 log lines:"
        tail -5 "$LOG_FILE" | sed 's/^/    /'
    fi
}

cmd_logs() {
    if [[ ! -f "$LOG_FILE" ]]; then
        warn "No log file found yet."
        exit 0
    fi
    tail -f "$LOG_FILE"
}

cmd_install() {
    header "📦 Installing dependencies"
    install_deps
}

cmd_help() {
    echo -e "${BOLD}Usage:${RESET} ./run_bot.sh <command> [options]\n"
    echo -e "${BOLD}Commands:${RESET}"
    printf "  ${CYAN}%-18s${RESET} %s\n" \
        "run"             "Fetch results + post today's leaderboard (once)" \
        "dry-run"         "Fetch results + print leaderboard (don't post)" \
        "collect"         "Fetch & save results only, no leaderboard post" \
        "backfill"        "Fire reactions for all results already in scores.json" \
        "standings"       "Post an ad-hoc standings (weekly/monthly/yearly/custom)" \
        "create-list"     "Create the Routlers Bluesky list and print URI for config" \
        "rebuild-records" "Recompute records.json from scratch using scores.json" \
        "fun"             "Pick and post a random fun report (--dry-run to preview)" \
        "announce"        "Post a freeform message from the bot account" \
        "start"           "Start the daily scheduler in the background" \
        "stop"            "Stop the background scheduler" \
        "status"          "Show whether the bot is running + score stats" \
        "logs"            "Tail the bot log (Ctrl+C to exit)" \
        "install"         "Set up virtual environment + install dependencies" \
        "help"            "Show this help message"
    echo ""
    echo -e "${BOLD}Examples:${RESET}"
    echo "  ./run_bot.sh dry-run --period all              # Preview all leaderboards"
    echo "  ./run_bot.sh run --period weekly               # Post weekly leaderboard"
    echo "  ./run_bot.sh run --date 2026-04-07             # Post for a specific date"
    echo "  ./run_bot.sh standings weekly --dry-run        # Preview weekly standings"
    echo "  ./run_bot.sh standings participation           # Post participation standings"
    echo "  ./run_bot.sh standings fun                     # Post all fun categories"
    echo "  ./run_bot.sh standings fun --dry-run           # Preview fun standings"
    echo "  ./run_bot.sh standings dow_tuesday             # Post Tuesday standings only"
    echo "  ./run_bot.sh standings yahtzee                 # Post Yahtzee Club only"
    echo "  ./run_bot.sh fun                               # Post random fun report"
    echo "  ./run_bot.sh fun --dry-run                    # Preview random fun report"
    echo "  ./run_bot.sh announce \"Bot back online!\"       # Post announcement"
    echo "  ./run_bot.sh announce --dry-run \"Test message\" # Preview announcement"
    echo "  ./run_bot.sh start                             # Run on autopilot"
    echo "  ./run_bot.sh logs                              # Watch live output"
}

# ── Dispatch ──────────────────────────────────────────────────────────────────
COMMAND="${1:-help}"
shift || true   # remove command from args so "$@" passes remaining flags

case "$COMMAND" in
    run)             cmd_run "$@" ;;
    dry-run)         cmd_dry_run "$@" ;;
    collect)         cmd_collect ;;
    backfill)        cmd_backfill "$@" ;;
    standings)       cmd_standings "$@" ;;
    create-list)     cmd_create_list ;;
    rebuild-records) cmd_rebuild_records ;;
    announce)        cmd_announce "$@" ;;
    fun)             cmd_fun "$@" ;;
    start)           cmd_start ;;
    stop)            cmd_stop ;;
    status)          cmd_status ;;
    logs)            cmd_logs ;;
    install)         cmd_install ;;
    help|--help|-h)  cmd_help ;;
    *)
        error "Unknown command: '$COMMAND'"
        echo ""
        cmd_help
        exit 1
        ;;
esac
