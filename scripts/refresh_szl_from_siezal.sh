#!/usr/bin/env bash
# HISTORICAL DESTRUCTIVE UTILITY. It once refreshed the szl dev/test site
# from siezal. SZL is now designated future production; do not assume either
# site's current role. The old cron entry is disabled.
#
# Run on demand:
#   bash /home/nabeel/frappe-bench/scripts/refresh_szl_from_siezal.sh
#
# WARNING: this completely overwrites szl's database and files with
# siezal's. Any szl-only test data present at run time is destroyed.
# szl's Administrator login and site_config.json encryption_key are also
# overwritten to match siezal, since encrypted fields (e.g. FBR Integration
# Settings security_token) restored from siezal's backup can only decrypt
# with siezal's own encryption key.

set -euo pipefail

EXPECTED_CONFIRMATION="OVERWRITE_SZL_FROM_SIEZAL"
if [[ "${AIMATIC_DESTRUCTIVE_REFRESH_CONFIRMATION:-}" != "$EXPECTED_CONFIRMATION" ]]; then
    echo "BLOCKED: this historical script destroys SZL data."
    echo "Verify both site roles, obtain explicit approval, take an independent SZL backup,"
    echo "prepare verification/rollback, then set AIMATIC_DESTRUCTIVE_REFRESH_CONFIRMATION=$EXPECTED_CONFIRMATION."
    exit 64
fi

BENCH_DIR="/home/nabeel/frappe-bench"
BENCH="/home/nabeel/.local/bin/bench"
SRC_SITE="siezal"
DST_SITE="szl"
LOG_DIR="$BENCH_DIR/logs"
LOG_FILE="$LOG_DIR/refresh_szl_from_siezal.log"
LOCK_FILE="$LOG_DIR/refresh_szl_from_siezal.lock"
BACKUP_DIR="$BENCH_DIR/sites/$SRC_SITE/private/backups"
RETENTION_DAYS=7

mkdir -p "$LOG_DIR"

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') [refresh] already running, skipping this run" >> "$LOG_FILE"
    exit 0
fi

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [refresh] $*" | tee -a "$LOG_FILE"
}

cd "$BENCH_DIR"

trap 'log "FAILED (exit $?) — szl left untouched or partially restored, check log above"' ERR

log "=== starting refresh of $DST_SITE from $SRC_SITE ==="

log "1/5 backing up $SRC_SITE (db + files)"
"$BENCH" --site "$SRC_SITE" backup --with-files --compress >> "$LOG_FILE" 2>&1

# --compress produces .tgz, uncompressed would be .tar — match either.
DB_FILE=$(ls -t "$BACKUP_DIR"/*-"$SRC_SITE"-database.sql.gz | head -1)
PUBLIC_FILE=$(ls -t "$BACKUP_DIR"/*-"$SRC_SITE"-files.* | head -1)
PRIVATE_FILE=$(ls -t "$BACKUP_DIR"/*-"$SRC_SITE"-private-files.* | head -1)

log "using backup set:"
log "  db:      $DB_FILE"
log "  public:  $PUBLIC_FILE"
log "  private: $PRIVATE_FILE"

log "2/5 syncing encryption_key from $SRC_SITE onto $DST_SITE (required to decrypt restored Password-type fields)"
ENC_KEY=$(python3 -c "import json; print(json.load(open('sites/$SRC_SITE/site_config.json'))['encryption_key'])")
"$BENCH" --site "$DST_SITE" set-config encryption_key "$ENC_KEY" >> "$LOG_FILE" 2>&1

log "3/5 restoring $SRC_SITE backup onto $DST_SITE (this overwrites $DST_SITE's database and files)"
"$BENCH" --site "$DST_SITE" restore "$DB_FILE" \
    --with-public-files "$PUBLIC_FILE" \
    --with-private-files "$PRIVATE_FILE" \
    --force >> "$LOG_FILE" 2>&1

log "4/5 running migrate + clear-cache on $DST_SITE"
"$BENCH" --site "$DST_SITE" migrate >> "$LOG_FILE" 2>&1
"$BENCH" --site "$DST_SITE" clear-cache >> "$LOG_FILE" 2>&1

log "5/5 pruning $SRC_SITE backups older than $RETENTION_DAYS days"
find "$BACKUP_DIR" -maxdepth 1 -type f -mtime "+$RETENTION_DAYS" -delete

log "=== refresh complete: $DST_SITE now mirrors $SRC_SITE ==="
