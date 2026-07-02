#!/bin/sh
# Apply migrations, seed the first admin if configured, then serve.
set -e

node scripts/migrate.mjs

if [ -n "$ADMIN_EMAIL" ] && [ -n "$ADMIN_PASSWORD" ]; then
  # Idempotent upsert — safe on every boot.
  node scripts/seed-admin.mjs || echo "seed-admin failed (continuing)"
fi

exec npx next start -H 0.0.0.0 -p 3000
