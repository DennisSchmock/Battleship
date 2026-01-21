"""Main game logic for Battleship."""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple
from datetime import datetime

from .board import Board
from .ship import Ship
from .player import Player


class GameState(Enum):
    SETUP = "setup"
    PLAYING = "playing"
    FINISHED = "finished"


@dataclass
class GameEvent:
    """Represents an event in the game for replay/visualization."""

    turn: int
    player_name: str
    action: str  # "shot", "hit", "miss", "sunk"
    position: Tuple[int, int]
    details: Optional[dict] = None
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "turn": self.turn,
            "player": self.player_name,
            "action": self.action,
            "position": list(self.position),
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class BattleshipGame:
    """Manages a single Battleship game between two players."""

    player1: Player
    player2: Player
    state: GameState = GameState.SETUP
    current_player_index: int = 0
    turn_count: int = 0
    events: List[GameEvent] = field(default_factory=list)
    winner: Optional[Player] = None

    @property
    def current_player(self) -> Player:
        """Get the player whose turn it is."""
        return self.player1 if self.current_player_index == 0 else self.player2

    @property
    def opponent(self) -> Player:
        """Get the opponent of the current player."""
        return self.player2 if self.current_player_index == 0 else self.player1

    def setup(self) -> None:
        """Set up the game by having both players place their ships."""
        # Reset players
        self.player1.reset()
        self.player2.reset()

        # Create fleets and place ships
        fleet1 = Ship.create_standard_fleet()
        fleet2 = Ship.create_standard_fleet()

        self.player1.place_ships(fleet1)
        self.player2.place_ships(fleet2)

        self.state = GameState.PLAYING
        self.turn_count = 0
        self.events = []
        self.winner = None

    def play_turn(self) -> GameEvent:
        """Play a single turn. Returns the event that occurred."""
        if self.state != GameState.PLAYING:
            raise RuntimeError(f"Cannot play turn in state: {self.state}")

        current = self.current_player
        opponent = self.opponent

        # Get shot from current player
        opponent_state = opponent.board.to_dict(hide_ships=True)
        row, col = current.get_shot(opponent_state)

        # Process the shot
        is_hit, sunk_ship = opponent.board.receive_shot(row, col)

        # Record result for the player
        current.record_shot_result(row, col, is_hit, sunk_ship)

        # Create event
        if sunk_ship:
            action = "sunk"
            details = {"ship": sunk_ship.name}
        elif is_hit:
            action = "hit"
            details = None
        else:
            action = "miss"
            details = None

        event = GameEvent(
            turn=self.turn_count,
            player_name=current.name,
            action=action,
            position=(row, col),
            details=details,
        )
        self.events.append(event)

        # Check for winner
        if opponent.board.all_ships_sunk:
            self.state = GameState.FINISHED
            self.winner = current
        else:
            # Switch players
            self.current_player_index = 1 - self.current_player_index
            self.turn_count += 1

        return event

    def play_full_game(self) -> Player:
        """Play the entire game until there's a winner. Returns the winner."""
        if self.state == GameState.SETUP:
            self.setup()

        while self.state == GameState.PLAYING:
            self.play_turn()

        return self.winner

    def get_game_state(self, for_player: Optional[Player] = None) -> dict:
        """
        Get the current game state.
        If for_player is specified, hide opponent's ship positions.
        """
        p1_hide = for_player == self.player2 if for_player else False
        p2_hide = for_player == self.player1 if for_player else False

        return {
            "state": self.state.value,
            "turn": self.turn_count,
            "current_player": self.current_player.name,
            "player1": {
                "name": self.player1.name,
                "board": self.player1.board.to_dict(hide_ships=p1_hide),
                "stats": self.player1.to_dict(),
            },
            "player2": {
                "name": self.player2.name,
                "board": self.player2.board.to_dict(hide_ships=p2_hide),
                "stats": self.player2.to_dict(),
            },
            "winner": self.winner.name if self.winner else None,
            "events": [e.to_dict() for e in self.events[-10:]],  # Last 10 events
        }

    def get_full_replay(self) -> dict:
        """Get all events for replaying the game."""
        return {
            "player1": self.player1.name,
            "player2": self.player2.name,
            "winner": self.winner.name if self.winner else None,
            "total_turns": self.turn_count,
            "events": [e.to_dict() for e in self.events],
        }
