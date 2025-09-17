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

exec "$@"
