#!/bin/bash
# Wispr Backup Script
set -e

BACKUP_DIR="/var/backups/wispr"
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=30
LOG_FILE="/var/log/wispr/backup.log"

mkdir -p "$BACKUP_DIR"
mkdir -p "$(dirname $LOG_FILE)"

# Application backup
APP_TAR="$BACKUP_DIR/wispr_app_$DATE.tar.gz"
tar -czf "$APP_TAR" --exclude='wispr_env' --exclude='__pycache__' --exclude='*.pyc' /var/www/wispr

# SQLite backup
if [ -f "/var/www/wispr/team_collaboration.db" ]; then
    cp /var/www/wispr/team_collaboration.db "$BACKUP_DIR/wispr_db_$DATE.db"
fi

# PostgreSQL backup (if DATABASE_URL is set and is PostgreSQL)
if [ ! -z "$DATABASE_URL" ] && [[ $DATABASE_URL == postgresql* ]]; then
    PG_DUMP_FILE="$BACKUP_DIR/wispr_pg_$DATE.sql"
    pg_dump "$DATABASE_URL" > "$PG_DUMP_FILE"
    gzip "$PG_DUMP_FILE"
fi

# Cleanup old backups
find "$BACKUP_DIR" -name "wispr_*" -mtime +$RETENTION_DAYS -delete

# Log
echo "[$(date)] Backup completed: $DATE" >> "$LOG_FILE" 