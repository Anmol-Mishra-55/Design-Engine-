#!/bin/bash
# Backup script for production data

BACKUP_DIR="backups/$(date +%Y%m%d)"
mkdir -p "$BACKUP_DIR"

echo "Creating backup in $BACKUP_DIR..."

# Database backup
echo "Backing up database..."
docker-compose -f deployment/docker-compose.yml exec db pg_dump -U user backend_db > $BACKUP_DIR/database.sql

# Application data backup
echo "Backing up application data..."
docker cp "$(docker-compose -f deployment/docker-compose.yml ps -q backend)":/app/data "$BACKUP_DIR/app_data"

# Reports backup
echo "Backing up reports..."
docker cp "$(docker-compose -f deployment/docker-compose.yml ps -q backend)":/app/reports "$BACKUP_DIR/reports"

# Configuration backup
echo "Backing up configuration..."
cp .env $BACKUP_DIR/env_backup
cp deployment/docker-compose.yml $BACKUP_DIR/

# Compress backup
echo "Compressing backup..."
tar -czf $BACKUP_DIR.tar.gz $BACKUP_DIR
rm -rf $BACKUP_DIR

echo "Backup complete: $BACKUP_DIR.tar.gz"
