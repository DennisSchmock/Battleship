"""Board class for Battleship game."""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Tuple, Set, Optional

from .ship import Ship, Orientation


class CellState(Enum):
    EMPTY = "empty"
    SHIP = "ship"
    HIT = "hit"
    MISS = "miss"
    SUNK = "sunk"


@dataclass
class Board:
    """Represents a player's board in Battleship."""

    size: int = 10
    ships: List[Ship] = field(default_factory=list)
    shots_received: Set[Tuple[int, int]] = field(default_factory=set)

    def __post_init__(self):
        """Initialize the grid."""
        self._grid: List[List[CellState]] = [
            [CellState.EMPTY for _ in range(self.size)]
            for _ in range(self.size)
        ]

    def is_valid_position(self, row: int, col: int) -> bool:
        """Check if a position is within the board."""
        return 0 <= row < self.size and 0 <= col < self.size

    def can_place_ship(self, ship: Ship, row: int, col: int, orientation: Orientation) -> bool:
        """Check if a ship can be placed at the given position."""
        # Temporarily set position to check coordinates
        original_pos = ship.position
        original_orient = ship.orientation
        ship.place(row, col, orientation)
        coords = ship.get_coordinates()
        ship.position = original_pos
        ship.orientation = original_orient

        # Check all coordinates are valid and not occupied
        for r, c in coords:
            if not self.is_valid_position(r, c):
                return False
            if self._grid[r][c] == CellState.SHIP:
                return False

        return True

    def place_ship(self, ship: Ship, row: int, col: int, orientation: Orientation) -> bool:
        """Place a ship on the board. Returns True if successful."""
        if not self.can_place_ship(ship, row, col, orientation):
            return False

        ship.place(row, col, orientation)

        # Mark cells as occupied
        for r, c in ship.get_coordinates():
            self._grid[r][c] = CellState.SHIP

        self.ships.append(ship)
        return True

    def receive_shot(self, row: int, col: int) -> Tuple[bool, Optional[Ship]]:
        """
        Process an incoming shot.
        Returns: (is_hit, ship_if_sunk)
        """
        if not self.is_valid_position(row, col):
            raise ValueError(f"Invalid position: ({row}, {col})")

        if (row, col) in self.shots_received:
            raise ValueError(f"Position already shot: ({row}, {col})")

        self.shots_received.add((row, col))

        # Check if any ship is hit
        for ship in self.ships:
            if ship.receive_hit(row, col):
                if ship.is_sunk:
                    # Mark all ship cells as sunk
                    for r, c in ship.get_coordinates():
                        self._grid[r][c] = CellState.SUNK
                    return True, ship
                else:
                    self._grid[row][col] = CellState.HIT
                    return True, None

        # Miss
        self._grid[row][col] = CellState.MISS
        return False, None

    @property
    def all_ships_sunk(self) -> bool:
        """Check if all ships have been sunk."""
        return all(ship.is_sunk for ship in self.ships)

    @property
    def remaining_ships(self) -> List[Ship]:
        """Get list of ships that haven't been sunk yet."""
        return [ship for ship in self.ships if not ship.is_sunk]

    def get_cell_state(self, row: int, col: int) -> CellState:
        """Get the state of a specific cell."""
        return self._grid[row][col]

    def get_available_shots(self) -> List[Tuple[int, int]]:
        """Get all positions that haven't been shot yet."""
        available = []
        for row in range(self.size):
            for col in range(self.size):
                if (row, col) not in self.shots_received:
                    available.append((row, col))
        return available

    def to_dict(self, hide_ships: bool = False) -> dict:
        """
        Convert board to dictionary for JSON serialization.
        If hide_ships is True, unrevealed ship positions are hidden.
        """
        grid = []
        for row in range(self.size):
            grid_row = []
            for col in range(self.size):
                state = self._grid[row][col]
                if hide_ships and state == CellState.SHIP:
                    grid_row.append(CellState.EMPTY.value)
                else:
                    grid_row.append(state.value)
            grid.append(grid_row)

        return {
            "size": self.size,
            "grid": grid,
            "ships": [ship.to_dict() for ship in self.ships] if not hide_ships else [],
            "shots_received": list(self.shots_received),
        }
