# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Sprog

Svar altid på dansk. Tekniske termer og kode-identifiers forbliver på engelsk.

## Kommandoer

### Makefile (anbefalet)

```bash
make install          # Installerer både backend og frontend dependencies
make run              # Kører backend (8000) og frontend (5173) parallelt
make run-backend      # Kun backend
make run-frontend     # Kun frontend
make test-unit        # Kører pytest unit tests
make test-tournament  # Hurtig 4-bot tournament (kræver kørende backend)
make test-bot         # WebSocket bot mod backend (OPPONENT=tactical|aggressive|defensive|random)
make clean            # Sletter __pycache__, replays, node_modules, dist
```

### Manuel kørsel

```bash
# Backend (autoreload)
cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Frontend
cd frontend && npm run dev
cd frontend && npm run lint           # ESLint
cd frontend && npm run build          # tsc + vite build (typecheck + bundle)

# Single test ad gangen
cd backend && python3 -m pytest tests/test_tournament.py -v
cd backend && python3 -m pytest tests/test_tournament.py::test_round_robin_pairings -v
cd backend && python3 -m pytest tests/ -v -k "lite_mode"
```

Der er **ingen test-runner for frontend** — kvalitetskontrol sker via `npm run build` (TypeScript) og `npm run lint`.

## Arkitektur

Repoet hoster **to uafhængige game engines** der deler én FastAPI-server, replay-storage-mønster og bot-protokol:

```
backend/app/
├── main.py                 # FastAPI app: REST + WebSocket for begge spil + tournament-orchestrator
├── fleet_commander/        # 3D space combat (primær)
│   ├── models.py           # Pydantic-frie dataclasses + SHIP_CONFIGS
│   ├── engine.py           # FleetCommanderGame: turns, AP, storm, fog of war
│   ├── bot_interface.py    # FleetBot ABC, GameView, AbilityInfo, VisibleShip
│   ├── bots/               # TacticalBot, AggressiveBot, DefensiveBot, RandomBot
│   ├── websocket_bot.py    # Adapter + serializers for ekstern bot-protokol
│   ├── tournament.py       # FleetCommanderTournament, TournamentManager, divisions, scoring
│   └── replay.py           # GameRecorder, ReplayStorage, ReplayPlayer (replays/-katalog)
└── tile_tactics/           # Tile-placering for små LLM-bots (sekundær)
    ├── engine.py           # TileTacticsGame: 10x10 board, 6 piece-typer, action-id-baseret
    ├── bots.py             # RandomTileBot, GreedyTileBot, BlockingTileBot
    ├── websocket_bot.py    # Serialisering til ekstern protokol
    └── replay.py           # TileReplayStorage (tile_tactics_replays/-katalog)
```

### To spilvarianter

1. **Fleet Commander** — kompleks 3D-strategi (24×24×12 lite/small, 32×32×16 standard) med 7 skibstyper, abilities, AP, storm, fog of war.
2. **Tile Tactics** — simpelt 10×10 board hvor bots placerer polyominoer ved at vælge en `action_id` fra en `legal_actions`-liste. Designet for små LLM-bots (< 8B params) der ikke kan håndtere Fleet Commander-protokollen. **Status: proof-of-concept**, ikke feature-komplet (engine, bots og UI er minimale).

### Tournament system (kun Fleet Commander)

`tournament.py` håndterer matches via en `TournamentManager`. Hvert tournament har:
- **Format**: `round_robin` eller `single_elimination`
- **Division**: `deterministic` (ingen LLM), `open`, `local_llm` (attesteret), `tiny_model` (< 4B params attesteret) — etiketter, ikke teknisk håndhævet
- **Scoring**: `win_plus_time` (default), `win_only`, `time_tiebreaker`
- **Time budget**: per-bot tidsforbrug per match (default 60s); overskrider = forfeit af tur

Tournament-matches eksekveres i `_run_tournament_matches` (background task i `main.py`). Live game state broadcastes til spectators via WebSocket på `/ws/fleet-commander/tournament/{tournament_id}`.

> ⚠️ `_create_tournament_bot` i `main.py` har en TODO: WebSocket-bots i tournaments fallbacker til `TacticalBot`. Hvis du arbejder på tournament-features, vær opmærksom på dette hul.

### Frontend (React/TypeScript/Three.js)

