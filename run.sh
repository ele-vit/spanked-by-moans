#!/usr/bin/env bash
set -e

cleanup() {
    stty echoctl 2>/dev/null || true
    tput cnorm 2>/dev/null || true
    kill $PID 2>/dev/null || true
    kill $BANNER_PID 2>/dev/null || true
    rm -f /tmp/slap_ready
    echo ""
    exit 0
}

stty -echoctl 2>/dev/null || true
trap cleanup EXIT INT TERM

poetry install --no-root &>/dev/null 2>&1

rm -f /tmp/slap_ready
poetry run python main.py &
PID=$!

while [[ ! -f /tmp/slap_ready ]]; do sleep 0.1; done
rm -f /tmp/slap_ready

tput civis 2>/dev/null || true

poetry run python banner.py &
BANNER_PID=$!

wait $PID

kill $BANNER_PID 2>/dev/null || true
tput cnorm 2>/dev/null || true
