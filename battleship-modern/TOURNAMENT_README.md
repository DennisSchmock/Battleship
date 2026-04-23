# Fleet Commander Tournament

Build an AI bot and compete against other bots in 3D space combat.

## Game Overview

Fleet Commander is a turn-based 3D space combat game. Two fleets battle on a
3D grid. Each ship has Action Points (AP) per turn — smaller ships get more AP.
Ships can move, fire, scan, and use unique abilities.

### Variants

| Variant | Grid | Ships | Abilities | Storm | Target Audience |
|---------|------|-------|-----------|-------|-----------------|
| **Lite** | 16×16×8 | 3 (Destroyer, Cruiser, Support) | Fire + Move only | No | Small LLMs (< 8B params) |
| **Small** | 24×24×12 | 7 (all types) | Full abilities | Yes (turn 40) | General bots |
| **Standard** | 32×32×16 | 7 (all types) | Full abilities | Yes (turn 50) | Advanced bots |

### Ship Types

| Type | Size | HP | Speed | AP | Role |
|------|------|----|-------|----|------|
| Destroyer | 3 | 4 | 2 | 3 | Burst fire, anti-stealth scan |
| Cruiser | 4 | 6 | 2 | 2 | Heavy fire (2 dmg), area bombardment, shield |
| Support | 3 | 3 | 1 | 3 | Repair allies, jam enemies, deploy decoys |
| Carrier | 5 | 8 | 1 | 2 | Long-range scan, launch drones |
| Artillery | 3 | 3 | 1 | 3 | Precision strike (range 12, 3 dmg), piercing shot |
| Minelayer | 2 | 2 | 2 | 4 | Deploy mines and sensors, stealth |
| Scout | 2 | 2 | 3 | 4 | Fast scan, stealth (50% detection evasion) |

**Lite mode uses only Destroyer, Cruiser, and Support with fire+move only.**

### Action Points

Each ship has its own AP pool per turn. Costs:
- **Move**: 1 AP per cell (Manhattan distance)
- **Fire**: 1-3 AP depending on ability
- **Abilities**: Individual AP costs (see `/api/fleet-commander/rules`)

A ship can combine actions in one turn if it has enough AP. Example: a
Destroyer (3 AP) can move 1 cell (1 AP) then fire (1 AP) then move again (1 AP).

### Storm (Full/Small only)

After `storm_start_turn`, the battlefield shrinks periodically. Ships outside
the safe zone take damage each turn. Forces engagement.

### Fog of War

Disabled by default (all ships visible). When enabled, you only see enemies
within scan range of your ships.

---

## Divisions

Tournaments can be tagged with a division — an etiquette system indicating
what kind of AI is competing:

| Division | Rules |
|----------|-------|
| `deterministic` | No LLM calls allowed. Pure algorithmic bots. |
| `open` | Anything goes — LLMs, neural nets, lookup tables. |
| `local_llm` | Participant attests that their model runs locally. |
| `tiny_model` | Participant attests parameter count < 4B. |

Divisions are not technically enforced. They exist for fair competition and
meaningful leaderboards.

---

## Scoring

Three scoring models, configurable per tournament:

### `win_plus_time` (default)
- Win = **3 points**
- Time bonus = **max(0, 30 - seconds_used)** points per match won
- A bot that wins in 10 seconds gets 3 + 20 = 23 points
- A bot that wins in 45 seconds gets 3 + 0 = 3 points

### `win_only`
- Win = **3 points**, draw = 1 point
- Time is ignored

### `time_tiebreaker`
- Win = **3 points**, draw = 1 point
- Equal points? Lower total time wins

### Time Budget

Each bot has a total time budget per match (default: 60 seconds). If your bot
exceeds its budget, its turn is forfeited (no actions executed). Budget tracks
**thinking time** — the time your bot takes to respond, not network latency.

---

## WebSocket Protocol

Connect to play a game against a built-in bot:

```
ws://host:8000/ws/fleet-commander?player1_type=websocket&player2_type=tactical
```

Query parameters:
- `player1_type` / `player2_type`: `websocket`, `tactical`, `aggressive`, `defensive`, `random`
- `delay`: ms between turns (default 500, for spectator mode)
- `small_grid`: `true` for 24×24×12 (default), `false` for 32×32×16

### Message Flow

```
Server → Client: game_start     (config, grid_size, fleet_ships)
Server → Client: place_fleet    (zone_x_min, zone_x_max)
Client → Server: fleet_placement (placements: [{ship_type, position, direction}])
─── Game loop ───
Server → Client: get_actions     (view: {turn, my_ships, visible_enemy_ships, time_remaining_ms, ...})
Client → Server: actions         (actions: [{type, ship_id, target/path, thinking_time_ms}])
Server → Client: turn_result     (result: {actions_taken, storm_damage, budget_exceeded})
─── End loop ────
Server → Client: game_end       (won: bool, reason, replay_id)
```

### `place_fleet` → `fleet_placement`

```json
{
  "type": "fleet_placement",
  "placements": [
    {"ship_type": "destroyer", "position": [2, 3, 4], "direction": "north"},
    {"ship_type": "cruiser", "position": [3, 5, 4], "direction": "east"}
  ]
}
```

Directions: `north`, `south`, `east`, `west`, `up`, `down`

