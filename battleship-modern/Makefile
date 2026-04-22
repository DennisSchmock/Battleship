.PHONY: install install-backend install-frontend run run-backend run-frontend test-unit test-bot test-tournament clean help

# Default target
help:
	@echo "Fleet Commander - Makefile commands"
	@echo ""
	@echo "  make install          - Install all dependencies"
	@echo "  make run              - Run both backend and frontend"
	@echo "  make run-backend      - Run only backend (port 8000)"
	@echo "  make run-frontend     - Run only frontend (port 5173)"
	@echo "  make test-unit        - Run unit tests (pytest)"
	@echo "  make test-bot         - Run WebSocket bot against backend"
	@echo "  make test-tournament  - Run a quick tournament (4 bots)"
	@echo "  make clean            - Remove generated files"
	@echo ""

# Install all dependencies
install: install-backend install-frontend

install-backend:
	@echo "Installing backend dependencies..."
	cd backend && pip install -r requirements.txt

install-frontend:
	@echo "Installing frontend dependencies..."
	cd frontend && npm install

# Run services
run:
	@echo "Starting Fleet Commander..."
	@echo "Backend: http://localhost:8000"
	@echo "Frontend: http://localhost:5173"
	@echo ""
	@make -j2 run-backend run-frontend

run-backend:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

run-frontend:
	cd frontend && npm run dev

# Run unit tests
test-unit:
	@echo "Running unit tests..."
	cd backend && python3 -m pytest tests/ -v

# Test WebSocket bot against backend
# Usage: make test-bot [OPPONENT=aggressive]
OPPONENT ?= tactical
test-bot:
	@echo "Testing WebSocket bot against $(OPPONENT) bot..."
	@echo "Make sure backend is running (make run-backend)"
	@echo ""
	cd example_bot && python3 simple_bot.py --server ws://localhost:8000 --opponent $(OPPONENT)

# Run a quick tournament with 4 internal bots
test-tournament:
	@echo "Make sure backend is running (make run-backend)"
	@echo ""
	python3 scripts/run_tournament.py

# Clean generated files
clean:
	@echo "Cleaning up..."
	rm -rf backend/app/__pycache__
	rm -rf backend/app/*/__pycache__
	rm -rf backend/replays
	rm -rf frontend/node_modules
	rm -rf frontend/dist
	rm -rf frontend/.vite
	@echo "Done!"
