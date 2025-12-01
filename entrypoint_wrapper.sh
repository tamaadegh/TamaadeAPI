#!/bin/bash
set -e

# Ensure the actual entrypoint has LF line endings and is executable
if [ -f "/code/entrypoint.sh" ]; then
  sed -i 's/\r$//' /code/entrypoint.sh || true
  chmod +x /code/entrypoint.sh || true
fi

# Set defaults for required environment variables
export PORT=${PORT:-8000}
export DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE:-config.settings.production}

echo "[entrypoint_wrapper] PORT=$PORT DJANGO_SETTINGS_MODULE=$DJANGO_SETTINGS_MODULE DATABASE_URL set: $([ -n "$DATABASE_URL" ] && echo 'yes' || echo 'no')"

# If there are any args provided, sanitize and expand environment variables in them, then forward
if [ "$#" -gt 0 ]; then
  sanitized_args=()
  for arg in "$@"; do
    # Convert things like ${PORT:-8000} to $PORT so envsubst can substitute
    arg=$(echo "$arg" | sed -E 's/\$\{([A-Za-z_][A-Za-z0-9_]*)[:-][^}]*\}/\$\1/g')
    # Use envsubst to expand $VAR patterns
    arg=$(echo "$arg" | envsubst)
    sanitized_args+=("$arg")
  done
  echo "[entrypoint_wrapper] Sanitized args: ${sanitized_args[*]}"
  set -- "${sanitized_args[@]}"
fi

exec /bin/bash /code/entrypoint.sh "$@"
