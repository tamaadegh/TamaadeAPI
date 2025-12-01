#!/bin/bash
set -e

# Ensure the actual entrypoint has LF line endings and is executable
if [ -f "/code/entrypoint.sh" ]; then
  sed -i 's/\r$//' /code/entrypoint.sh || true
  chmod +x /code/entrypoint.sh || true
fi

# Ensure PORT has a sensible default and is numeric
PORT="${PORT:-8000}"
# Clean PORT: remove any whitespace, quotes, or literal $PORT strings
PORT=$(echo "$PORT" | sed 's/[^0-9]//g')
[ -z "$PORT" ] && PORT="8000"
export PORT

# If DJANGO_SETTINGS_MODULE not set, prefer production for image deployments
export DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE:-config.settings.production}

echo "[entrypoint_wrapper] PORT=$PORT DJANGO_SETTINGS_MODULE=$DJANGO_SETTINGS_MODULE"

# Validate PORT is numeric and in valid range (1-65535)
if ! [ "$PORT" -ge 1 ] 2>/dev/null || ! [ "$PORT" -le 65535 ] 2>/dev/null; then
  echo "[entrypoint_wrapper] ERROR: PORT='$PORT' is not a valid port number (must be 1-65535). Check your PORT environment variable."
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
