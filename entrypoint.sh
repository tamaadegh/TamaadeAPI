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

echo 'Checking PORT environment variable...'
# Ensure PORT is numeric; strip non-numeric characters
PORT="${PORT:-8000}"
PORT=$(echo "$PORT" | sed 's/[^0-9]//g')
[ -z "$PORT" ] && PORT="8000"
export PORT
echo "PORT is set to $PORT"

echo 'Starting process...'
if [ $# -eq 0 ]; then
    echo "No arguments provided, running gunicorn directly"
    echo "Running: gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --log-level debug --access-logfile - --error-logfile -"
    exec gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --log-level debug --access-logfile - --error-logfile -
else
    echo "Arguments provided: $@"
    # Handle specific commands without appending gunicorn flags
    case "$1" in
      celery)
        echo "Running Celery worker: $@"
        exec "$@"
        ;;
      python)
        # If running Django dev server, ensure correct bind and no extra flags
        if [ "$2" = "manage.py" ] && [ "$3" = "runserver" ]; then
          echo "Running Django development server"
          exec python manage.py runserver 0.0.0.0:$PORT
        else
          echo "Running Python command: $@"
          exec "$@"
        fi
        ;;
      gunicorn)
        echo "Running provided gunicorn command"
        exec "$@"
        ;;
      *)
        echo "Running provided command as-is"
        exec "$@"
        ;;
    esac
fi
