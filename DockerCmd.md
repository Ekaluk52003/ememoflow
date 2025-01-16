##Dev Docker
docker-compose logs -f
docker-compose exec web python migrate_data.py
docker-compose exec web python manage.py createsuperuser
docker-compose logs web -f
docker-compose logs db
docker-compose down -v
docker-compose up -d --build


logs tour_pack-web2-1

apt docker compose


sudo docker-compose -f docker-compose.prod.yml up -d --build web

sudo docker-compose -f docker-compose.prod.yml up -d --build


sudo docker-compose -f docker-compose.prod.yml up -d --build



sudo docker-compose -f docker-compose.prod.yml exec web ls /app/staticfiles


sudo docker-compose -f docker-compose.prod.yml exec web python manage.py migrate
sudo docker-compose -f docker-compose.prod.yml exec web  python manage.py makemigrations
sudo docker-compose -f docker-compose.prod.yml exec web  python manage.py createsuperuser
sudo docker-compose -f docker-compose.prod.yml logs web -f
sudo docker-compose -f docker-compose.prod.yml exec web  python manage.py collectstatic

docker-compose run web npm run dev
docker-compose exec web  python manage.py collectstatic

docker-compose exec web python manage.py python manage.py makemigrations

docker-compose exec web celery -A django_project worker --loglevel=info


sudo docker-compose -f docker-compose.prod.yml up -d --build



sudo docker-compose -f docker-compose.prod.yml exec web  python manage.py collectstatic

sudo docker-compose -f docker-compose.prod.yml exec web python manage.py makemigrations


sudo docker-compose -f docker-compose.prod.yml logs db -f


sudo docker-compose -f docker-compose.prod.yml exec db psql -U postgres -c "CREATE DATABASE hello_django_prod;"

sudo docker-compose -f docker-compose.prod.yml exec db psql -U postgres -d hello_django_prod -f /docker-entrypoint-initdb.d/db_dump.sql

sudo docker-compose -f docker-compose.prod.yml exec db psql -U  hello_django -d hello_django_prod



##Dumpdb from docker to local computure
docker-compose exec db pg_dumpall -c -U postgres > db_dump.sql

sudo docker-compose -f docker-compose.prod.yml exec db psql -U hello_django -f /docker-entrypoint-initdb.d/db_dump.sql

sudo docker-compose -f docker-compose.prod.yml exec db psql -U postgres -d postgres -f /docker-entrypoint-initdb.d/db_dump.sql


D:\Django\djangox\db_dump.sql   /home/ekaluk/smartflow

scp db_dump.sql user@vm_ip:/path/to/project


My VM IP is 103.117.148.194
My dumdb is D:\Django\djangox\db_dump.sql
My VM part is /home/ekaluk/smartflow

scp D:\Django\djangox\db_dump.sql ekaluk@103.117.148.194:/home/ekaluk/smartflow/db_dump.sql


sudo docker-compose -f docker-compose.prod.yml exec db psql -U hello_django -d hello_django_prod -f /docker-entrypoint-initdb.d/db_dump.sql > import_log.txt 2>&1

sudo docker-compose -f docker-compose.prod.yml exec db psql -U hello_django  -d hello_django_prod -f /docker-entrypoint-initdb.d/db_dump.sql > import_log.txt 2>&1 cat import_log.txt

103.117.148.194

##Prod Docker
sudo docker-compose -f docker-compose.prod.yml exec web python manage.py migrate --noinput
sudo docker-compose -f docker-compose.prod.yml exec web python manage.py migrate
sudo docker-compose -f docker-compose.prod.yml down -v
sudo docker-compose -f docker-compose.prod.yml up -d --build
sudo docker-compose -f docker-compose.prod.yml logs

sudo docker-compose -f docker-compose.prod.yml exec db psql -U hello_django -f /docker-entrypoint-initdb.d/db_dump.sql



sudo docker-compose -f docker-compose.prod.yml up -d db


sudo docker-compose -f docker-compose.prod.yml exec db psql -U postgres -d postgres -f /docker-entrypoint-initdb.d/db_dump.sql

sudo docker-compose -f docker-compose.prod.yml exec db psql -U postgres -d postgres \dt

sudo docker-compose -f docker-compose.prod.yml exec db psql -U postgres -d postgres
\dt



sudo docker-compose -f docker-compose.prod.yml ps

sudo docker cp db_dump.sql smartflow-db-1:/db_dump.sql
sudo docker-compose -f docker-compose.prod.yml exec db bash
psql -U hello_django -d <database_name>


docker-compose exec -u postgres db pg_dump -U postgres postgres > mydatabase_dump.sql



 sudo docker-compose -f docker-compose.prod.yml exec db psql -U hello_django -d hello_django_prod -f /docker-entrypoint-initdb.d/db_dump.sql



sudo docker-compose -f docker-compose.prod.yml exec db psql -U hello_django -d hello_django_prod

sudo docker-compose -f docker-compose.prod.yml logs db

hello_django_prod



sudo docker-compose down -v


EkalukPongsri50915
1MFTRJGBXQ5TU8Q166Q67U2F

docker-compose run web bash psql -h db -U ekaluk -d django1


sudo docker-compose -f docker-compose.prod.yml logs db -f

docker exec -it 2325303790dc sh /code/entrypoint.sh


docker exec -it cbb145ca1cdd8e931b721813177af9d1b28ea030697fcee62d2db9a62a9d945e sh /code/entrypoint.sh


docker compose -f docker-compose.prod.yml exec web bash