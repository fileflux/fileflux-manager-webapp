#!/bin/bash

# Postgres connection check
PGPASSWORD="${DB_PASSWORD}" pg_isready -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}"
if [ $? -ne 0 ]; then
  echo "CRDB is not ready"
  exit 1
fi
echo "CRDB is ready"

# All checks
exit 0