.PHONY: install install-backend install-frontend run run-backend run-frontend test test-bot test-unit test-tournament clean help

# Default target
help:
	@echo "SpaceBattleship - Makefile commands"
	@echo ""
	@echo "  make install        - Install all dependencies"
	@echo "  make run            - Run both backend and frontend"
	@echo "  make run-backend    - Run only backend (port 8000)"
	@echo "  make run-frontend   - Run only frontend (port 5173)"
	@echo "  make test           - Run test games"
	@echo "  make test-unit      - Run unit tests (pytest)"
	@echo "  make test-bot       - Run WebSocket bot against backend"
	@echo "  make test-tournament- Run a quick tournament (4 bots)"
	@echo "  make train          - Train RL agent"
	@echo "  make clean          - Remove generated files"
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
	@echo "Running quick tournament with 4 bots..."
	@echo "Make sure backend is running (make run-backend)"
	@echo ""
	@TID=$$(curl -s -X POST http://localhost:8000/api/fleet-commander/tournaments \
		-H "Content-Type: application/json" \
		-d '{"name":"Quick Test","include_bots":["tactical","aggressive","defensive","random"]}' \
		| python3 -c "import sys,json; print(json.load(sys.stdin)['tournament']['id'])") && \
	echo "Created tournament: $$TID" && \
	curl -s -X POST "http://localhost:8000/api/fleet-commander/tournaments/$$TID/run" > /dev/null && \
	echo "Tournament running! Waiting for completion..." && \
	sleep 10 && \
	curl -s "http://localhost:8000/api/fleet-commander/tournaments/$$TID" | python3 -c "\
import sys,json; \
t=json.load(sys.stdin)['tournament']; \
print(f\"\nTournament: {t['name']} ({t['state']})\"); \
print('Standings:'); \
for i,s in enumerate(t['standings']): \
    p=next((p for p in t['participants'] if p['id']==s['participant_id']),{}); \
    print(f\"  {i+1}. {p.get('name','?')}: {s['wins']}W-{s['losses']}L ({s['points']}pts)\")"

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