Ships extend from `position` in `direction` for `size` cells. All cells must
be within your zone and the grid.

### `get_actions` → `actions`

The server sends a `get_actions` message with a full view of the game state:

```json
{
  "type": "get_actions",
  "view": {
    "turn": 15,
    "my_player_id": 0,
    "grid_size": [24, 24, 12],
    "time_remaining_ms": 45000,
    "my_ships": [
      {
        "id": "ship_0",
        "ship_type": "destroyer",
        "positions": [[2, 3, 4], [2, 4, 4], [2, 5, 4]],
        "hp": 4, "max_hp": 4,
        "action_points": 3, "max_action_points": 3,
        "can_act": true, "can_fire": true, "can_move": true,
        "fire_range": 4, "scan_range": 0,
        "abilities": {
          "fire": {"can_use": true, "ap_cost": 1, "cooldown": 0, "range": 4, "damage": 1},
          "burst_fire": {"can_use": true, "ap_cost": 2, "cooldown": 0, "range": 4, "damage": 1}
        }
      }
    ],
    "visible_enemy_ships": [
      {"id": "enemy_0", "positions": [[18, 10, 5]], "ship_type": "cruiser"}
    ],
    "storm": {
      "min": [2, 2, 1], "max": [21, 21, 10],
      "turns_until_shrink": 5, "damage": 1
    }
  }
}
```

Respond with:

```json
{
  "type": "actions",
  "actions": [
    {"type": "fire", "ship_id": "ship_0", "target": [18, 10, 5]},
    {"type": "move", "ship_id": "ship_1", "path": [[5, 6, 4], [6, 6, 4]]}
  ],
  "thinking_time_ms": 150
}
```

Action types:
- `fire`: `{"type": "fire", "ship_id": "ID", "target": [x, y, z]}`
- `move`: `{"type": "move", "ship_id": "ID", "path": [[x,y,z], [x2,y2,z2], ...]}`
- `scan`: `{"type": "scan", "ship_id": "ID", "center": [x, y, z]}`
- `ability`: `{"type": "ability", "ship_id": "ID", "ability": "burst_fire", "target": [x,y,z]}`

`thinking_time_ms` is optional — if provided, it's subtracted from your time
budget. If omitted, server uses wall-clock time.

### `turn_result`

```json
{
  "type": "turn_result",
  "result": {
    "turn": 15,
    "player_id": 0,
    "budget_exceeded": false,
    "thinking_time_ms": 150,
    "actions_taken": [
      {"success": true, "message": "Hit!", "damage_dealt": 1, "ships_hit": ["enemy_0"]}
    ],
    "storm_damage": {}
  }
}
```

### `game_end`

```json
{
  "type": "game_end",
  "won": true,
  "reason": "All enemy ships destroyed",
  "replay_id": "abc123"
}
```

---

## How to Participate

### 1. Check the rules

```bash
curl http://localhost:8000/api/fleet-commander/rules | python -m json.tool
```

### 2. Pick your approach

- **Algorithmic bot**: See `example_bot/simple_bot.py` (WebSocket protocol demo)
- **LLM-powered bot**: See `example_bot/llm_bot_template.py` (prompt formatting, JSON parsing, fallback)
- **Start with Lite**: Use `GameConfig.lite()` / small grid for faster iteration

### 3. Connect and play

```bash
# Install deps
pip install websockets

# Run against TacticalBot
python example_bot/simple_bot.py --server ws://localhost:8000 --opponent tactical
```

### 4. Join a tournament

Tournaments are created via the REST API or frontend UI. Your bot connects via
WebSocket with `role=participant`:

```
ws://host:8000/ws/fleet-commander/tournament/{id}?role=participant&bot_name=MyBot
```

### 5. Iterate

- Watch replays in the frontend
- Check `/api/fleet-commander/replays/{id}` for full game data
- Test against different opponents: `tactical`, `aggressive`, `defensive`, `random`

---

## API Reference

### REST Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Health check |
| GET | `/api/fleet-commander/bot-types` | List built-in bot types |
| GET | `/api/fleet-commander/rules` | Full game rules and ship configs |
| GET | `/api/fleet-commander/replays` | List saved replays |
| GET | `/api/fleet-commander/replays/{id}` | Get replay data |
| POST | `/api/fleet-commander/tournaments` | Create tournament |
| GET | `/api/fleet-commander/tournaments` | List tournaments |
| GET | `/api/fleet-commander/tournaments/{id}` | Tournament details |
| GET | `/api/fleet-commander/tournaments/{id}/live` | Live match state |
| POST | `/api/fleet-commander/tournaments/{id}/add-bot` | Add internal bot |
| POST | `/api/fleet-commander/tournaments/{id}/start` | Start tournament |
| POST | `/api/fleet-commander/tournaments/{id}/run` | Run to completion |
| DELETE | `/api/fleet-commander/tournaments/{id}` | Delete tournament |

### WebSocket Endpoints

| Path | Description |
|------|-------------|
| `/ws/fleet-commander` | Play or watch a single game |
| `/ws/fleet-commander/tournament/{id}` | Tournament participation/spectating |

---

## Running the Server

```bash
make install    # Install dependencies
make run        # Start backend (8000) + frontend (5173)
make test-unit  # Run tests
make test-bot   # Test WebSocket bot (requires running backend)
```
