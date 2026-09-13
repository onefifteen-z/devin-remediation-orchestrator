.PHONY: backend frontend test build up down

backend:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

frontend:
	cd frontend && npm run dev

test:
	cd backend && pytest -v

build:
	docker compose build

up:
	docker compose up --build

down:
	docker compose down
