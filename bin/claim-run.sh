#!/usr/bin/env bash
# Claim a per-run state dir under /tmp for an arcg drive.
#
#   bin/claim-run.sh [N]
#
# N (run number) is optional. Given, you claim /tmp/arcg-run<N> (idempotent —
# re-claiming the same N returns the same dir, so a drive can resume). Omitted,
# it picks the next free number so a new run never collides with an old one.
#
# Prints the absolute dir path on stdout (only that, so it is captureable:
# RUN=$(bin/claim-run.sh)). Narration goes to stderr. Every arcg/simmer/jotter
# command in the drive is then prefixed `ARCG_STATE_DIR=$RUN ...`.
set -euo pipefail

prefix=/tmp/arcg-run
if [ "$#" -ge 1 ]; then
  n="$1"
  case "$n" in (*[!0-9]*|'') echo "claim-run: run number must be a non-negative integer, got '$n'" >&2; exit 2;; esac
else
  n=1
  while [ -e "${prefix}${n}" ]; do n=$((n + 1)); done
fi

dir="${prefix}${n}"
fresh=yes; [ -d "$dir" ] && fresh=no
mkdir -p "$dir"
echo "claim-run: run $n -> $dir ($( [ "$fresh" = yes ] && echo fresh || echo resumed ))" >&2
echo "$dir"
