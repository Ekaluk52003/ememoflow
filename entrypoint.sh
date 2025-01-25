#!/bin/sh

if [ "$DATABASE" = "postgres" ]
then
    echo "Waiting for postgres..."

    while ! nc -z $SQL_HOST $SQL_PORT; do
        sleep 0.1
    done

    echo "PostgreSQL started"
fi

# Start cron service
service cron start

# Add crontab and show crontab list for debugging
python manage.py crontab add
python manage.py crontab show

python manage.py migrate

exec "$@"