# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Sprog

Svar altid på dansk. Tekniske termer og kode-identifiers forbliver på engelsk.

## Kommandoer

### Makefile (anbefalet)

```bash
make install          # Installerer både backend og frontend dependencies
make run              # Kører backend (port 8000) og frontend (port 5173) parallelt
make run-backend      # Kun backend
make run-frontend     # Kun frontend
make test-unit        # Kører pytest unit tests (backend/tests/)
make test-tournament  # Kører en hurtig tournament test (kræver kørende backend)
make test-bot         # Test WebSocket bot mod backend (OPPONENT=tactical|aggressive|defensive|random)
make train            # Træner RL agent (stable-baselines3)
```

### Manuel kørsel

```bash
# Backend
cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Frontend
cd frontend && npm run dev

# Tests
cd backend && python3 -m pytest tests/ -v
cd backend && python3 -m pytest tests/test_tournament.py -v -k "test_name"

# Lint frontend
cd frontend && npm run lint
```

## Arkitektur

### Backend (Python/FastAPI)

Tre separate spil-engines med stigende kompleksitet:

1. **Classic 2D Battleship** (`app/game/`)
   - Standard 10×10 grid, traditionel Battleship
   - `board.py`, `ship.py`, `player.py`, `game.py`

2. **3D SpaceBattleship** (`app/game/*3d.py`)
   - 12×12×8 grid (1,152 celler), 6 retninger
   - Samme gameplay som 2D, bare i 3D

3. **Strategic SpaceBattleship** (`app/strategic/`)
   - Fire/Move/Scan actions, skibe kan bevæge sig
   - `engine.py` håndterer spilflow
   - Bots i `bots/`: RandomBot, HunterBot, ScoutBot, EvasiveBot, PredictorBot

4. **Fleet Commander** (`app/fleet_commander/`) - HOVEDSPILLET
   - 24×24×12 (small) eller 32×32×16 (standard) grid
   - 7 skibstyper med unikke abilities (se `models.py:SHIP_CONFIGS`)
   - Action Points system: små skibe har flere AP end store
   - Storm mechanic der gradvist krymper banen
   - Fuld replay-system (`replay.py`)
   - Tournament system (`tournament.py`)
   - WebSocket bot interface for eksterne AI bots

### Frontend (React/TypeScript/Three.js)

- **Vite** som build tool
- **Three.js** via `@react-three/fiber` og `@react-three/drei` til 3D rendering
- Views i `src/components/`:
  - `FleetCommander3DView.tsx` - Hovedspillet
  - `FleetCommanderTournament.tsx` - Tournament UI
  - `Strategic3DBoard.tsx` - 3D rendering komponent

### WebSocket API

Fleet Commander bot protokol (`/ws/fleet-commander`):

```
Query params: player1_type=websocket&player2_type=tactical
Server -> Client: game_start, place_fleet, get_actions, turn_result, game_end
Client -> Server: fleet_placement, actions
```

Se `/api/fleet-commander/rules` for komplet spiloversigt.

## Fleet Commander Game Design

### Ship Types (fra `models.py`)

| Type | Size | HP | Speed | AP | Rolle |
|------|------|----|----|----|----|
| Destroyer | 3 | 4 | 2 | 3 | Burst fire, anti-stealth |
| Cruiser | 4 | 6 | 2 | 2 | Heavy fire, area bombardment, shield |
| Support | 3 | 3 | 1 | 3 | Repair, jam, decoys |
| Carrier | 5 | 8 | 1 | 2 | Long-range scan, drones |
| Artillery | 3 | 3 | 1 | 3 | Precision strike (12 range), piercing |
| Minelayer | 2 | 2 | 2 | 4 | Mines, sensors, stealth |

### Action Points

Hvert skib har sine egne AP per tur. Mindre skibe = flere AP.
- Move: 1 AP per celle
- Fire: Varierer (se ability configs)
- Abilities har individuelle AP costs og cooldowns

## Bot Development

Interne bots implementerer `BotInterface` fra `app/fleet_commander/bot_interface.py`:
- `place_fleet(config, zone_x_min, zone_x_max)` → ship placements
- `get_actions(view: GameView)` → list of actions
- `on_turn_result(result: TurnResult)`

Se `example_bot/simple_bot.py` for WebSocket bot eksempel.

## GS-TDD Workflow

Følg Test-Driven Development:
1. Skriv tests først (BDD: Given-When-Then)
2. Vent på godkendelse
3. Implementér
4. Kør tests - alle skal passe
