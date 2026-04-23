"""Fleet Commander Tournament Server."""
import asyncio
from contextlib import asynccontextmanager
from typing import List, Optional, Tuple
import json
import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .fleet_commander import (
    FleetCommanderGame, GamePhase as FCGamePhase, GameConfig as FCGameConfig,
    Position as FCPosition, Direction as FCDirection, ShipType,
    MoveAction as FCMoveAction, FireAction as FCFireAction,
    ScanAction as FCScanAction, AbilityAction, AbilityType
)
from .fleet_commander.bot_interface import create_game_view
from .fleet_commander.bots import TacticalBot, AggressiveBot, DefensiveBot, RandomBot
from .fleet_commander.replay import GameRecorder, ReplayStorage, ReplayPlayer
from .fleet_commander.websocket_bot import WebSocketBotAdapter, serialize_config
from .fleet_commander.tournament import (
    FleetCommanderTournament, TournamentManager, TournamentFormat,
    TournamentState, MatchState, MatchResult, Participant
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for the application."""
    print("Fleet Commander Tournament Server starting...")
    yield
    print("Fleet Commander Tournament Server shutting down...")


app = FastAPI(
    title="Fleet Commander Tournament",
    description="AI bot tournament platform for Fleet Commander",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Replay storage
replay_storage = ReplayStorage("replays")

# Tournament manager
tournament_manager = TournamentManager()

FLEET_BOTS = {
    "tactical": TacticalBot,
    "aggressive": AggressiveBot,
    "defensive": DefensiveBot,
    "random": RandomBot,
}


# === REST API ===

@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "message": "Fleet Commander Tournament Server"}


@app.get("/api/fleet-commander/bot-types")
async def get_fleet_bot_types():
    """Get available Fleet Commander bot types."""
    return {
        "types": [
            {"id": "tactical", "name": "Tactical Bot", "description": "Uses all ship abilities strategically"},
            {"id": "aggressive", "name": "Aggressive Bot", "description": "Focuses on maximum firepower and pushing forward"},
            {"id": "defensive", "name": "Defensive Bot", "description": "Prioritizes survival, shields and repairs"},
            {"id": "random", "name": "Random Bot", "description": "Baseline - takes random actions"},
        ]
    }


@app.get("/api/fleet-commander/rules")
async def get_fleet_commander_rules():
    """Get Fleet Commander game rules and ship configurations."""
    from .fleet_commander.models import SHIP_CONFIGS, ShipType, AbilityType

    ship_info = {}
    for ship_type, config in SHIP_CONFIGS.items():
        abilities = {}
        for ability in config.abilities:
            abilities[ability.ability_type.value] = {
                "ap_cost": ability.ap_cost,
                "cooldown": ability.cooldown,
                "range": ability.range,
                "damage": ability.damage,
                "area_size": ability.area_size,
                "description": ability.description,
            }

        ship_info[ship_type.value] = {
            "name": config.name,
            "size": config.size,
            "hp": config.hp,
            "speed": config.speed,
            "action_points": config.action_points,
            "fire_range": config.fire_range,
            "fire_damage": config.fire_damage,
            "scan_range": config.scan_range,
            "abilities": abilities,
        }

    return {
        "game_name": "Fleet Commander",
        "grid_sizes": {
            "small": {"x": 24, "y": 24, "z": 12},
            "standard": {"x": 32, "y": 32, "z": 16},
        },
        "ship_types": ship_info,
        "mechanics": {
            "action_points": "Each ship has its own AP pool per turn. Smaller ships get more AP.",
            "fog_of_war": "You can only see enemy ships within scan range of your ships.",
            "storm": "After storm_start_turn, the battlefield shrinks periodically. Ships outside take damage.",
            "abilities": "Each ship type has unique abilities with AP costs and cooldowns.",
        },
        "bot_protocol": {
            "connect": "ws://host:port/ws/fleet-commander?player1_type=websocket&player2_type=aggressive",
            "messages": {
                "game_start": "Server sends game config",
                "place_fleet": "Server requests fleet placement",
                "fleet_placement": "Client sends ship positions",
                "get_actions": "Server sends game view, expects actions",
                "actions": "Client sends list of actions",
                "turn_result": "Server sends result of actions",
                "game_end": "Server sends final result",
            }
        },
    }


@app.get("/api/fleet-commander/replays")
async def get_replays():
    """List available replays."""
    return {"replays": replay_storage.list_replays()}


@app.get("/api/fleet-commander/replays/{replay_id}")
async def get_replay(replay_id: str):
    """Get a specific replay."""
    replay = replay_storage.load(replay_id)
    if not replay:
        raise HTTPException(status_code=404, detail="Replay not found")
    return replay.to_dict()


# === Tournament REST API ===

class FleetTournamentConfig(BaseModel):
    name: str
    format: str = "round_robin"
    use_small_grid: bool = True
    max_participants: int = 8


@app.post("/api/fleet-commander/tournaments")
async def create_fleet_tournament(config: FleetTournamentConfig):
    """Create a new Fleet Commander tournament."""
    tournament = tournament_manager.create_tournament(
        name=config.name,
        format=config.format,
        use_small_grid=config.use_small_grid,
        max_participants=config.max_participants,
    )
    return {"tournament_id": tournament.id, "tournament": tournament.to_dict()}


@app.get("/api/fleet-commander/tournaments")
async def list_fleet_tournaments():
    """List all tournaments."""
    return {"tournaments": [t.to_dict() for t in tournament_manager.list_tournaments()]}


@app.get("/api/fleet-commander/tournaments/{tournament_id}")
async def get_fleet_tournament(tournament_id: str):
    """Get tournament details."""
    tournament = tournament_manager.get_tournament(tournament_id)
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")
    return tournament.to_dict()


@app.get("/api/fleet-commander/tournaments/{tournament_id}/live")
async def get_live_match(tournament_id: str):
    """Get the current live game state for a tournament."""
    tournament = tournament_manager.get_tournament(tournament_id)
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")
    return {
        "live_game_state": tournament.live_game_state,
        "current_match": tournament.current_match.to_dict() if tournament.current_match else None,
    }


@app.post("/api/fleet-commander/tournaments/{tournament_id}/add-bot")
async def add_bot_to_tournament(tournament_id: str, bot_type: str = "tactical", bot_name: Optional[str] = None):
    """Add an internal bot to a tournament."""
    tournament = tournament_manager.get_tournament(tournament_id)
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")

    if bot_type not in FLEET_BOTS:
        raise HTTPException(status_code=400, detail=f"Unknown bot type: {bot_type}")

    name = bot_name or f"{bot_type.title()}Bot"
    participant = tournament.add_participant(
        name=name,
        is_internal_bot=True,
        internal_bot_type=bot_type,
    )
    if not participant:
        raise HTTPException(status_code=400, detail="Could not add bot (tournament full?)")

    tournament.set_participant_ready(participant.id, True)
    return {"participant": participant.to_dict(), "tournament": tournament.to_dict()}


@app.post("/api/fleet-commander/tournaments/{tournament_id}/start")
async def start_fleet_tournament(tournament_id: str):
    """Start a tournament (all participants must be ready)."""
    tournament = tournament_manager.get_tournament(tournament_id)
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")

    if not tournament.can_start():
        raise HTTPException(status_code=400, detail="Cannot start: need at least 2 ready participants")

    tournament.start()
    return {"message": "Tournament started", "tournament": tournament.to_dict()}


@app.delete("/api/fleet-commander/tournaments/{tournament_id}")
async def delete_tournament(tournament_id: str):
    """Delete a tournament."""
    if not tournament_manager.delete_tournament(tournament_id):
        raise HTTPException(status_code=404, detail="Tournament not found")
    return {"deleted": True}


# === WebSocket: Single Game ===

async def _run_fleet_commander_with_ws_bot(
    websocket: WebSocket,
    ws_player_id: int,
    player1_type: str,
    player2_type: str,
    delay: float,
    use_small: bool
):
    """Run Fleet Commander game with external WebSocket bot as a player."""
    from .fleet_commander.websocket_bot import (
        deserialize_position, deserialize_direction, deserialize_ship_type, deserialize_action
    )

    config = FCGameConfig.small() if use_small else FCGameConfig()

    other_player_id = 1 - ws_player_id
    other_type = player2_type if ws_player_id == 0 else player1_type
    other_bot_class = FLEET_BOTS.get(other_type, TacticalBot)
    other_bot = other_bot_class()
    other_bot.on_game_start(config)

    game = FleetCommanderGame(config=config)

    await websocket.send_json({
        "type": "game_start",
        "config": serialize_config(config)
    })

    zone = config.player1_zone if ws_player_id == 0 else config.player2_zone
    await websocket.send_json({
        "type": "place_fleet",
        "zone_x_min": zone[0],
        "zone_x_max": zone[1]
    })

    response = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
    placement_data = json.loads(response)

    if placement_data.get("type") != "fleet_placement":
        await websocket.send_json({"type": "error", "message": f"Expected fleet_placement, got {placement_data.get('type')}"})
        return

    ws_placements = []
    for p in placement_data["placements"]:
        ship_type = deserialize_ship_type(p["ship_type"])
        position = deserialize_position(p["position"])
        direction = deserialize_direction(p["direction"])
        ws_placements.append((ship_type, position, direction))

    other_zone = config.player2_zone if ws_player_id == 0 else config.player1_zone
    other_placements = other_bot.place_fleet(config, other_zone[0], other_zone[1])

    if ws_player_id == 0:
        game.setup_fleet(0, ws_placements)
        game.setup_fleet(1, other_placements)
        game.players[0].name = "WebSocketBot"
        game.players[1].name = other_bot.get_name()
    else:
        game.setup_fleet(0, other_placements)
        game.setup_fleet(1, ws_placements)
        game.players[0].name = other_bot.get_name()
        game.players[1].name = "WebSocketBot"

    game.start_game()

    recorder = GameRecorder(config, game.players[0].name, game.players[1].name)
    recorder.record_initial_state(
        [s.to_dict() for s in game.players[0].ships],
        [s.to_dict() for s in game.players[1].ships]
    )

    max_turns = config.max_turns

    while game.phase == FCGamePhase.PLAYING and game.turn < max_turns:
        current_player_idx = game.current_player_idx

        state_dict = game.get_visible_state(current_player_idx)
        view = create_game_view(state_dict)

        if current_player_idx == ws_player_id:
            view_dict = _create_view_dict(view, state_dict)

            await websocket.send_json({
                "type": "get_actions",
                "view": view_dict
            })

            response = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            actions_data = json.loads(response)

            if actions_data.get("type") != "actions":
                await websocket.send_json({"type": "error", "message": f"Expected actions, got {actions_data.get('type')}"})
                return

            actions = [deserialize_action(a) for a in actions_data.get("actions", [])]
        else:
            actions = other_bot.get_actions(view)

        recorder.record_actions(game.turn, current_player_idx, actions)
        result = game.execute_turn(actions)

        full_state = {
            "player1_ships": [s.to_dict() for s in game.players[0].ships],
            "player2_ships": [s.to_dict() for s in game.players[1].ships],
            "storm_bounds": (
                game.storm.current_bounds[0].to_tuple(),
                game.storm.current_bounds[1].to_tuple()
            ) if game.storm else None
        }
        recorder.record_turn_result(result, full_state)

        if current_player_idx == ws_player_id:
            result_dict = {
                "turn": result.turn,
                "player_id": result.player_id,
                "actions_taken": [
                    {
                        "success": ar.success,
                        "message": ar.message,
                        "damage_dealt": ar.damage_dealt,
                        "ships_hit": ar.ships_hit,
                        "ships_destroyed": ar.ships_destroyed,
                    }
                    for ar in result.actions_taken
                ],
                "storm_damage": result.storm_damage_taken,
                "storm_shrunk": result.storm_shrunk,
            }
            await websocket.send_json({
                "type": "turn_result",
                "result": result_dict
            })
        else:
            other_bot.on_turn_result(result)

        await asyncio.sleep(delay)

    winner_id = game.winner if game.winner is not None else -1
    ws_won = (winner_id == ws_player_id)

    recorder.record_game_end(winner_id, {
        "player1_ships": [s.to_dict() for s in game.players[0].ships],
        "player2_ships": [s.to_dict() for s in game.players[1].ships],
    })

    replay_id = replay_storage.save(recorder.get_replay())

    if winner_id >= 0:
        loser_id = 1 - winner_id
        loser_fleet_destroyed = all(s.is_destroyed for s in game.players[loser_id].ships)

        if ws_won:
            reason = "All enemy ships destroyed" if loser_fleet_destroyed else "More ships remaining"
        else:
            reason = "Your fleet was destroyed" if loser_fleet_destroyed else "Fewer ships remaining"
    else:
        reason = "Draw"

    await websocket.send_json({
        "type": "game_end",
        "won": ws_won,
        "reason": reason,
        "replay_id": replay_id
    })


def _create_view_dict(view, state_dict) -> dict:
    """Create JSON-serializable view dict for WebSocket bot."""
    from .fleet_commander.websocket_bot import serialize_position
    from .fleet_commander.models import AbilityType

    return {
        "turn": view.turn,
        "my_player_id": view.my_player_id,
        "grid_size": list(view.grid_size),
        "my_ships": [
            {
                "id": s.id,
                "positions": [serialize_position(p) for p in s.positions],
                "ship_type": s.ship_type.value if s.ship_type else None,
                "hp": s.hp,
                "max_hp": s.max_hp,
                "speed": s.speed,
                "movement_remaining": s.movement_remaining,
                "action_points": s.action_points,
                "max_action_points": s.max_action_points,
                "has_acted": s.has_acted,
                "can_act": s.can_act(),
                "can_fire": s.can_fire(),
                "can_scan": s.can_scan(),
                "can_move": s.can_move(),
                "fire_range": s.get_fire_range(),
                "scan_range": s.get_scan_range(),
                "abilities": {
                    k.value: {
                        "can_use": v.can_use,
                        "ap_cost": v.ap_cost,
                        "cooldown": v.cooldown_remaining,
                        "range": v.range,
                        "damage": v.damage,
                        "area_size": v.area_size,
                    }
                    for k, v in (s.ability_info or {}).items()
                }
            }
            for s in view.my_ships
        ],
        "visible_enemy_ships": [
            {
                "id": s.id,
                "positions": [serialize_position(p) for p in s.positions],
                "ship_type": s.ship_type.value if s.ship_type else None,
            }
            for s in view.visible_enemy_ships
        ],
        "my_mines": [[m[0], serialize_position(m[1])] for m in view.my_mines],
        "my_sensors": [[s[0], serialize_position(s[1])] for s in view.my_sensors],
        "my_decoys": [[d[0], serialize_position(d[1])] for d in view.my_decoys],
        "my_drones": [[d[0], serialize_position(d[1]), d[2]] for d in view.my_drones],
        "storm": {
            "min": serialize_position(view.storm_min) if view.storm_min else None,
            "max": serialize_position(view.storm_max) if view.storm_max else None,
            "turns_until_shrink": view.storm_turns_until_shrink,
            "damage": view.storm_damage
        } if view.storm_min else None
    }


@app.websocket("/ws/fleet-commander")
async def fleet_commander_websocket(
    websocket: WebSocket,
    player1_type: str = "tactical",
    player2_type: str = "tactical",
    delay: int = 500,
    small_grid: bool = True
):
    """WebSocket for Fleet Commander game.

    Query params:
    - player1_type: Bot type or 'websocket' for external bot
    - player2_type: Bot type or 'websocket' for external bot
    - delay: Delay between turns in ms (default 500)
    - small_grid: Use small grid (default true)
    """
    await websocket.accept()

    delay_sec = delay / 1000.0
    use_small = small_grid

    ws_player_id = None
    if player1_type == "websocket":
        ws_player_id = 0
    elif player2_type == "websocket":
        ws_player_id = 1

    try:
        if ws_player_id is not None:
            await _run_fleet_commander_with_ws_bot(
                websocket, ws_player_id, player1_type, player2_type, delay_sec, use_small
            )
            return

        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if message.get("action") == "start_game":
                p1_type = message.get("player1_type", player1_type)
                p2_type = message.get("player2_type", player2_type)
                delay_sec = message.get("delay", delay) / 1000.0
                use_small = message.get("small_grid", small_grid)

                config = FCGameConfig.small() if use_small else FCGameConfig()

                bot1_class = FLEET_BOTS.get(p1_type, TacticalBot)
                bot2_class = FLEET_BOTS.get(p2_type, TacticalBot)
                bot1 = bot1_class()
                bot2 = bot2_class()
                bot1.on_game_start(config)
                bot2.on_game_start(config)

                game = FleetCommanderGame(config=config)

                game.auto_place_fleet(0)
                game.auto_place_fleet(1)
                game.players[0].name = bot1.get_name()
                game.players[1].name = bot2.get_name()
                game.start_game()

                recorder = GameRecorder(config, game.players[0].name, game.players[1].name)
                recorder.record_initial_state(
                    [s.to_dict() for s in game.players[0].ships],
                    [s.to_dict() for s in game.players[1].ships]
                )

                await websocket.send_json({
                    "type": "game_start",
                    "data": {
                        "replay_id": recorder.replay.replay_id,
                        "config": {
                            "grid_size": config.grid_size,
                            "storm_start_turn": config.storm_start_turn,
                        },
                        "player1": {
                            "name": game.players[0].name,
                            "ships": [s.to_dict() for s in game.players[0].ships]
                        },
                        "player2": {
                            "name": game.players[1].name,
                            "ships": [s.to_dict() for s in game.players[1].ships]
                        },
                        "storm": {
                            "min": game.storm.current_bounds[0].to_tuple() if game.storm else None,
                            "max": game.storm.current_bounds[1].to_tuple() if game.storm else None,
                        }
                    }
                })

                bots = [bot1, bot2]
                max_turns = config.max_turns

                while game.phase == FCGamePhase.PLAYING and game.turn < max_turns:
                    current_bot = bots[game.current_player_idx]
                    player = game.current_player

                    state_dict = game.get_visible_state(game.current_player_idx)
                    view = create_game_view(state_dict)

                    actions = current_bot.get_actions(view)

                    recorder.record_actions(game.turn, game.current_player_idx, actions)

                    result = game.execute_turn(actions)

                    full_state = {
                        "player1_ships": [s.to_dict() for s in game.players[0].ships],
                        "player2_ships": [s.to_dict() for s in game.players[1].ships],
                        "storm_bounds": (
                            game.storm.current_bounds[0].to_tuple(),
                            game.storm.current_bounds[1].to_tuple()
                        ) if game.storm else None
                    }
                    recorder.record_turn_result(result, full_state)

                    current_bot.on_turn_result(result)

                    await websocket.send_json({
                        "type": "turn",
                        "data": {
                            "turn": game.turn,
                            "player": player.name,
                            "player_id": player.player_id,
                            "actions": [
                                {
                                    "success": ar.success,
                                    "type": ar.action.to_dict()["type"],
                                    "data": ar.action.to_dict(),
                                    "damage": ar.damage_dealt,
                                    "ships_hit": ar.ships_hit,
                                    "ships_destroyed": ar.ships_destroyed,
                                }
                                for ar in result.actions_taken
                            ],
                            "storm_damage": result.storm_damage_taken,
                            "storm_shrunk": result.storm_shrunk,
                            "state": {
                                "player1": {
                                    "ships": [s.to_dict() for s in game.players[0].ships]
                                },
                                "player2": {
                                    "ships": [s.to_dict() for s in game.players[1].ships]
                                },
                                "storm": {
                                    "min": game.storm.current_bounds[0].to_tuple() if game.storm else None,
                                    "max": game.storm.current_bounds[1].to_tuple() if game.storm else None,
                                    "turns_until_shrink": game.storm.turns_until_shrink if game.storm else 0
                                }
                            }
                        }
                    })

                    await asyncio.sleep(delay_sec)

                winner_id = game.winner if game.winner is not None else -1
                winner_name = game.players[winner_id].name if winner_id >= 0 else "Draw"

                recorder.record_game_end(winner_id, {
                    "player1_ships": [s.to_dict() for s in game.players[0].ships],
                    "player2_ships": [s.to_dict() for s in game.players[1].ships],
                })

                replay_id = replay_storage.save(recorder.get_replay())

                await websocket.send_json({
                    "type": "game_end",
                    "data": {
                        "winner": winner_name,
                        "winner_id": winner_id,
                        "turns": game.turn,
                        "player1_ships_remaining": sum(1 for s in game.players[0].ships if not s.is_destroyed),
                        "player2_ships_remaining": sum(1 for s in game.players[1].ships if not s.is_destroyed),
                        "replay_id": replay_id
                    }
                })

            elif message.get("action") == "load_replay":
                replay_id = message.get("replay_id")
                replay = replay_storage.load(replay_id)

                if not replay:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Replay not found"
                    })
                    continue

                player = ReplayPlayer(replay)

                initial = player.get_initial_state()
                await websocket.send_json({
                    "type": "replay_start",
                    "data": {
                        "replay_id": replay.replay_id,
                        "total_turns": player.total_turns,
                        "player1_name": replay.player1_name,
                        "player2_name": replay.player2_name,
                        "winner": replay.winner,
                        "config": initial["config"],
                        "ships_p1": initial["ships_p1"],
                        "ships_p2": initial["ships_p2"]
                    }
                })

            elif message.get("action") == "replay_step":
                pass

    except WebSocketDisconnect:
        pass


# === Tournament WebSocket ===

tournament_connections: dict[str, dict[str, list]] = {}


@app.websocket("/ws/fleet-commander/tournament/{tournament_id}")
async def fleet_tournament_websocket(
    websocket: WebSocket,
    tournament_id: str,
    role: str = "spectator",
    bot_name: str = "WebSocketBot",
):
    """WebSocket for tournament participation and spectating.

    Query params:
    - role: "participant" to join as a bot, "spectator" to watch
    - bot_name: Name for your bot (if participant)
    """
    await websocket.accept()

    tournament = tournament_manager.get_tournament(tournament_id)
    if not tournament:
        await websocket.send_json({"type": "error", "message": "Tournament not found"})
        await websocket.close()
        return

    if tournament_id not in tournament_connections:
        tournament_connections[tournament_id] = {"participants": [], "spectators": []}

    participant = None

    try:
        if role == "participant":
            if tournament.state != TournamentState.LOBBY:
                await websocket.send_json({"type": "error", "message": "Tournament already started"})
                await websocket.close()
                return

            participant = tournament.add_participant(
                name=bot_name,
                websocket=websocket,
                is_internal_bot=False,
            )

            if not participant:
                await websocket.send_json({"type": "error", "message": "Could not join tournament (full?)"})
                await websocket.close()
                return

            tournament_connections[tournament_id]["participants"].append(websocket)

            await websocket.send_json({
                "type": "registered",
                "participant_id": participant.id,
                "tournament": tournament.to_dict(),
            })

            await _broadcast_tournament_event(tournament_id, {
                "type": "participant_joined",
                "participant": participant.to_dict(),
                "tournament": tournament.to_dict(),
            })

        else:
            tournament_connections[tournament_id]["spectators"].append(websocket)
            await websocket.send_json({
                "type": "spectator_joined",
                "tournament": tournament.to_dict(),
            })

        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if message.get("type") == "ready" and participant:
                tournament.set_participant_ready(participant.id, True)
                await _broadcast_tournament_event(tournament_id, {
                    "type": "participant_ready",
                    "participant_id": participant.id,
                    "tournament": tournament.to_dict(),
                })

            elif message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        if role == "participant" and participant:
            if tournament.state == TournamentState.LOBBY:
                tournament.remove_participant(participant.id)
            if websocket in tournament_connections.get(tournament_id, {}).get("participants", []):
                tournament_connections[tournament_id]["participants"].remove(websocket)
        else:
            if websocket in tournament_connections.get(tournament_id, {}).get("spectators", []):
                tournament_connections[tournament_id]["spectators"].remove(websocket)


async def _broadcast_tournament_event(tournament_id: str, event: dict):
    """Broadcast event to all connected clients for a tournament."""
    if tournament_id not in tournament_connections:
        return

    all_connections = (
        tournament_connections[tournament_id].get("participants", []) +
        tournament_connections[tournament_id].get("spectators", [])
    )

    dead = []
    for ws in all_connections:
        try:
            await ws.send_json(event)
        except Exception:
            dead.append(ws)

    for ws in dead:
        for key in ["participants", "spectators"]:
            if ws in tournament_connections[tournament_id].get(key, []):
                tournament_connections[tournament_id][key].remove(ws)


@app.post("/api/fleet-commander/tournaments/{tournament_id}/run")
async def run_tournament(tournament_id: str):
    """Run a tournament to completion."""
    tournament = tournament_manager.get_tournament(tournament_id)
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")

    if tournament.state == TournamentState.IN_PROGRESS:
        raise HTTPException(status_code=400, detail="Tournament already running")

    if tournament.state == TournamentState.LOBBY:
        if not tournament.can_start():
            raise HTTPException(status_code=400, detail="Cannot start tournament. Need at least 2 ready participants.")
        tournament.start()

    asyncio.create_task(_run_tournament_matches(tournament_id))

    return {"message": "Tournament started", "tournament": tournament.to_dict()}


async def _run_tournament_matches(tournament_id: str):
    """Background task to run all tournament matches."""
    tournament = tournament_manager.get_tournament(tournament_id)
    if not tournament:
        logger.error(f"Tournament {tournament_id} not found")
        return

    try:
        await _broadcast_tournament_event(tournament_id, {
            "type": "tournament_started",
            "tournament": tournament.to_dict(),
        })

        while not tournament.is_completed():
            match = tournament.get_next_match()
            if not match:
                logger.info(f"No more matches for tournament {tournament_id}")
                break

            match.state = MatchState.IN_PROGRESS
            tournament.current_match = match
            logger.info(f"Starting match {match.id}: {match.player1_id} vs {match.player2_id}")

            p1 = tournament.participants.get(match.player1_id)
            p2 = tournament.participants.get(match.player2_id)

            if not p1 or not p2:
                logger.error(f"Participants not found for match {match.id}")
                continue

            await _broadcast_tournament_event(tournament_id, {
                "type": "match_start",
                "match": match.to_dict(),
                "player1": p1.to_dict(),
                "player2": p2.to_dict(),
            })

            try:
                result = await _run_tournament_match(tournament, match, p1, p2)
            except Exception as e:
                logger.exception(f"Error running match {match.id}: {e}")
                result = MatchResult(
                    winner_id=None,
                    loser_id=None,
                    turns=0,
                    winner_ships_remaining=0,
                    loser_ships_remaining=0,
                    replay_id=None,
                )

            tournament.record_match_result(match.id, result)

            await _broadcast_tournament_event(tournament_id, {
                "type": "match_end",
                "match": match.to_dict(),
                "result": result.to_dict(),
                "standings": [s.to_dict() for s in tournament.get_leaderboard()],
            })

            await asyncio.sleep(2)

        tournament.complete()
        winner = tournament.get_winner()
        logger.info(f"Tournament {tournament_id} completed. Winner: {winner.name if winner else 'None'}")

        await _broadcast_tournament_event(tournament_id, {
            "type": "tournament_end",
            "winner": winner.to_dict() if winner else None,
            "standings": [s.to_dict() for s in tournament.get_leaderboard()],
            "tournament": tournament.to_dict(),
        })
    except Exception as e:
        logger.exception(f"Fatal error in tournament {tournament_id}: {e}")
        tournament.live_game_state = None


async def _run_tournament_match(
    tournament: FleetCommanderTournament,
    match,
    p1: Participant,
    p2: Participant,
) -> MatchResult:
    """Run a single match between two participants."""
    config = FCGameConfig.small() if tournament.use_small_grid else FCGameConfig()

    game = FleetCommanderGame(config=config)

    bot1 = _create_tournament_bot(p1, config)
    bot2 = _create_tournament_bot(p2, config)

    placements1 = bot1.place_fleet(config, config.player1_zone[0], config.player1_zone[1])
    placements2 = bot2.place_fleet(config, config.player2_zone[0], config.player2_zone[1])

    game.setup_fleet(0, placements1)
    game.setup_fleet(1, placements2)
    game.players[0].name = p1.name
    game.players[1].name = p2.name
    game.start_game()

    recorder = GameRecorder(config, p1.name, p2.name)
    recorder.record_initial_state(
        [s.to_dict() for s in game.players[0].ships],
        [s.to_dict() for s in game.players[1].ships]
    )

    bots = [bot1, bot2]
    max_turns = config.max_turns

    tournament.live_game_state = {
        "turn": game.turn,
        "phase": game.phase.value if hasattr(game.phase, 'value') else str(game.phase),
        "current_player": game.current_player_idx,
        "player1_ships": [s.to_dict() for s in game.players[0].ships],
        "player2_ships": [s.to_dict() for s in game.players[1].ships],
        "storm": game.storm.to_dict() if game.storm else None,
        "player1_name": p1.name,
        "player2_name": p2.name,
        "config": {
            "grid_size": list(config.grid_size),
        },
    }

    await _broadcast_tournament_event(tournament.id, {
        "type": "live_match_update",
        "game_state": tournament.live_game_state,
    })

    await asyncio.sleep(0.5)

    while game.phase == FCGamePhase.PLAYING and game.turn < max_turns:
        current_bot = bots[game.current_player_idx]

        state_dict = game.get_visible_state(game.current_player_idx)
        view = create_game_view(state_dict)

        actions = current_bot.get_actions(view)

        recorder.record_actions(game.turn, game.current_player_idx, actions)
        result = game.execute_turn(actions)
        current_bot.on_turn_result(result)

        tournament.live_game_state = {
            "turn": game.turn,
            "phase": game.phase.value if hasattr(game.phase, 'value') else str(game.phase),
            "current_player": game.current_player_idx,
            "player1_ships": [s.to_dict() for s in game.players[0].ships],
            "player2_ships": [s.to_dict() for s in game.players[1].ships],
            "storm": game.storm.to_dict() if game.storm else None,
            "player1_name": p1.name,
            "player2_name": p2.name,
            "config": {
                "grid_size": list(config.grid_size),
            },
            "last_turn_result": result.to_dict(),
        }

        await _broadcast_tournament_event(tournament.id, {
            "type": "live_match_update",
            "game_state": tournament.live_game_state,
        })

        await asyncio.sleep(0.3)

    tournament.live_game_state = {
        "turn": game.turn,
        "phase": "finished",
        "current_player": game.current_player_idx,
        "player1_ships": [s.to_dict() for s in game.players[0].ships],
        "player2_ships": [s.to_dict() for s in game.players[1].ships],
        "storm": game.storm.to_dict() if game.storm else None,
        "player1_name": p1.name,
        "player2_name": p2.name,
        "winner": game.winner,
        "config": {
            "grid_size": list(config.grid_size),
        },
    }

    await _broadcast_tournament_event(tournament.id, {
        "type": "live_match_update",
        "game_state": tournament.live_game_state,
    })

    await asyncio.sleep(2.0)

    tournament.live_game_state = None
    await _broadcast_tournament_event(tournament.id, {
        "type": "live_match_ended",
    })
    winner_id = game.winner if game.winner is not None else -1
    replay_id = replay_storage.save(recorder.get_replay())

    winner_participant_id = None
    loser_participant_id = None
    winner_ships = 0
    loser_ships = 0

    if winner_id == 0:
        winner_participant_id = p1.id
        loser_participant_id = p2.id
        winner_ships = sum(1 for s in game.players[0].ships if not s.is_destroyed)
        loser_ships = sum(1 for s in game.players[1].ships if not s.is_destroyed)
    elif winner_id == 1:
        winner_participant_id = p2.id
        loser_participant_id = p1.id
        winner_ships = sum(1 for s in game.players[1].ships if not s.is_destroyed)
        loser_ships = sum(1 for s in game.players[0].ships if not s.is_destroyed)

    return MatchResult(
        winner_id=winner_participant_id,
        loser_id=loser_participant_id,
        turns=game.turn,
        winner_ships_remaining=winner_ships,
        loser_ships_remaining=loser_ships,
        replay_id=replay_id,
    )


def _create_tournament_bot(participant: Participant, config):
    """Create a bot instance for a tournament participant."""
    if participant.is_internal_bot and participant.internal_bot_type:
        bot_class = FLEET_BOTS.get(participant.internal_bot_type, TacticalBot)
        bot = bot_class()
        bot.on_game_start(config)
        return bot

    # For WebSocket bots, fall back to TacticalBot for now
    # TODO: Implement WebSocket bot adapter for tournaments
    bot = TacticalBot()
    bot.on_game_start(config)
    return bot


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
