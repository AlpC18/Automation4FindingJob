#!/bin/sh
set -eu

backup_file="${1:-}"
if [ "${CONFIRM_RESTORE:-}" != "YES" ]; then
  echo "Restore overwrites matching records in the target database. Set CONFIRM_RESTORE=YES to continue." >&2
  exit 2
fi
if [ -z "$backup_file" ] || [ ! -f "$backup_file" ]; then
  echo "Usage: CONFIRM_RESTORE=YES $0 /path/to/career-engine-YYYYMMDDTHHMMSSZ.dump" >&2
  exit 2
fi
case "$backup_file" in
  /backups/career-engine-*.dump) ;;
  *) echo "Restore is restricted to generated database backups under /backups." >&2; exit 2 ;;
esac
if [ -z "${PGDATABASE:-}" ]; then
  echo "PGDATABASE must name the intended restore target." >&2
  exit 2
fi
pg_restore --list "$backup_file" >/dev/null
pg_restore --clean --if-exists --no-owner --no-acl --dbname="$PGDATABASE" "$backup_file"
echo "Restore finished for database: $PGDATABASE"
