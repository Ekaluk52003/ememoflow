#!/bin/sh

if [ "$DATABASE" = "postgres" ]
then
    echo "Waiting for postgres..."

    while ! nc -z $SQL_HOST $SQL_PORT
    do
      echo "Waiting for PostgreSQL to start on $SQL_HOST:$SQL_PORT..."
      sleep 2
    done

    echo "PostgreSQL started"
fi

# Create backups directory if it doesn't exist
mkdir -p /code/backups

# Run migrations
echo "Running migrations..."
python manage.py migrate

exec "$@"