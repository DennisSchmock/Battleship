"""FastAPI application for Battleship tournament."""
import asyncio
from contextlib import asynccontextmanager
from typing import List, Optional
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
from .game.player import AIPlayer, HunterAIPlayer


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
