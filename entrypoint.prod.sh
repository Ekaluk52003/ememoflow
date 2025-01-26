#!/bin/sh

if [ "$DATABASE" = "postgres" ]; then
    echo "Waiting for postgres..."

    while ! nc -z $SQL_HOST $SQL_PORT; do
        sleep 0.1
    done

    echo "PostgreSQL started"
fi

# Collect static files only for web service
if [ "$SERVICE" = "web" ]; then
    echo "Collecting static files..."
    python manage.py collectstatic --noinput

    echo "Applying database migrations..."
    python manage.py migrate --noinput || python manage.py migrate --noinput --fake-initial
fi

# Start the appropriate service
case "$SERVICE" in
    web)
        echo "Starting Gunicorn..."
        exec gunicorn ${DJANGO_PROJECT_NAME}.wsgi:application --bind 0.0.0.0:8000
        ;;
    celery)
        echo "Starting Celery worker..."
        exec celery -A ${DJANGO_PROJECT_NAME} worker --loglevel=info --concurrency=2 --max-tasks-per-child=500 --optimization=fair
        ;;
    celery-beat)
        echo "Starting Celery Beat..."
        exec celery -A ${DJANGO_PROJECT_NAME} beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
        ;;
    *)
        echo "Unknown service: $SERVICE"
        exec "$@"
        ;;
esac
