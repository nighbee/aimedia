#!/bin/sh
# Idempotent migration runner — safe to run on every docker compose up.
# Applied migrations are tracked in the _migrations table.

set -e

MIGRATION_DIR="/migrations"

# Create tracking table if it doesn't exist
psql -v ON_ERROR_STOP=0 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -c "
    CREATE TABLE IF NOT EXISTS _migrations (
        filename TEXT PRIMARY KEY,
        applied_at TIMESTAMPTZ DEFAULT now()
    );"

# Apply each .sql file in order, skipping already-applied ones
for f in $(ls "$MIGRATION_DIR"/*.sql 2>/dev/null | sort); do
    filename=$(basename "$f")

    # Check if already applied (table may not exist yet on first run)
    already=$(psql -v ON_ERROR_STOP=0 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -tAc \
        "SELECT 1 FROM _migrations WHERE filename='$filename'" 2>/dev/null || echo "")

    if [ "$already" = "1" ]; then
        echo "Already applied: $filename"
    else
        echo "Applying: $filename"
        psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -f "$f"
        psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
            -c "INSERT INTO _migrations (filename) VALUES ('$filename');"
    fi
done

echo "All migrations applied."
