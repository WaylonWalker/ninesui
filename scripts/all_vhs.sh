#!/usr/bin/env bash
set -euo pipefail
export TERM=xterm-256color
export COLORTERM=truecolor
# Find all .tape files in the assets directory and run `vhs` on each in parallel
find assets -name "*.tape" | parallel --will-cite --halt soon,fail=1 vhs {}
