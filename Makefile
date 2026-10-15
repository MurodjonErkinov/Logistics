PYTHON ?= python3
# Prefer the server configuration when it exists; use MODE=dev to override.
MODE ?= $(if $(wildcard .env.production),prod,dev)
PDC = docker compose --project-name logistics-prod --env-file .env.production -f compose.production.yaml
DC ?= $(if $(filter prod,$(MODE)),$(PDC),docker compose)
ALL_DC = $(DC) --profile telegram --profile frontend --profile driver-bot
PROD_DC = $(PDC) --profile telegram --profile driver-bot
.DEFAULT_GOAL := up

.PHONY: build build-openai up telegram-up telegram-login stop down restart migrations migrate createsuperuser collectstatic shell test bash logs
.NOTPARALLEL:


build:
	$(ALL_DC) build

build-openai:
	$(PYTHON) scripts/ai_stack.py build --provider openai --compose "$(DC)"

# Rebuild and recreate every service, including the opt-in bot/parser profiles.
up:
	$(ALL_DC) config --quiet
	$(ALL_DC) build web frontend
	$(ALL_DC) up -d --wait --force-recreate
	$(ALL_DC) ps

telegram-up: up

telegram-login:
	$(ALL_DC) run --rm telegram_importer python manage.py telegram_login

stop:
	$(DC) --profile telegram --profile frontend --profile driver-bot stop

down:
	$(DC) --profile telegram --profile frontend --profile driver-bot down

restart: up

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

.PHONY: prod-build prod-up prod-check prod-logs prod-bot-up prod-telegram-login prod-telegram-up prod-backup prod-restart

prod-build:
	$(PDC) build web frontend

prod-up:
	$(PROD_DC) config --quiet
	$(PROD_DC) build web frontend
	$(PROD_DC) up -d --wait --force-recreate
	$(PROD_DC) ps

prod-restart: prod-up

prod-check:
	$(PDC) config --quiet
	$(PDC) exec web python manage.py check --deploy --fail-level WARNING
	$(PDC) exec web python manage.py makemigrations --check --dry-run

prod-logs:
	$(PROD_DC) logs --tail=100 -f

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
