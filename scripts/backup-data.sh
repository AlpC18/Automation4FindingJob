#!/bin/sh
# Archive the local database, vector store and .env (it holds the key that decrypts saved tokens)
# to another disk. Usage: scripts/backup-data.sh   (BACKUP_DIR and BACKUP_KEEP are optional)
# ponytail: plain tar of live files; run it while the app is stopped, or switch to `sqlite3 .backup` if that is a burden.
set -eu

cd "$(dirname "$0")/.."
backup_dir="${BACKUP_DIR:-/Volumes/SandDisk SSD/Backups/career-agent}"
keep="${BACKUP_KEEP:-14}"
umask 077
mkdir -p "$backup_dir"

final="$backup_dir/career-agent-$(date -u +%Y%m%dT%H%M%SZ).tar.gz"
tar -czf "$final.partial" backend/data .env
tar -tzf "$final.partial" >/dev/null
mv "$final.partial" "$final"
ls -1t "$backup_dir"/career-agent-*.tar.gz | tail -n "+$((keep + 1))" | while read -r old; do rm -f "$old"; done
echo "Backup completed: $final"
