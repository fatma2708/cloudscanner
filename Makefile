.PHONY: help dev-backend dev-frontend install install-backend install-frontend test lint format seed up down migrate

help:
	@echo "CloudPilot AI commands"
	@echo "  make install-backend   Install Python backend dependencies"
	@echo "  make install-frontend  Install frontend dependencies"
	@echo "  make dev-backend       Run FastAPI dev server"
	@echo "  make dev-frontend      Run Next.js dev server"
	@echo "  make test              Run backend test suite"
	@echo "  make lint              Run ruff + eslint"
	@echo "  make format            Run black/isort formatting"
	@echo "  make seed              Seed demo project data"
	@echo "  make up                Start full stack via docker-compose"
	@echo "  make down              Stop docker-compose stack"

install: install-backend install-frontend

install-backend:
	cd backend && python -m venv .venv && .venv/bin/pip install -e ".[dev]"

install-frontend:
	cd frontend && npm install

dev-backend:
	cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

dev-frontend:
	cd frontend && npm run dev

seed:
	cd backend && .venv/bin/python -m scripts.seed_demo

test:
	cd backend && .venv/bin/pytest

lint:
	cd backend && .venv/bin/ruff check app tests
	cd frontend && npm run lint

format:
	cd backend && .venv/bin/ruff format app tests

up:
	docker compose up --build

down:
	docker compose down
