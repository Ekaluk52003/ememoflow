#!/bin/sh

if [ "$DATABASE" = "postgres" ]
then
    echo "Waiting for postgres..."

    while ! nc -z $SQL_HOST $SQL_PORT; do
      sleep 0.1
    done

    echo "PostgreSQL started"
fi

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Try to migrate, if it fails due to existing tables, try running migrate with --fake-initial
echo "Applying database migrations..."
python manage.py migrate --no-input || python manage.py migrate --no-input --fake-initial

# Start Gunicorn
echo "Starting Gunicorn..."
exec gunicorn ${DJANGO_PROJECT_NAME}.wsgi:application --bind 0.0.0.0:8000