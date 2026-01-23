"""Replay System for Fleet Commander.

Records games and allows playback.
"""
import json
import os
import uuid
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from pathlib import Path

from .models import (
    Position, Direction, ShipType, GameConfig,
    Action, TurnResult, ActionResult
)


@dataclass
class GameEvent:
    """A single event in a game replay."""
    turn: int
    player_id: int
    event_type: str  # "action", "result", "storm", "game_start", "game_end"
    data: Dict[str, Any]
    timestamp: float = 0.0  # Relative time from game start


@dataclass
class GameReplay:
    """Complete recording of a game."""
    replay_id: str
    created_at: str
    config: Dict[str, Any]
    player1_name: str
    player2_name: str
    winner: Optional[int]
    total_turns: int
    events: List[GameEvent] = field(default_factory=list)

    # Initial state
    initial_ships_p1: List[Dict] = field(default_factory=list)
    initial_ships_p2: List[Dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "replay_id": self.replay_id,
            "created_at": self.created_at,
            "config": self.config,
            "player1_name": self.player1_name,
            "player2_name": self.player2_name,
            "winner": self.winner,
            "total_turns": self.total_turns,
            "initial_ships_p1": self.initial_ships_p1,
            "initial_ships_p2": self.initial_ships_p2,
            "events": [
                {
                    "turn": e.turn,
                    "player_id": e.player_id,
                    "event_type": e.event_type,
                    "data": e.data,
                    "timestamp": e.timestamp
                }
                for e in self.events
            ]
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'GameReplay':
        events = [
            GameEvent(
                turn=e["turn"],
                player_id=e["player_id"],
                event_type=e["event_type"],
                data=e["data"],
                timestamp=e.get("timestamp", 0.0)
            )
            for e in data.get("events", [])
        ]
        return cls(
            replay_id=data["replay_id"],
            created_at=data["created_at"],
            config=data["config"],
            player1_name=data["player1_name"],
            player2_name=data["player2_name"],
            winner=data.get("winner"),
            total_turns=data["total_turns"],
            initial_ships_p1=data.get("initial_ships_p1", []),
            initial_ships_p2=data.get("initial_ships_p2", []),
            events=events
        )


class GameRecorder:
    """Records a game for replay."""

    def __init__(self, config: GameConfig, player1_name: str, player2_name: str):
        self.replay = GameReplay(
            replay_id=str(uuid.uuid4()),
            created_at=datetime.now().isoformat(),
            config={
                "grid_size": config.grid_size,
                "storm_start_turn": config.storm_start_turn,
                "storm_shrink_interval": config.storm_shrink_interval,
                "max_turns": config.max_turns,
                "fleet": [s.value for s in config.fleet_config.ships]
            },
            player1_name=player1_name,
            player2_name=player2_name,
            winner=None,
            total_turns=0
        )
        self.start_time = datetime.now()

    def record_initial_state(self, ships_p1: List[Dict], ships_p2: List[Dict]):
        """Record initial ship positions."""
        self.replay.initial_ships_p1 = ships_p1
        self.replay.initial_ships_p2 = ships_p2

        self._add_event(0, -1, "game_start", {
            "ships_p1": ships_p1,
            "ships_p2": ships_p2
        })

    def record_actions(self, turn: int, player_id: int, actions: List[Action]):
        """Record actions taken by a player."""
        self._add_event(turn, player_id, "actions", {
            "actions": [a.to_dict() for a in actions]
        })

    def record_turn_result(self, result: TurnResult, game_state: Dict):
        """Record the result of a turn."""
        self._add_event(result.turn, result.player_id, "turn_result", {
            "actions_taken": [
                {
                    "success": ar.success,
                    "action": ar.action.to_dict(),
                    "message": ar.message,
                    "damage_dealt": ar.damage_dealt,
                    "ships_hit": ar.ships_hit,
                    "ships_destroyed": ar.ships_destroyed,
                    "cells_revealed": {
                        str(p.to_tuple()): s.value
                        for p, s in ar.cells_revealed.items()
                    } if ar.cells_revealed else {}
                }
                for ar in result.actions_taken
            ],
            "storm_damage": result.storm_damage_taken,
            "storm_shrunk": result.storm_shrunk,
            "game_state": game_state
        })
        self.replay.total_turns = result.turn

    def record_storm_shrink(self, turn: int, new_bounds: tuple):
        """Record storm shrinking."""
        self._add_event(turn, -1, "storm_shrink", {
            "new_min": new_bounds[0],
            "new_max": new_bounds[1]
        })

    def record_game_end(self, winner: int, final_state: Dict):
        """Record game ending."""
        self.replay.winner = winner
        self._add_event(self.replay.total_turns, -1, "game_end", {
            "winner": winner,
            "final_state": final_state
        })

    def _add_event(self, turn: int, player_id: int, event_type: str, data: Dict):
        elapsed = (datetime.now() - self.start_time).total_seconds()
        self.replay.events.append(GameEvent(
            turn=turn,
            player_id=player_id,
            event_type=event_type,
            data=data,
            timestamp=elapsed
        ))

    def get_replay(self) -> GameReplay:
        return self.replay


class ReplayStorage:
    """Stores and retrieves replays from disk."""

    def __init__(self, storage_dir: str = "replays"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(exist_ok=True)

    def save(self, replay: GameReplay) -> str:
        """Save a replay to disk. Returns the replay ID."""
        filepath = self.storage_dir / f"{replay.replay_id}.json"
        with open(filepath, 'w') as f:
            json.dump(replay.to_dict(), f, indent=2)
        return replay.replay_id

    def load(self, replay_id: str) -> Optional[GameReplay]:
        """Load a replay from disk."""
        filepath = self.storage_dir / f"{replay_id}.json"
        if not filepath.exists():
            return None
        with open(filepath, 'r') as f:
            data = json.load(f)
        return GameReplay.from_dict(data)

    def list_replays(self, limit: int = 20) -> List[Dict]:
        """List available replays (most recent first)."""
        replays = []
        for filepath in sorted(self.storage_dir.glob("*.json"), reverse=True)[:limit]:
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                replays.append({
                    "replay_id": data["replay_id"],
                    "created_at": data["created_at"],
                    "player1_name": data["player1_name"],
                    "player2_name": data["player2_name"],
                    "winner": data.get("winner"),
                    "total_turns": data["total_turns"]
                })
            except Exception:
                continue
        return replays

    def delete(self, replay_id: str) -> bool:
        """Delete a replay."""
        filepath = self.storage_dir / f"{replay_id}.json"
        if filepath.exists():
            filepath.unlink()
            return True
        return False


class ReplayPlayer:
    """Plays back a recorded game."""

    def __init__(self, replay: GameReplay):
        self.replay = replay
        self.current_event_idx = 0
        self.current_turn = 0

    def reset(self):
        """Reset to beginning."""
        self.current_event_idx = 0
        self.current_turn = 0

    def get_initial_state(self) -> Dict:
        """Get initial game state for replay."""
        return {
            "config": self.replay.config,
            "player1_name": self.replay.player1_name,
            "player2_name": self.replay.player2_name,
            "ships_p1": self.replay.initial_ships_p1,
            "ships_p2": self.replay.initial_ships_p2
        }

    def get_events_for_turn(self, turn: int) -> List[GameEvent]:
        """Get all events for a specific turn."""
        return [e for e in self.replay.events if e.turn == turn]

    def get_next_event(self) -> Optional[GameEvent]:
        """Get the next event in sequence."""
        if self.current_event_idx >= len(self.replay.events):
            return None
        event = self.replay.events[self.current_event_idx]
        self.current_event_idx += 1
        self.current_turn = event.turn
        return event

    def seek_to_turn(self, turn: int) -> List[GameEvent]:
        """Seek to a specific turn, returning all events up to that point."""
        events = []
        for i, event in enumerate(self.replay.events):
            if event.turn <= turn:
                events.append(event)
                self.current_event_idx = i + 1
                self.current_turn = event.turn
            else:
                break
        return events

    @property
    def is_finished(self) -> bool:
        return self.current_event_idx >= len(self.replay.events)

    @property
    def total_turns(self) -> int:
        return self.replay.total_turns

    @property
    def progress(self) -> float:
        """Progress as 0-1."""
        if not self.replay.events:
            return 1.0
        return self.current_event_idx / len(self.replay.events)
