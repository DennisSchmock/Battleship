# Battleship AI Tournament

A modern browser-based Battleship game featuring AI vs AI tournaments with Reinforcement Learning.

## Features

- **Game Engine**: Full Battleship implementation in Python
- **Multiple AI Types**:
  - **Random AI**: Baseline that shoots randomly
  - **Hunter AI**: Systematically hunts ships after getting a hit
  - **RL Agent**: Deep Q-Network trained through self-play
- **Tournament System**: Round-robin tournaments with real-time updates
- **Modern UI**: React + TypeScript frontend with WebSocket updates
- **ML Training**: Gymnasium-compatible environment for RL training

## Project Structure

```
battleship-modern/
├── backend/
│   ├── app/
│   │   ├── game/          # Game engine
│   │   │   ├── board.py   # Board logic
│   │   │   ├── ship.py    # Ship class
│   │   │   ├── player.py  # AI players
│   │   │   └── game.py    # Game controller
│   │   ├── ml/            # Machine Learning
│   │   │   ├── environment.py  # Gymnasium env
│   │   │   ├── rl_player.py    # RL-based player
│   │   │   └── trainer.py      # Training script
│   │   ├── api/           # API layer
│   │   │   └── tournament.py   # Tournament logic
│   │   └── main.py        # FastAPI app
│   └── requirements.txt
└── frontend/
    ├── src/
    │   ├── components/    # React components
    │   ├── App.tsx        # Main app
    │   └── main.tsx       # Entry point
    └── package.json
```

## Getting Started

### Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the server
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Run dev server
npm run dev
```

Open http://localhost:5173 in your browser.

## Training the RL Agent

```bash
cd backend
python -m app.ml.trainer
```

This will:
1. Train a DQN agent for 200,000 timesteps
2. Save the best model to `./models/best/`
3. Evaluate and print performance metrics

## API Endpoints

- `GET /api/player-types` - List available AI types
- `POST /api/tournaments` - Create a new tournament
- `GET /api/tournaments/{id}` - Get tournament status
- `POST /api/tournaments/{id}/start` - Start a tournament
- `POST /api/quick-game` - Play a single game
- `WS /ws/tournament/{id}` - Real-time tournament updates
- `WS /ws/game` - Real-time game visualization

## Tech Stack

- **Backend**: Python, FastAPI, WebSockets
- **ML**: PyTorch, Stable-Baselines3, Gymnasium
- **Frontend**: React, TypeScript, Vite
- **Styling**: CSS with custom properties

## Legacy

This is a modern reimagining of a Java Battleship AI from university days.
The original featured adaptive heat-map based ship placement and hunting strategies.
