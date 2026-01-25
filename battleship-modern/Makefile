.PHONY: install install-backend install-frontend run run-backend run-frontend test test-bot clean help

# Default target
help:
	@echo "SpaceBattleship - Makefile commands"
	@echo ""
	@echo "  make install      - Install all dependencies"
	@echo "  make run          - Run both backend and frontend"
	@echo "  make run-backend  - Run only backend (port 8000)"
	@echo "  make run-frontend - Run only frontend (port 5173)"
	@echo "  make test         - Run test games"
	@echo "  make test-bot     - Run WebSocket bot against backend"
	@echo "  make train        - Train RL agent"
	@echo "  make clean        - Remove generated files"
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
	@echo "Starting SpaceBattleship..."
	@echo "Backend: http://localhost:8000"
	@echo "Frontend: http://localhost:5173"
	@echo ""
	@make -j2 run-backend run-frontend

run-backend:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

run-frontend:
	cd frontend && npm run dev

# Run test games
test:
	@echo "Running SpaceBattleship test games..."
	@cd backend && python -c "\
from app.game.game3d import SpaceBattleshipGame; \
from app.game.player3d import HunterAI3D, RandomPlayer3D, SmartHunter3D; \
print('=== SpaceBattleship Test ==='); \
print('Grid: 12x12x8 = 1,152 cells\n'); \
smart_wins = 0; \
for i in range(10): \
    p1 = SmartHunter3D(name='SmartHunter'); \
    p2 = RandomPlayer3D(name='Random'); \
    game = SpaceBattleshipGame(player1=p1, player2=p2); \
    winner = game.play_full_game(); \
    if winner.name == 'SmartHunter': smart_wins += 1; \
print(f'SmartHunter vs Random: {smart_wins}/10 wins'); \
"

# Test WebSocket bot against backend
# Usage: make test-bot [OPPONENT=aggressive]
OPPONENT ?= tactical
test-bot:
	@echo "Testing WebSocket bot against $(OPPONENT) bot..."
	@echo "Make sure backend is running (make run-backend)"
	@echo ""
	cd example_bot && python simple_bot.py --server ws://localhost:8000 --opponent $(OPPONENT)

# Train RL agent
train:
	@echo "Training RL agent (this may take a while)..."
	cd backend && python -m app.ml.trainer

# Clean generated files
clean:
	@echo "Cleaning up..."
	rm -rf backend/app/__pycache__
	rm -rf backend/app/*/__pycache__
	rm -rf backend/models
	rm -rf backend/logs
	rm -rf backend/tensorboard_logs
	rm -rf frontend/node_modules
	rm -rf frontend/dist
	rm -rf frontend/.vite
	@echo "Done!"
