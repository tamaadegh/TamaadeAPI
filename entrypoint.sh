#!/bin/bash

# Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    echo 'Error: DATABASE_URL is not set. Exiting.'
    exit 1
fi

echo 'Using DATABASE_URL for database connection.'

# Wait for the database to be ready
until nc -z $(echo $DATABASE_URL | sed -E 's|.*://[^@]*@([^:/]+):([0-9]+).*|\1 \2|'); do
    echo 'Waiting for the database to be ready...'
    sleep 1
done

echo 'Database is ready.'

echo 'Running migrations...'
python manage.py migrate

# Collect static only if not a Celery worker and when DEBUG is not true
case "$1" in
  celery)
    echo 'Skipping collectstatic for Celery worker'
    ;;
  *)
    if [ "${DEBUG}" = "True" ] || [ "${DEBUG}" = "true" ]; then
      echo 'DEBUG=True -> skipping collectstatic in development'
    else
      echo 'Collecting static files...'
      python manage.py collectstatic --no-input
    fi
    ;;
esac

echo 'Testing Django import...'
python -c "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production'); import django; django.setup(); print('Django import successful')"

echo 'Testing WSGI import...'
echo "DJANGO_SETTINGS_MODULE: $DJANGO_SETTINGS_MODULE"
python -c "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production'); from config.wsgi import application; print('WSGI import successful')"

echo "PORT validation and setup..."
# Ensure PORT is numeric; strip non-numeric characters
PORT="${PORT:-8000}"
PORT=$(echo "$PORT" | sed 's/[^0-9]//g')
[ -z "$PORT" ] && PORT="8000"
export PORT

# Validate PORT is in valid range
if ! [ "$PORT" -ge 1 ] 2>/dev/null || ! [ "$PORT" -le 65535 ] 2>/dev/null; then
  echo "ERROR: PORT='$PORT' is not valid (must be 1-65535)"
  exit 1
fi
echo "PORT is set to $PORT"
# If the prepared command line contains an explicit binding like `--bind 0.0.0.0:XXXX` or
# `--bind=0.0.0.0:XXXX`, prefer that port if it's a valid integer in range. This helps when
# platforms inject a port into the command rather than an environment variable.
if [ "$#" -gt 0 ]; then
  ARGS=("$@")
  for i in "${!ARGS[@]}"; do
    arg="${ARGS[$i]}"
    if [ "$arg" = "--bind" ]; then
      valIndex=$((i+1))
      if [ $valIndex -lt ${#ARGS[@]} ]; then
        val="${ARGS[$valIndex]}"
      fi
    elif [[ "$arg" == --bind=* ]]; then
      val="${arg#--bind=}"
    fi
    if [ -n "${val:-}" ]; then
      # extract anything after the last ':' (port), handle IPv6 by looking for last ':'
      candidate_port="${val##*:}"
      candidate_port=$(echo "$candidate_port" | sed 's/[^0-9]//g')
      if [ -n "$candidate_port" ] && [ "$candidate_port" -ge 1 ] 2>/dev/null && [ "$candidate_port" -le 65535 ] 2>/dev/null; then
        echo "[entrypoint] Found explicit bind port from args: $candidate_port; using it as PORT"
        PORT="$candidate_port"
        export PORT
        break
      fi
    fi
  done
fi

# If command arguments were provided (for example a platform-specific startCommand), try
# to safely expand environment variables (like $PORT or ${PORT:-8000}) inside those
# arguments so that they don't remain literal strings like '$PORT' and cause validation errors.
if [ "$#" -gt 0 ]; then
  sanitized_args=()
  for arg in "$@"; do
    arg=$(echo "$arg" | sed -E 's/\$\{([A-Za-z_][A-Za-z0-9_]*)[:-][^}]*\}/\$\1/g')
    if command -v envsubst >/dev/null 2>&1; then
      arg=$(echo "$arg" | envsubst)
    fi
    sanitized_args+=("$arg")
  done
  echo "[entrypoint] Sanitized args: ${sanitized_args[*]}"
  set -- "${sanitized_args[@]}"
fi

echo 'Starting application...'
if [ $# -eq 0 ]; then
    echo "Running gunicorn on port $PORT"
    exec gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 3 --log-level info --access-logfile - --error-logfile -
else
    case "$1" in
      celery)
        echo "Running Celery worker"
        exec "$@"
        ;;
      gunicorn|python)
        echo "Running: $@"
        exec "$@"
        ;;
      *)
        echo "Running custom command: $@"
        exec "$@"
        ;;
    esac
fi
