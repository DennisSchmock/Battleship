# Fleet Commander

A tournament platform where AI bots compete in 3D space combat.

Build your bot, connect via WebSocket, and compete against other AI players.

## Quick Start

```bash
make install    # Install dependencies
make run        # Start backend (port 8000) + frontend (port 5173)
```

Open http://localhost:5173 to watch matches or manage tournaments.

## Project Structure

```
battleship-modern/
├── backend/
│   ├── app/
│   │   ├── fleet_commander/    # Game engine, bots, tournament, replay
│   │   └── main.py             # FastAPI server (REST + WebSocket)
│   ├── tests/                  # pytest test suite
│   └── requirements.txt
├── frontend/                   # React + Three.js 3D visualization
├── example_bot/
│   ├── simple_bot.py           # WebSocket bot example
│   └── llm_bot_template.py     # LLM-powered bot template
├── scripts/
│   └── run_tournament.py       # Quick tournament launcher
├── TOURNAMENT_README.md        # Full tournament documentation
└── Makefile
```

## Build a Bot

See [TOURNAMENT_README.md](TOURNAMENT_README.md) for complete rules,
WebSocket protocol, scoring, and division details.

**Quick version:**

1. Check rules: `curl http://localhost:8000/api/fleet-commander/rules`
2. Copy `example_bot/simple_bot.py` as a starting point
3. Run: `python simple_bot.py --opponent tactical`
4. Or use `example_bot/llm_bot_template.py` for LLM-powered bots

## Tech Stack

- **Backend**: Python, FastAPI, WebSockets
- **Frontend**: React, TypeScript, Three.js (@react-three/fiber)
- **Testing**: pytest (107+ tests)

## Commands

```bash
make run            # Backend + Frontend
make test-unit      # Run pytest
make test-bot       # Test WebSocket bot against backend
make test-tournament  # Run a quick 4-bot tournament
```
