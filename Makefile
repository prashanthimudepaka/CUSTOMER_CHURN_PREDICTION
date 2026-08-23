.PHONY: setup lint format test api mlflow-ui

setup:
	python -m venv .venv && . .venv/bin/activate && pip install -r requirements-dev.txt

lint:
	ruff check .

format:
	ruff check --fix . && ruff format .

test:
	pytest

api:
	uvicorn src.api.main:app --reload

mlflow-ui:
	mlflow ui
