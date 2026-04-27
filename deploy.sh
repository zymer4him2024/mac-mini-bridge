#!/usr/bin/env bash
# Deploy bridge.py changes from MacBook -> Mac Mini and reload the LaunchAgent.
# Usage:  ./deploy.sh           # commit + push (if needed) + remote pull + reload
#         ./deploy.sh --no-pull # remote reload only (when code is already in place)
#
# Assumes:
#   - origin is github.com/zymer4him2024/mac-mini-bridge (public; pull works without auth)
#   - Mac Mini is reachable as MAC_MINI_HOST (default below)
#   - Mac Mini has the repo at MAC_MINI_REPO (default below)
#   - LaunchAgent label is com.shawn.telegram-bridge

set -euo pipefail

MAC_MINI_HOST="${MAC_MINI_HOST:-shawnlee@100.86.233.125}"
MAC_MINI_REPO="${MAC_MINI_REPO:-/Users/shawnlee/telegram-bridge}"
LAUNCH_PLIST="${LAUNCH_PLIST:-\$HOME/Library/LaunchAgents/com.shawn.telegram-bridge.plist}"
SKIP_PULL=false

for arg in "$@"; do
  case "$arg" in
    --no-pull) SKIP_PULL=true ;;
    *) echo "unknown arg: $arg"; exit 2 ;;
  esac
done

if [ "$SKIP_PULL" = false ]; then
  echo "==> local: checking for uncommitted changes"
  if ! git diff-index --quiet HEAD --; then
    echo "    uncommitted changes present. Commit/push manually before deploying."
    git status --short
    exit 1
  fi

  echo "==> local: pushing to origin"
  git push

  echo "==> ${MAC_MINI_HOST}: git pull"
  ssh "$MAC_MINI_HOST" "cd '$MAC_MINI_REPO' && git pull --ff-only"
fi

echo "==> ${MAC_MINI_HOST}: reload LaunchAgent"
ssh "$MAC_MINI_HOST" "launchctl unload $LAUNCH_PLIST 2>/dev/null || true; launchctl load $LAUNCH_PLIST"

echo "==> ${MAC_MINI_HOST}: verify process is running"
ssh "$MAC_MINI_HOST" "launchctl list | grep com.shawn.telegram-bridge || (echo 'LaunchAgent not running' && exit 1)"

echo "==> done"
