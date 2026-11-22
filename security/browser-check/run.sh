#!/bin/bash
# Browser checks (Parts 14-15). Run from the repo root, in a venv with requirements-dev.txt:
#   bash security/browser-check/run.sh regression.mjs <screenshot-dir>
#   bash security/browser-check/run.sh csp-check.mjs     # SEC-05: CSP + framing
#   bash security/browser-check/run.sh loadfail.mjs      # SEC-09: load-failure message
# Starts Flask (port 5077), a static server for docs/ (8077), a page that tries to
# frame the game (8078) and headless Chromium (9277), then runs the script once per mode.
# Needs Node 22+ and Chromium; the first run of Pyodide takes a few seconds.
set -u
D=security/browser-check
TMP=$(mktemp -d)
SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(32))') \
  flask --app app run --port 5077 > "$TMP/flask.log" 2>&1 &
python3 -m http.server 8077 -d docs > /dev/null 2>&1 &
mkdir -p "$TMP/framer" && cp $D/framer.html "$TMP/framer/index.html"
python3 -m http.server 8078 -d "$TMP/framer" > /dev/null 2>&1 &
chromium --headless=new --remote-debugging-port=9277 --user-data-dir="$TMP/chromium" about:blank > /dev/null 2>&1 &
sleep 2
for url in http://127.0.0.1:5077/ http://127.0.0.1:8077/; do
  node $D/"$1" 9277 "$url" "${@:2}"
done
kill $(jobs -p) 2>/dev/null; wait 2>/dev/null; rm -rf "$TMP"
