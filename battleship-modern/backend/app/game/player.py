"""Player classes for Battleship game."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Tuple, Optional
import random

from .board import Board
from .ship import Ship, Orientation


@dataclass
class Player(ABC):
    """Abstract base class for a Battleship player."""

    name: str
    board: Board = field(default_factory=Board)
    shots_fired: List[Tuple[int, int]] = field(default_factory=list)
    hits: List[Tuple[int, int]] = field(default_factory=list)

    @abstractmethod
    def place_ships(self, ships: List[Ship]) -> None:
        """Place all ships on the board."""
        pass

    @abstractmethod
    def get_shot(self, opponent_board_state: dict) -> Tuple[int, int]:
        """Determine the next shot to fire."""
        pass

    def record_shot_result(self, row: int, col: int, is_hit: bool, sunk_ship: Optional[Ship] = None) -> None:
        """Record the result of a shot."""
        self.shots_fired.append((row, col))
        if is_hit:
            self.hits.append((row, col))

    def reset(self) -> None:
        """Reset player for a new game."""
        self.board = Board()
        self.shots_fired = []
        self.hits = []

    def to_dict(self) -> dict:
        """Convert player to dictionary."""
        total_shots = len(self.shots_fired)
        total_hits = len(self.hits)
        accuracy = round((total_hits / total_shots * 100), 1) if total_shots > 0 else 0
        return {
            "name": self.name,
            "shots_fired": total_shots,
            "hits": total_hits,
            "accuracy": accuracy,
            "ships_remaining": len(self.board.remaining_ships),
        }


class AIPlayer(Player):
    """Base AI player with random strategy."""

    def place_ships(self, ships: List[Ship]) -> None:
        """Randomly place all ships on the board."""
        for ship in ships:
            placed = False
            attempts = 0
            max_attempts = 1000

            while not placed and attempts < max_attempts:
                row = random.randint(0, self.board.size - 1)
                col = random.randint(0, self.board.size - 1)
                orientation = random.choice([Orientation.HORIZONTAL, Orientation.VERTICAL])

                placed = self.board.place_ship(ship, row, col, orientation)
                attempts += 1

            if not placed:
                raise RuntimeError(f"Could not place ship: {ship.name}")

    def get_shot(self, opponent_board_state: dict) -> Tuple[int, int]:
        """Random shot selection."""
        shots_received = set(tuple(s) for s in opponent_board_state.get("shots_received", []))
        size = opponent_board_state.get("size", 10)

        available = [
            (r, c) for r in range(size) for c in range(size)
            if (r, c) not in shots_received
        ]

        if not available:
            raise RuntimeError("No available shots")

        return random.choice(available)


class HunterAIPlayer(AIPlayer):
    """
    Smarter AI that hunts ships after getting a hit.
    Similar to the original Java implementation's strategy.
    """

    def __init__(self, name: str):
        super().__init__(name)
        self._hunt_mode: bool = False
        self._hunt_targets: List[Tuple[int, int]] = []
        self._last_hit: Optional[Tuple[int, int]] = None

    def reset(self) -> None:
        """Reset player for a new game."""
        super().reset()
        self._hunt_mode = False
        self._hunt_targets = []
        self._last_hit = None

    def record_shot_result(self, row: int, col: int, is_hit: bool, sunk_ship: Optional[Ship] = None) -> None:
        """Record shot result and update hunting state."""
        super().record_shot_result(row, col, is_hit, sunk_ship)

        if is_hit:
            self._last_hit = (row, col)
            if sunk_ship:
                # Ship sunk - clear hunt targets for this ship
                self._hunt_targets = [t for t in self._hunt_targets if t not in sunk_ship.get_coordinates()]
                if not self._hunt_targets:
                    self._hunt_mode = False
            else:
                # Hit but not sunk - enter hunt mode
                self._hunt_mode = True
                self._add_adjacent_targets(row, col)

    def _add_adjacent_targets(self, row: int, col: int) -> None:
        """Add adjacent cells to hunt targets."""
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            new_row, new_col = row + dr, col + dc
            if 0 <= new_row < self.board.size and 0 <= new_col < self.board.size:
                if (new_row, new_col) not in self.shots_fired and (new_row, new_col) not in self._hunt_targets:
                    self._hunt_targets.append((new_row, new_col))

    def get_shot(self, opponent_board_state: dict) -> Tuple[int, int]:
        """Smart shot selection with hunting behavior."""
        shots_received = set(tuple(s) for s in opponent_board_state.get("shots_received", []))

        # Filter hunt targets to remove already shot positions
        self._hunt_targets = [t for t in self._hunt_targets if t not in shots_received]

        # If in hunt mode and have targets, use them
        if self._hunt_mode and self._hunt_targets:
            return self._hunt_targets.pop(0)

        # Otherwise use grid pattern (checkerboard) for efficiency
        size = opponent_board_state.get("size", 10)

        # Checkerboard pattern - more efficient ship hunting
        checkerboard = [
            (r, c) for r in range(size) for c in range(size)
            if (r + c) % 2 == 0 and (r, c) not in shots_received
        ]

        if checkerboard:
            return random.choice(checkerboard)

        # Fallback to any available cell
        available = [
            (r, c) for r in range(size) for c in range(size)
            if (r, c) not in shots_received
        ]

        if available:
            return random.choice(available)

        raise RuntimeError("No available shots")
