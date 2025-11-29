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

# If there are any args provided, forward them to the main entrypoint script
exec /bin/bash /code/entrypoint.sh "$@"
