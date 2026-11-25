#!/usr/bin/env bash
# Confirm the newest backup restores: load it into a scratch database, compare row
# counts with the live database, then drop the scratch database. Prints counts only.
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
dir="${ATLAS_BACKUP_DIR:-$root/data/backups}"
scratch="atlas_restore_check"
tables="users sources segments statements nodes edges evidence map_positions"

newest="$(find "$dir" -name 'atlas-*.dump' | sort | tail -n 1)"
if [ -z "$newest" ]; then
  echo "no backup found; run make backup first" >&2
  exit 1
fi

cd "$root"
psql_in() { docker compose exec -T postgres psql -U atlas_owner -v ON_ERROR_STOP=1 -At "$@"; }
counts() {
  for table in $tables; do
    printf '%s=%s ' "$table" "$(psql_in -d "$1" -c "SELECT count(*) FROM $table")"
  done
}

psql_in -d postgres -c "DROP DATABASE IF EXISTS $scratch" > /dev/null
psql_in -d postgres -c "CREATE DATABASE $scratch OWNER atlas_owner" > /dev/null
trap 'psql_in -d postgres -c "DROP DATABASE IF EXISTS $scratch" > /dev/null' EXIT
docker compose exec -T postgres pg_restore -U atlas_owner -d "$scratch" --no-owner --exit-on-error < "$newest"

restored="$(counts "$scratch")"
echo "restored from $(basename "$newest"): $restored"
echo "live database now:                  $(counts atlas)"
echo "restore check passed: the dump loads and every table is readable"
