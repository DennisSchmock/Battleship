# SpaceBattleship AI Tournament

A modern browser-based 3D Battleship game featuring AI vs AI tournaments with Reinforcement Learning.

## Features

- **3D Game Engine**: Full SpaceBattleship in a 12×12×8 grid (1,152 cells!)
- **Three.js Visualization**: Rotatable 3D battlefield with real-time updates
- **Multiple AI Types**:
  - **Random AI**: Baseline that shoots randomly in 3D space
  - **Hunter AI**: 3D checkerboard pattern + 6-directional hunting
  - **Smart Hunter**: Directional tracking with line continuation
  - **RL Agent**: Deep Q-Network trained through self-play
- **Tournament System**: Round-robin tournaments with real-time updates
- **Modern UI**: React + TypeScript + Three.js frontend
- **ML Training**: Gymnasium-compatible 3D environment for RL training
- **Classic Mode**: Traditional 10×10 2D Battleship also available

## Project Structure

```
battleship-modern/
├── backend/
│   ├── app/
│   │   ├── game/              # Game engines
│   │   │   ├── board.py       # 2D Board logic
│   │   │   ├── board3d.py     # 3D Board (12×12×8)
│   │   │   ├── ship.py        # 2D Ship class
│   │   │   ├── ship3d.py      # 3D Ship (6 orientations)
│   │   │   ├── player.py      # 2D AI players
│   │   │   ├── player3d.py    # 3D AI players
│   │   │   ├── game.py        # 2D Game controller
│   │   │   └── game3d.py      # 3D Game controller
│   │   ├── ml/                # Machine Learning
│   │   │   ├── environment.py     # 2D Gymnasium env
│   │   │   ├── environment3d.py   # 3D Gymnasium env
│   │   │   ├── rl_player.py       # RL-based player
│   │   │   └── trainer.py         # Training script
│   │   ├── api/               # API layer
│   │   │   └── tournament.py  # Tournament logic
│   │   └── main.py            # FastAPI app
│   └── requirements.txt
└── frontend/
    ├── src/
    │   ├── components/
    │   │   ├── SpaceBoard.tsx      # Three.js 3D board
    │   │   ├── SpaceGameView.tsx   # 3D game view
    │   │   ├── GameBoard.tsx       # 2D board
    │   │   └── GameView.tsx        # 2D game view
    │   ├── App.tsx            # Main app
    │   └── main.tsx           # Entry point
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
- **Frontend**: React, TypeScript, Vite, Three.js
- **3D Rendering**: @react-three/fiber, @react-three/drei
- **Styling**: CSS with custom properties

## The 3D Challenge

Going from 2D (100 cells) to 3D (1,152 cells) changes the game dramatically:

| Aspect | 2D Classic | 3D Space |
|--------|-----------|----------|
| Grid | 10×10 | 12×12×8 |
| Cells | 100 | 1,152 |
| Directions | 4 | 6 |
| Ship orientations | 2 | 6 |
| Neighbor cells | 4 | 6 |

The Hunter AI adapts by using a 3D checkerboard pattern `(x + y + z) % 2 == 0`
for efficient search, then hunts in all 6 directions when a hit is found.

## Legacy

This is a modern reimagining of a Java Battleship AI from university days (2010s).
The original "R58" bot featured adaptive heat-map based ship placement and
hunting strategies that nearly beat the instructor's secret bot in tournament play.
