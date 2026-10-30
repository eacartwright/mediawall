#!/bin/sh
# Linux debug launcher: runs Mediawall in a terminal and keeps the
# terminal open after it exits, so the output can still be read.
# Used by the "Mediawall (debug)" menu entry (tools/create_launchers.py).

cd "$(dirname "$0")/.." || exit 1
venv/bin/python main.py "$@"

echo
printf 'Mediawall has exited. Press Enter to close this window. '
read -r _
