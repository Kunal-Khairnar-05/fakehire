#!/bin/sh
# Runs ONCE, the first time the postgres container starts with an EMPTY data volume.
# (The official postgres image runs every file in /docker-entrypoint-initdb.d/.)
#
# Creates two databases and applies every migration to both:
#   fakehire       -> the app
#   fakehire_test  -> the tests (wiped before every test)
set -e

for db in "$POSTGRES_DB" "${POSTGRES_DB}_test"; do
  if [ "$db" != "$POSTGRES_DB" ]; then
    echo "Creating database $db"
    psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "CREATE DATABASE \"$db\""
  fi
  for migration in /migrations/*.sql; do
    echo "Applying $migration to $db"
    psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$db" -f "$migration"
  done
done
