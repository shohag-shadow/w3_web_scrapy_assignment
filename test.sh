#!/usr/bin/env bash
# test.sh — schedule a crawl, wait, and copy results to where you run this script.
set -uo pipefail

PROJECT=w3_web_scrapy_assignment
SPIDER=books
BASE=http://localhost:6800

# Where the script was launched from. Everything is copied here.
HERE="$(pwd)"
echo "== Working directory: $HERE =="

# 1. Schedule and capture the jobid.
echo "== Scheduling =="
JOBID=$(curl -s "$BASE/schedule.json" \
        -d project="$PROJECT" \
        -d spider="$SPIDER" \
        -d seed=42 \
        | python -c "import sys,json; print(json.load(sys.stdin).get('jobid',''))")
[ -z "$JOBID" ] && { echo "Schedule failed. Is Scrapyd running?"; exit 1; }
echo "Job: $JOBID"

# 2. Wait until the job leaves running/pending.
echo "== Waiting =="
while true; do
    STATE=$(curl -s "$BASE/listjobs.json?project=$PROJECT" 2>/dev/null | python -c "
import sys, json
try:
    d = json.load(sys.stdin)
    job = '$JOBID'
    if any(j['id'] == job for j in d.get('running', []) + d.get('pending', [])):
        print('running')
    elif any(j['id'] == job for j in d.get('finished', [])):
        print('finished')
    else:
        print('unknown')
except Exception:
    print('error')
")
    case "$STATE" in
        running)  echo -n "."; sleep 2 ;;
        finished) echo; echo "Finished."; break ;;
        error)    echo "!"; sleep 3 ;;
        *)        echo; echo "Job not found (pruned or crashed)."; exit 1 ;;
    esac
done

# 3. Find the log and report success.
echo "== Log =="
LOGPATH=$(docker compose exec -T scrapyd \
    sh -c "find /var/lib/scrapyd/logs /root/logs /logs -name '$JOBID*.log' 2>/dev/null | head -1" \
    2>/dev/null || true)
if [ -n "$LOGPATH" ]; then
    echo "Log: $LOGPATH"
    docker compose exec -T scrapyd \
        grep -E "finish_reason|item_scraped_count" "$LOGPATH" || true
else
    echo "(log not found in container)"
fi

# 4. Copy results to $HERE.
#    Primary source: ./scrapyd-data/  (the volume mount — already on the host)
#    Fallback:       docker compose cp from the container
echo "== Copying results to $HERE =="

# Timestamped snapshot folder so previous runs aren't overwritten.
SNAPSHOT="$HERE/results-$(date +%Y-%m-%d_%H-%M-%S)"
mkdir -p "$SNAPSHOT"

copied=0

# Try the volume mount first — no docker round-trip needed.
for f in books.json books.csv books.xml books.db; do
    if [ -f "$HERE/scrapyd-data/$f" ]; then
        cp "$HERE/scrapyd-data/$f" "$SNAPSHOT/$f"
        cp "$HERE/scrapyd-data/$f" "$HERE/$f"
        echo "  ✓ $f (from volume)"
        copied=$((copied+1))
    fi
done

# Fallback: pull anything missing directly from the container.
if [ "$copied" -lt 4 ]; then
    for f in books.json books.csv books.xml books.db; do
        if [ ! -f "$SNAPSHOT/$f" ]; then
            for src in "/var/lib/scrapyd/$f" "/$f"; do
                if docker compose cp "scrapyd:$src" "$SNAPSHOT/$f" 2>/dev/null; then
                    cp "$SNAPSHOT/$f" "$HERE/$f"
                    echo "  ✓ $f (from container:$src)"
                    copied=$((copied+1))
                    break
                fi
            done
        fi
    done
fi

# Also copy the log alongside the results for the record.
if [ -n "$LOGPATH" ]; then
    docker compose cp "scrapyd:$LOGPATH" "$SNAPSHOT/$JOBID.log" 2>/dev/null \
        && echo "  ✓ $JOBID.log"
fi

# 5. Summary.
echo
echo "== Results =="
ls -lh "$HERE"/books.* 2>/dev/null || echo "  (nothing in $HERE)"
echo
echo "== Snapshot =="
echo "  $SNAPSHOT"
ls -lh "$SNAPSHOT" 2>/dev/null