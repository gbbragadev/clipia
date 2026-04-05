#!/usr/bin/env bash
# scripts/backup-postgres.sh — Backup diario do PostgreSQL ClipIA
set -euo pipefail

BACKUP_DIR="/mnt/backups/clipia-postgres"
CONTAINER="auto-shorts-postgres-1"
RETENTION_DAYS=14
DATE=$(date +%Y-%m-%d_%H%M)

mkdir -p "$BACKUP_DIR"

echo "[$(date -Iseconds)] Iniciando backup ClipIA PostgreSQL..."

docker exec "$CONTAINER" pg_dumpall -U clipia | gzip > "$BACKUP_DIR/clipia_${DATE}.sql.gz"

# Limpar backups antigos
find "$BACKUP_DIR" -name "clipia_*.sql.gz" -mtime +${RETENTION_DAYS} -delete

SIZE=$(du -sh "$BACKUP_DIR/clipia_${DATE}.sql.gz" | cut -f1)
echo "[$(date -Iseconds)] Backup concluido: $SIZE"
