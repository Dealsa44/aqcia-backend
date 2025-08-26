PY=python

.PHONY: dev migrate worker test fmt lint

dev:
	uvicorn app.main:app --reload

migrate:
	alembic upgrade head

worker:
	celery -A celery_worker.celery_app worker --loglevel=info

test:
	pytest -q

fmt:
	black app tests
	isort app tests

lint:
	flake8 app tests
