#!/bin/bash
set -e

# Ensure the actual entrypoint has LF line endings and is executable
if [ -f "/code/entrypoint.sh" ]; then
  sed -i 's/\r$//' /code/entrypoint.sh || true
  chmod +x /code/entrypoint.sh || true
fi

# Ensure PORT has a sensible default
export PORT=${PORT:-8000}

# If DJANGO_SETTINGS_MODULE not set, prefer production for image deployments
export DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE:-config.settings.production}

echo "[entrypoint_wrapper] PORT=$PORT DJANGO_SETTINGS_MODULE=$DJANGO_SETTINGS_MODULE"

# Basic validation: PORT must be a number
if ! (echo "$PORT" | grep -Eq '^[0-9]+$'); then
  echo "[entrypoint_wrapper] ERROR: PORT='$PORT' is not a valid numeric port. Set a numeric PORT (e.g., 8000) in your environment or hosting panel."
  exit 1
fi

# For production, require that DATABASE_URL is set (we don't run a local DB)
if [ "$DJANGO_SETTINGS_MODULE" = "config.settings.production" ]; then
  if [ -z "$DATABASE_URL" ]; then
    echo "[entrypoint_wrapper] WARNING: DJANGO_SETTINGS_MODULE=config.settings.production but DATABASE_URL is not set. Ensure your .env has DATABASE_URL pointing to your external DB."
  fi
fi

# If there are any args provided, forward them to the main entrypoint script
exec /bin/bash /code/entrypoint.sh "$@"
