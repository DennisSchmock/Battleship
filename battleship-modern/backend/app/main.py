"""FastAPI application for Battleship tournament."""
import asyncio
from contextlib import asynccontextmanager
from typing import List, Optional, Tuple
import json

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .api.tournament import (
    Tournament,
    AsyncTournament,
    TournamentFormat,
    create_player,
    AI_PLAYER_REGISTRY,
)
from .game.game import BattleshipGame
from .game.game3d import SpaceBattleshipGame
from .game.player import Player, AIPlayer, HunterAIPlayer
from .game.player3d import RandomPlayer3D, HunterAI3D, SmartHunter3D
from .game.ship3d import Ship3D


# Store active tournaments and connections
tournaments: dict[str, AsyncTournament] = {}
connections: dict[str, List[WebSocket]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for the application."""
    print("🚢 Battleship Tournament Server starting...")
    yield
    print("🚢 Battleship Tournament Server shutting down...")


app = FastAPI(
    title="Battleship AI Tournament",
    description="A modern Battleship game with ML-powered AI players",
    version="1.0.0",
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


# Pydantic models
class PlayerConfig(BaseModel):
    name: str
    type: str  # "random", "hunter", "rl"
    model_path: Optional[str] = None


class TournamentConfig(BaseModel):
    name: str
    format: str = "round_robin"
    games_per_match: int = 3
    players: List[PlayerConfig]


class QuickGameConfig(BaseModel):
    player1_type: str = "hunter"
    player2_type: str = "random"


# REST API endpoints
@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "message": "Battleship Tournament Server"}


@app.get("/api/player-types")
async def get_player_types():
    """Get available AI player types."""
    return {
        "types": [
            {"id": "random", "name": "Random AI", "description": "Shoots randomly"},
            {"id": "hunter", "name": "Hunter AI", "description": "Hunts ships after hitting"},
            {"id": "adaptive", "name": "Adaptive Hunter", "description": "Learns opponent patterns across rounds"},
            {"id": "rl", "name": "RL Agent", "description": "Reinforcement Learning trained AI"},
        ]
    }


@app.post("/api/tournaments")
async def create_tournament(config: TournamentConfig):
    """Create a new tournament."""
    tournament = AsyncTournament(
        name=config.name,
        format=TournamentFormat(config.format),
        games_per_match=config.games_per_match,
    )

    for player_config in config.players:
        kwargs = {}
        if player_config.model_path:
            kwargs["model_path"] = player_config.model_path

        player = create_player(
            player_config.type,
            player_config.name,
            **kwargs
        )
        tournament.add_player(player)

    tournaments[config.name] = tournament
    connections[config.name] = []

    return {"tournament_id": config.name, "status": "created"}


@app.get("/api/tournaments/{tournament_id}")
async def get_tournament(tournament_id: str):
    """Get tournament status and leaderboard."""
    if tournament_id not in tournaments:
        raise HTTPException(status_code=404, detail="Tournament not found")

    return tournaments[tournament_id].to_dict()


@app.post("/api/tournaments/{tournament_id}/start")
async def start_tournament(tournament_id: str):
    """Start a tournament (non-blocking, use WebSocket for updates)."""
    if tournament_id not in tournaments:
        raise HTTPException(status_code=404, detail="Tournament not found")

    tournament = tournaments[tournament_id]

    if tournament.is_running:
        raise HTTPException(status_code=400, detail="Tournament already running")

    # Run tournament in background
    asyncio.create_task(_run_tournament(tournament_id))

    return {"status": "started"}


async def _run_tournament(tournament_id: str):
    """Background task to run tournament and broadcast updates."""
    tournament = tournaments[tournament_id]

    # Run the tournament
    asyncio.create_task(tournament.run_round_robin_async())

    # Broadcast events to connected clients
    while tournament.is_running or not tournament._event_queue.empty():
        try:
            event = await asyncio.wait_for(tournament.get_event(), timeout=1.0)
            await broadcast(tournament_id, event)
        except asyncio.TimeoutError:
            continue


async def broadcast(tournament_id: str, message: dict):
    """Broadcast message to all connected clients for a tournament."""
    if tournament_id not in connections:
        return

    dead_connections = []
    for websocket in connections[tournament_id]:
        try:
            await websocket.send_json(message)
        except Exception:
            dead_connections.append(websocket)

    # Remove dead connections
    for ws in dead_connections:
        connections[tournament_id].remove(ws)


@app.post("/api/quick-game")
async def quick_game(config: QuickGameConfig):
    """Play a quick game between two AIs and return the result."""
    player1 = create_player(config.player1_type, f"Player 1 ({config.player1_type})")
    player2 = create_player(config.player2_type, f"Player 2 ({config.player2_type})")

    game = BattleshipGame(player1=player1, player2=player2)
    winner = game.play_full_game()

    return {
        "winner": winner.name,
        "total_turns": game.turn_count,
        "replay": game.get_full_replay(),
    }


# WebSocket endpoint for real-time updates
@app.websocket("/ws/tournament/{tournament_id}")
async def tournament_websocket(websocket: WebSocket, tournament_id: str):
    """WebSocket connection for tournament updates."""
    await websocket.accept()

    if tournament_id not in connections:
        connections[tournament_id] = []

    connections[tournament_id].append(websocket)

    try:
        # Send current state
        if tournament_id in tournaments:
            await websocket.send_json({
                "type": "state",
                "data": tournaments[tournament_id].to_dict()
            })

        # Keep connection alive and handle incoming messages
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        if tournament_id in connections:
            connections[tournament_id].remove(websocket)


@app.websocket("/ws/game")
async def game_websocket(websocket: WebSocket):
    """WebSocket for watching a single game in real-time."""
    await websocket.accept()

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if message.get("action") == "start_game":
                p1_type = message.get("player1_type", "hunter")
                p2_type = message.get("player2_type", "random")

                player1 = create_player(p1_type, f"Player 1 ({p1_type})")
                player2 = create_player(p2_type, f"Player 2 ({p2_type})")

                game = BattleshipGame(player1=player1, player2=player2)
                game.setup()

                # Send initial state
                await websocket.send_json({
                    "type": "game_start",
                    "data": game.get_game_state()
                })

                # Play game turn by turn
                while game.state.value == "playing":
                    event = game.play_turn()

                    await websocket.send_json({
                        "type": "turn",
                        "data": {
                            "event": event.to_dict(),
                            "state": game.get_game_state()
                        }
                    })

                    # Small delay for visualization
                    await asyncio.sleep(0.3)

                # Send final state
                await websocket.send_json({
                    "type": "game_end",
                    "data": {
                        "winner": game.winner.name if game.winner else None,
                        "replay": game.get_full_replay()
                    }
                })

    except WebSocketDisconnect:
        pass


def create_3d_player(player_type: str, name: str):
    """Factory function to create 3D AI players."""
    if player_type == "random3d":
        return RandomPlayer3D(name=name)
    elif player_type == "hunter3d":
        return HunterAI3D(name=name)
    elif player_type == "smart3d":
        return SmartHunter3D(name=name)
    else:
        return RandomPlayer3D(name=name)


@app.websocket("/ws/space-game")
async def space_game_websocket(websocket: WebSocket):
    """WebSocket for watching a 3D SpaceBattleship game in real-time."""
    await websocket.accept()

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if message.get("action") == "start_game":
                p1_type = message.get("player1_type", "smart3d")
                p2_type = message.get("player2_type", "random3d")
                delay = message.get("delay", 300) / 1000.0  # Convert ms to seconds

                player1 = create_3d_player(p1_type, f"Player 1 ({p1_type})")
                player2 = create_3d_player(p2_type, f"Player 2 ({p2_type})")

                game = SpaceBattleshipGame(player1=player1, player2=player2)
                game.setup()

                # Send initial state
                await websocket.send_json({
                    "type": "game_start",
                    "data": game.get_game_state()
                })

                # Play game turn by turn
                while game.state.value == "playing":
                    event = game.play_turn()

                    await websocket.send_json({
                        "type": "turn",
                        "data": {
                            "event": event.to_dict(),
                            "state": game.get_game_state()
                        }
                    })

                    # Delay for visualization
                    await asyncio.sleep(delay)

                # Send final state
                await websocket.send_json({
                    "type": "game_end",
                    "data": {
                        "winner": game.winner.name if game.winner else None,
                        "replay": game.get_full_replay()
                    }
                })

    except WebSocketDisconnect:
        pass


def get_ship_positions(player: Player) -> List[Tuple[int, int]]:
    """Extract all ship positions from a player's board."""
    positions = []
    for ship in player.board.ships:
        positions.extend(ship.get_coordinates())
    return positions


@app.websocket("/ws/match")
async def match_websocket(websocket: WebSocket):
    """WebSocket for multi-round match between two AIs."""
    await websocket.accept()

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if message.get("action") == "start_match":
                p1_type = message.get("player1_type", "hunter")
                p2_type = message.get("player2_type", "random")
                num_rounds = message.get("rounds", 50)
                delay = message.get("delay", 100) / 1000.0

                p1_name = f"{p1_type.title()}"
                p2_name = f"{p2_type.title()}"

                # Create players ONCE - they persist across rounds for learning
                player1 = create_player(p1_type, p1_name)
                player2 = create_player(p2_type, p2_name)

                # Track overall stats
                p1_wins = 0
                p2_wins = 0
                results = []

                await websocket.send_json({
                    "type": "match_start",
                    "data": {
                        "player1": p1_name,
                        "player2": p2_name,
                        "total_rounds": num_rounds
                    }
                })

                for round_num in range(1, num_rounds + 1):
                    # Signal start of new round for adaptive players
                    if hasattr(player1, 'start_new_round'):
                        player1.start_new_round()
                    if hasattr(player2, 'start_new_round'):
                        player2.start_new_round()

                    # Play the full game (setup() will call reset() and place_ships())
                    game = BattleshipGame(player1=player1, player2=player2)
                    winner = game.play_full_game()

                    # Calculate stats BEFORE recording round result (which might happen before next reset)
                    p1_shots = len(player1.shots_fired)
                    p2_shots = len(player2.shots_fired)
                    p1_hits = len(player1.hits)
                    p2_hits = len(player2.hits)

                    # Get ship positions for learning
                    p1_ship_positions = get_ship_positions(player1)
                    p2_ship_positions = get_ship_positions(player2)

                    # Determine winner
                    if winner.name == p1_name:
                        p1_wins += 1
                        winner_name = p1_name
                        p1_won, p2_won = True, False
                    else:
                        p2_wins += 1
                        winner_name = p2_name
                        p1_won, p2_won = False, True

                    # Record round results for learning
                    # Player1 learns from player2's behavior
                    if hasattr(player1, 'record_round_result'):
                        player1.record_round_result(
                            won=p1_won,
                            enemy_shots=list(player2.shots_fired),
                            enemy_ship_positions=p2_ship_positions
                        )
                    # Player2 learns from player1's behavior
                    if hasattr(player2, 'record_round_result'):
                        player2.record_round_result(
                            won=p2_won,
                            enemy_shots=list(player1.shots_fired),
                            enemy_ship_positions=p1_ship_positions
                        )

                    round_result = {
                        "round": round_num,
                        "winner": winner_name,
                        "turns": game.turn_count,
                        "p1_shots": p1_shots,
                        "p1_hits": p1_hits,
                        "p1_accuracy": round(p1_hits / p1_shots * 100, 1) if p1_shots > 0 else 0,
                        "p2_shots": p2_shots,
                        "p2_hits": p2_hits,
                        "p2_accuracy": round(p2_hits / p2_shots * 100, 1) if p2_shots > 0 else 0,
                    }
                    results.append(round_result)

                    # Send round result
                    await websocket.send_json({
                        "type": "round_end",
                        "data": {
                            "result": round_result,
                            "standings": {
                                "p1_wins": p1_wins,
                                "p2_wins": p2_wins,
                                "rounds_played": round_num
                            }
                        }
                    })

                    await asyncio.sleep(delay)

                # Send final match result
                await websocket.send_json({
                    "type": "match_end",
                    "data": {
                        "winner": p1_name if p1_wins > p2_wins else p2_name if p2_wins > p1_wins else "Tie",
                        "p1_wins": p1_wins,
                        "p2_wins": p2_wins,
                        "results": results
                    }
                })

    except WebSocketDisconnect:
        pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
