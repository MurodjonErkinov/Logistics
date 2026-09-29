DC=docker compose


build:
	$(DC) build --no-cache

up:
	$(DC) up -d

stop:
	$(DC) stop

down:
	$(DC) down

restart: down up

migrations:
	$(DC) exec web python manage.py makemigrations

migrate:
	$(DC) exec web python manage.py migrate

createsuperuser:
	$(DC) exec web python manage.py createsuperuser

collectstatic:
	$(DC) exec web python manage.py collectstatic --noinput

shell:
	$(DC) exec web python manage.py shell

test:
	$(DC) exec web python manage.py test

bash:
	$(DC) exec web bash

logs:
	$(DC) logs -f
