import os
import django
import sqlite3
import psycopg2
from psycopg2 import sql

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_project.settings")
django.setup()

from django.apps import apps

def get_all_models():
    return apps.get_models()

def sqlite_connect():
    return sqlite3.connect('db.sqlite3')

def postgres_connect():
    return psycopg2.connect(
        dbname="hello_django_dev",
        user="hello_django",
        password="hello_django",
        host="db",
        port="5432"
    )

def get_field_types(model):
    return {f.name: f.get_internal_type() for f in model._meta.fields}

def convert_value(value, field_type):
    if value is None:
        return None
    if field_type == 'BooleanField':
        return bool(value)
    if field_type in ['IntegerField', 'BigIntegerField', 'SmallIntegerField']:
        return int(value)
    if field_type in ['FloatField', 'DecimalField']:
        return float(value)
    return value

def migrate_table(sqlite_cur, pg_cur, model):
    table_name = model._meta.db_table
    field_types = get_field_types(model)

    sqlite_cur.execute(f"SELECT * FROM {table_name}")
    rows = sqlite_cur.fetchall()

    if not rows:
        return

    columns = [description[0] for description in sqlite_cur.description]

    for row in rows:
        converted_row = [convert_value(value, field_types.get(col, '')) for col, value in zip(columns, row)]

        placeholders = ','.join(['%s'] * len(columns))
        insert_query = sql.SQL("INSERT INTO {} ({}) VALUES ({}) ON CONFLICT DO NOTHING").format(
            sql.Identifier(table_name),
            sql.SQL(', ').join(map(sql.Identifier, columns)),
            sql.SQL(', ').join(sql.Placeholder() * len(columns))
        )
        pg_cur.execute(insert_query, converted_row)

def main():
    sqlite_conn = sqlite_connect()
    pg_conn = postgres_connect()

    sqlite_cur = sqlite_conn.cursor()
    pg_cur = pg_conn.cursor()

    for model in get_all_models():
        print(f"Migrating {model._meta.db_table}...")
        migrate_table(sqlite_cur, pg_cur, model)

    pg_conn.commit()

    sqlite_conn.close()
    pg_conn.close()

    print("Migration completed!")

if __name__ == "__main__":
    main()