#!/bin/sh
set -eu

backup_dir="${BACKUP_DIR:-/backups}"
retention_days="${BACKUP_RETENTION_DAYS:-14}"
interval_seconds="${BACKUP_INTERVAL_SECONDS:-86400}"
mkdir -p "$backup_dir"
umask 077

case "$retention_days:$interval_seconds" in
  *[!0-9:]*|:*|*:) echo "Backup retention and interval must be positive integers." >&2; exit 2 ;;
esac
[ "$retention_days" -gt 0 ] && [ "$interval_seconds" -gt 0 ] || exit 2

while :; do
  timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
  final="$backup_dir/career-engine-$timestamp.dump"
  temporary="$final.partial"
  if pg_dump --format=custom --no-owner --no-acl --file="$temporary"; then
    if pg_restore --list "$temporary" >/dev/null 2>&1; then
      mv "$temporary" "$final"
      find "$backup_dir" -maxdepth 1 -type f -name 'career-engine-*.dump' -mtime "+$retention_days" -delete
      echo "Backup completed: $(basename "$final")"
    else
      echo "Backup validation failed; preserving previous backups." >&2
      rm -f "$temporary"
    fi
  else
    echo "Backup failed; preserving previous backups." >&2
    rm -f "$temporary"
  fi
  sleep "$interval_seconds"
done
