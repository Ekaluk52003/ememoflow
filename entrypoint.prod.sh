#!/bin/sh

if [ "$DATABASE" = "postgres" ]
then
    echo "Waiting for postgres..."

    while ! nc -z $SQL_HOST $SQL_PORT; do
      sleep 0.1
    done

    echo "PostgreSQL started"
fi

# Only run migrations and collect static for web service
if [ "$1" = "gunicorn" ]; then
    # Collect static files
    echo "Collecting static files..."
    python manage.py collectstatic --noinput

    # Try to migrate, if it fails due to existing tables, try running migrate with --fake-initial
    echo "Applying database migrations..."
    python manage.py migrate --no-input || python manage.py migrate --no-input --fake-initial
fi

# If command starts with celery, handle celery-specific migrations
if [ "${1%%\ *}" = "celery" ]; then
    echo "Running Celery migrations..."
    python manage.py migrate django_celery_beat --fake-initial
fi

# Start the service
echo "Starting service: $@"
exec "$@"