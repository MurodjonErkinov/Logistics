DC ?= docker compose
PYTHON ?= python3

.PHONY: build build-openai build-ollama up telegram-up telegram-login stop down restart migrations migrate createsuperuser collectstatic shell test bash logs
.NOTPARALLEL:


build:
	$(DC) build --no-cache

build-openai:
	$(PYTHON) scripts/ai_stack.py build --provider openai --compose "$(DC)"

build-ollama:
	$(PYTHON) scripts/ai_stack.py build --provider ollama --compose "$(DC)"

up:
	$(PYTHON) scripts/ai_stack.py up --compose "$(DC)"

telegram-up: up

telegram-login:
	$(DC) run --rm telegram_importer python manage.py telegram_login

stop:
	$(DC) --profile telegram --profile ollama --profile frontend --profile driver-bot stop

down:
	$(DC) --profile telegram --profile ollama --profile frontend --profile driver-bot down

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

.PHONY: frontend-dev frontend-build frontend-up frontend-logs frontend-stop

frontend-dev:
	cd frontend && npm run dev

frontend-build:
	$(DC) --profile frontend build frontend

frontend-up:
	$(DC) --profile frontend up -d --build frontend

frontend-logs:
	$(DC) logs -f frontend

frontend-stop:
	$(DC) stop frontend

.PHONY: driver-bot-up driver-bot-logs driver-worker-up

driver-bot-up:
	$(DC) --profile driver-bot up -d driver_bot driver_worker

driver-bot-logs:
	$(DC) logs -f driver_bot driver_worker

driver-worker-up:
	$(DC) up -d driver_worker

PDC = docker compose --project-name logistics-prod --env-file .env.production -f compose.production.yaml

.PHONY: prod-build prod-up prod-check prod-logs prod-bot-up prod-telegram-login prod-telegram-up prod-backup

prod-build:
	$(PDC) build web frontend

prod-up:
	$(PDC) up -d --wait

prod-check:
	$(PDC) config --quiet
	$(PDC) exec web python manage.py check --deploy --fail-level WARNING
	$(PDC) exec web python manage.py makemigrations --check --dry-run

prod-logs:
	$(PDC) logs --tail=100 -f

prod-bot-up:
	$(PDC) --profile driver-bot up -d --force-recreate driver_bot

prod-telegram-login:
	$(PDC) --profile telegram run --rm telegram_importer python manage.py telegram_login

prod-telegram-up:
	$(PDC) --profile telegram up -d --force-recreate telegram_importer

prod-backup:
	mkdir -p backups
	chmod 700 backups
	umask 077; $(PDC) exec -T db sh -c 'pg_dump -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" -Fc' > backups/logistics-$$(date +%Y%m%d-%H%M%S).dump