`App.tsx` routerer mellem 4 views (state-baseret, ingen router-bibliotek):
- `FleetCommander3DView` — live match-spectator, 3D rendering (`@react-three/fiber`)
- `FleetCommanderTournament` — tournament-lobby + creation
- `TournamentMatchViewer` — live match viewer med WebSocket
- `TileTacticsView` — Tile Tactics-spectator

Komponenterne bruger lokal `useState` til state og taler direkte med backend via `fetch` og `WebSocket`. Der er ingen state-management bibliotek.

### REST + WebSocket endpoints

Backend eksponerer **separate routes for hver engine** under `/api/fleet-commander/*` og `/api/tile-tactics/*`. WebSocket-endpoints:
- `/ws/fleet-commander` — single match (spectator eller WebSocket-bot deltager)
- `/ws/fleet-commander/tournament/{id}` — tournament participation/spectating
- `/ws/tile-tactics` — Tile Tactics match

Spilreglerne er selvbeskrevet: `GET /api/fleet-commander/rules` og `GET /api/tile-tactics/rules`. Bots bør hente disse ved opstart.

## Fleet Commander Game Design

7 skibstyper, hver med unikke abilities og AP-pulje. **Mindre skibe = flere AP**. Se `models.py:SHIP_CONFIGS` for autoritativ kilde.

| Type      | Size | HP | Speed | AP | Rolle |
|-----------|------|----|-------|----|-------|
| Scout     | 2    | 2  | 3     | 4  | Hurtig scan, 50% stealth |
| Destroyer | 3    | 4  | 2     | 3  | Burst fire, anti-stealth |
| Cruiser   | 4    | 6  | 2     | 2  | Heavy fire, area bombardment, shield |
| Support   | 3    | 3  | 1     | 3  | Repair, jam, decoys |
| Carrier   | 5    | 8  | 1     | 2  | Long-range scan, drones |
| Artillery | 3    | 3  | 1     | 3  | Precision strike (range 12), piercing |
| Minelayer | 2    | 2  | 2     | 4  | Mines, sensors, stealth |

**Action Points**: Move = 1 AP/celle (Manhattan). Fire/abilities har individuelle costs og cooldowns (se `AbilityInfo` i `bot_interface.py`).

**Lite mode** (16×16×8, kun Destroyer/Cruiser/Support, fire+move): målrettet LLM-bots < 8B params. Aktivér via `GameConfig.lite()`.

**Storm**: efter `storm_start_turn` krymper banen periodisk; skibe udenfor tager skade. Tvinger engagement.

## Bot Development

### Interne bots (Python)

Implementér `FleetBot` ABC fra `bot_interface.py`:
- `place_fleet(config, zone_x_min, zone_x_max)` → `[(ship_type, position, direction), ...]`
- `get_actions(view: GameView)` → `[Action, ...]`
- `on_turn_result(result: TurnResult)`
- `on_game_start(config)` (hook for setup)

Tile Tactics-bots har et meget simplere interface — `choose_action(legal_actions)` returnerer en `action_id` (string).

### Eksterne bots (WebSocket)

`example_bot/`:
- `simple_bot.py` — Fleet Commander WebSocket-bot eksempel
- `llm_bot_template.py` — LLM-drevet Fleet Commander-bot (kompatibel med lite/small mode)
- `tile_tactics_prompt_agent.py` — LLM-prompt-agent til Tile Tactics

Protokollen er fuldt dokumenteret i `TOURNAMENT_README.md` — den skal være eneste kilde til protokol-detaljer.

## Tests

Testene er organiseret efter feature, ikke efter fil-struktur:

| Fil | Dækker |
|-----|--------|
| `test_tournament.py` | Pairings, formater, lifecycle |
| `test_divisions.py` | Division-etiketter |
| `test_scoring.py` | De 3 scoring-modeller |
| `test_time_budget.py` | Time budget enforcement og forfeit |
| `test_lite_mode.py` | Lite-konfiguration |
| `test_deterministic_seeding.py` | Reproducerbarhed for `deterministic` division |
| `test_llm_bot_template.py` | LLM bot-template integration |
| `test_tile_tactics_engine.py`, `test_tile_tactics_bots.py`, `test_tile_tactics_api.py` | Tile Tactics |

## GS-TDD Workflow

Følg Test-Driven Development:
1. Skriv tests først (BDD: Given-When-Then)
2. ⏸️ Vent på "godkendt" fra bruger
3. Implementér
4. Kør `make test-unit` — alle skal passe
5. Commit
