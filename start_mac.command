#!/usr/bin/env bash
cd "$(dirname "$0")"
if command -v python3 >/dev/null 2>&1; then
  python3 START_HERE.py
elif command -v python >/dev/null 2>&1; then
  python START_HERE.py
else
  echo "Python 3 is not installed. Install it from https://www.python.org/downloads/ and run this again."
fi
echo
read -r -p "Press Enter to close this window..."
