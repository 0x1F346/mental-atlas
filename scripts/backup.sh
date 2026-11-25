#!/usr/bin/env bash
# Dump the local Postgres database and expire dumps older than 30 days.
#
# Dumps hold real data once a real session is uploaded. They are written under
# data/backups, which is git-ignored and which Claude Code is denied from reading.
# Schedule it with cron or launchd, for example once a day:
#   15 3 * * *  cd /path/to/mental-atlas && make backup
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
dir="${ATLAS_BACKUP_DIR:-$root/data/backups}"
keep_days="${ATLAS_BACKUP_KEEP_DAYS:-30}"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
target="$dir/atlas-$stamp.dump"

mkdir -p "$dir"
chmod 700 "$dir"
cd "$root"
docker compose exec -T postgres pg_dump -U atlas_owner -d atlas --format=custom > "$target.partial"
mv "$target.partial" "$target"
chmod 600 "$target"
# Deleted data leaves the backups within the retention period.
find "$dir" -name 'atlas-*.dump' -mtime "+$keep_days" -delete
find "$dir" -name '*.partial' -mmin +60 -delete

count="$(find "$dir" -name 'atlas-*.dump' | wc -l | tr -d ' ')"
echo "backup written: atlas-$stamp.dump ($count kept, $keep_days-day retention)"
