#!/bin/sh
# Put the village (town file, database, DCC characters) back as a backup left it, e.g.
#   scripts/dcc/westmarch_reset.sh before-history-experiment        # data/westmarch-backup-20261009-before-history-experiment.tar.gz
#   scripts/dcc/westmarch_reset.sh                                   # lists the backups
# Stops a running fast-forward first. The nightly update carries on from the day the backup was made.
cd "$(dirname "$0")/.." || exit 1
if [ -z "$1" ]; then ls -1 data/westmarch-backup-*.tar.gz | sed 's#data/westmarch-backup-##; s#\.tar\.gz##'; exit 0; fi
file=$(ls -1 data/westmarch-backup-*"$1"*.tar.gz 2>/dev/null | head -1)
[ -n "$file" ] || { echo "no backup matching $1"; exit 1; }
docker exec sheet sh -c 'for p in /proc/[0-9]*; do case "$(tr "\0" " " < $p/cmdline 2>/dev/null)" in *ff.py*) kill ${p#/proc/};; esac; done' 2>/dev/null
docker exec sheet tar xzf "/app/data/$(basename "$file")" -C /app && echo "village restored from $file"
