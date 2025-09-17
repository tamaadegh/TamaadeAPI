#!/bin/sh

# Check if we're in Render environment (has DATABASE_URL)
if [ -n "$DATABASE_URL" ]; then
    echo 'Running in Render environment...'
    echo 'Database connection will be handled by Django settings'
else
    echo 'Waiting for postgres...'
    while ! nc -z $DB_HOSTNAME $DB_PORT; do
        sleep 0.1
    done
    echo 'PostgreSQL started'
fi

echo 'Running migrations...'
python manage.py migrate

echo 'Collecting static files...'
python manage.py collectstatic --no-input

echo 'Testing Django import...'
python -c "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production'); import django; django.setup(); print('Django import successful')"

echo 'Testing WSGI import...'
echo "DJANGO_SETTINGS_MODULE: $DJANGO_SETTINGS_MODULE"
python -c "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production'); from config.wsgi import application; print('WSGI import successful')"

echo 'Checking PORT environment variable...'
if [ -z "$PORT" ]; then
    echo "PORT is not set, using default 8000"
    export PORT=8000
else
    echo "PORT is set to $PORT"
fi

echo 'Starting gunicorn...'
echo "Command: $@"
exec "$@" --log-level debug --access-logfile - --error-logfile -
