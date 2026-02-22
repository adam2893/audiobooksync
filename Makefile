.PHONY: help build push run stop logs clean test lint format install dev

help:
	@echo "AudioBook Sync - Available Commands"
	@echo ""
	@echo "Development:"
	@echo "  make install      - Install Python dependencies"
	@echo "  make dev         - Run application in development mode"
	@echo "  make lint        - Run code linter (pylint)"
	@echo "  make format      - Format code with black"
	@echo "  make test        - Run tests"
	@echo ""
	@echo "Docker:"
	@echo "  make build       - Build Docker image locally"
	@echo "  make run         - Run Docker container (interactive)"
	@echo "  make stop        - Stop running container"
	@echo "  make logs        - View container logs"
	@echo "  make push        - Push image to registry"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean       - Remove build artifacts and cache"
	@echo "  make clean-db    - Remove SQLite database (WARNING: deletes all data)"

# Development targets
install:
	pip install -r requirements.txt

dev:
	@export $$(cat .env | xargs) && python -m src.main

lint:
	pylint src/ || true

format:
	black src/ tests/

test:
	pytest tests/ -v

# Docker targets
build:
	docker build -f docker/Dockerfile -t audiobook-sync:latest .

run:
	@if [ ! -f .env ]; then cp .env.example .env; echo "Created .env file - please configure it"; exit 1; fi
	docker compose up

stop:
	docker compose down

logs:
	docker compose logs -f audiobook-sync

push:
	docker push ghcr.io/adam2893/audiobooksync:latest

# Build and run locally (for testing)
build-local:
	docker build -f docker/Dockerfile -t audiobook-sync:local .

run-local:
	@if [ ! -f .env ]; then cp .env.example .env; echo "Created .env file - please configure it"; exit 1; fi
	docker run -d \
		--name audiobook-sync-local \
		-p 8000:8000 \
		-v audiobook-sync-data:/data \
		--env-file .env \
		audiobook-sync:local
	@echo "Container started! Access UI at http://localhost:8000"

stop-local:
	docker stop audiobook-sync-local && docker rm audiobook-sync-local

# Cleanup targets
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + || true
	rm -rf .pytest_cache/ .coverage htmlcov/ dist/ build/

clean-db:
	@echo "WARNING: This will delete all sync data and mappings!"
	@read -p "Are you sure? (y/N) " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		rm -f data/sync.db; \
		echo "Database deleted"; \
	else \
		echo "Cancelled"; \
	fi

clean-all: clean clean-docker
	rm -rf venv/

clean-docker:
	docker compose down -v
	docker rmi audiobook-sync:latest audiobook-sync:local 2>/dev/null || true

# Quick setup
setup:
	@echo "Setting up AudioBook Sync..."
	@if [ ! -f .env ]; then cp .env.example .env; fi
	@echo "✓ Created .env file"
	@echo ""
	@echo "Next steps:"
	@echo "1. Edit .env with your credentials"
	@echo "2. Run 'make run' to start the application"
	@echo "3. Visit http://localhost:8000 to configure"

# Build and push to registry (CI/CD style)
ci-build: clean
	docker build -f docker/Dockerfile -t ghcr.io/adam2893/audiobooksync:latest .

ci-push: ci-build
	docker push ghcr.io/adam2893/audiobooksync:latest

# Git helpers
git-status:
	git status

git-push:
	git add -A && git commit -m "Updates" && git push origin main
