"""3D Board class for SpaceBattleship game."""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Tuple, Set, Optional
import random

from .ship3d import Ship3D, Orientation3D, ORIENTATION_VECTORS


class CellState3D(Enum):
    EMPTY = "empty"
    SHIP = "ship"
    HIT = "hit"
    MISS = "miss"
    SUNK = "sunk"


@dataclass
class Board3D:
    """Represents a 3D space battlefield."""

    size_x: int = 12
    size_y: int = 12
    size_z: int = 8
    ships: List[Ship3D] = field(default_factory=list)
    shots_received: Set[Tuple[int, int, int]] = field(default_factory=set)

    def __post_init__(self):
        """Initialize the 3D grid."""
        self._grid: List[List[List[CellState3D]]] = [
            [
                [CellState3D.EMPTY for _ in range(self.size_z)]
                for _ in range(self.size_y)
            ]
            for _ in range(self.size_x)
        ]

    @property
    def total_cells(self) -> int:
        """Total number of cells in the grid."""
        return self.size_x * self.size_y * self.size_z

    def is_valid_position(self, x: int, y: int, z: int) -> bool:
        """Check if a position is within the battlefield."""
        return (0 <= x < self.size_x and
                0 <= y < self.size_y and
                0 <= z < self.size_z)

    def can_place_ship(self, ship: Ship3D, x: int, y: int, z: int,
                       orientation: Orientation3D) -> bool:
        """Check if a ship can be placed at the given position."""
        # Temporarily set position to check coordinates
        original_pos = ship.position
        original_orient = ship.orientation
        ship.place(x, y, z, orientation)
        coords = ship.get_coordinates()
        ship.position = original_pos
        ship.orientation = original_orient

        # Check all coordinates are valid and not occupied
        for cx, cy, cz in coords:
            if not self.is_valid_position(cx, cy, cz):
                return False
            if self._grid[cx][cy][cz] == CellState3D.SHIP:
                return False

        return True

    def place_ship(self, ship: Ship3D, x: int, y: int, z: int,
                   orientation: Orientation3D) -> bool:
        """Place a ship on the board. Returns True if successful."""
        if not self.can_place_ship(ship, x, y, z, orientation):
            return False

        ship.place(x, y, z, orientation)

        # Mark cells as occupied
        for cx, cy, cz in ship.get_coordinates():
            self._grid[cx][cy][cz] = CellState3D.SHIP

        self.ships.append(ship)
        return True

    def place_ship_randomly(self, ship: Ship3D) -> bool:
        """Try to place a ship at a random valid position."""
        orientations = list(Orientation3D)
        random.shuffle(orientations)

        attempts = 0
        max_attempts = 1000

        while attempts < max_attempts:
            x = random.randint(0, self.size_x - 1)
            y = random.randint(0, self.size_y - 1)
            z = random.randint(0, self.size_z - 1)
            orientation = random.choice(orientations)

            if self.place_ship(ship, x, y, z, orientation):
                return True
            attempts += 1

        return False

    def receive_shot(self, x: int, y: int, z: int) -> Tuple[bool, Optional[Ship3D]]:
        """
        Process an incoming shot.
        Returns: (is_hit, ship_if_sunk)
        """
        if not self.is_valid_position(x, y, z):
            raise ValueError(f"Invalid position: ({x}, {y}, {z})")

        if (x, y, z) in self.shots_received:
            raise ValueError(f"Position already shot: ({x}, {y}, {z})")

        self.shots_received.add((x, y, z))

        # Check if any ship is hit
        for ship in self.ships:
            if ship.receive_hit(x, y, z):
                if ship.is_sunk:
                    # Mark all ship cells as sunk
                    for cx, cy, cz in ship.get_coordinates():
                        self._grid[cx][cy][cz] = CellState3D.SUNK
                    return True, ship
                else:
                    self._grid[x][y][z] = CellState3D.HIT
                    return True, None

        # Miss
        self._grid[x][y][z] = CellState3D.MISS
        return False, None

    @property
    def all_ships_sunk(self) -> bool:
        """Check if all ships have been destroyed."""
        return all(ship.is_sunk for ship in self.ships)

    @property
    def remaining_ships(self) -> List[Ship3D]:
        """Get list of ships that haven't been destroyed yet."""
        return [ship for ship in self.ships if not ship.is_sunk]

    def get_cell_state(self, x: int, y: int, z: int) -> CellState3D:
        """Get the state of a specific cell."""
        return self._grid[x][y][z]

    def get_available_shots(self) -> List[Tuple[int, int, int]]:
        """Get all positions that haven't been shot yet."""
        available = []
        for x in range(self.size_x):
            for y in range(self.size_y):
                for z in range(self.size_z):
                    if (x, y, z) not in self.shots_received:
                        available.append((x, y, z))
        return available

    def get_neighbors(self, x: int, y: int, z: int) -> List[Tuple[int, int, int]]:
        """Get all 6 adjacent cells (for hunting mode)."""
        neighbors = []
        for dx, dy, dz in ORIENTATION_VECTORS.values():
            nx, ny, nz = x + dx, y + dy, z + dz
            if self.is_valid_position(nx, ny, nz):
                neighbors.append((nx, ny, nz))
        return neighbors

    def to_dict(self, hide_ships: bool = False) -> dict:
        """
        Convert board to dictionary for JSON serialization.
        If hide_ships is True, unrevealed ship positions are hidden.
        """
        # For 3D, we return layers (z-slices)
        layers = []
        for z in range(self.size_z):
            layer = []
            for x in range(self.size_x):
                row = []
                for y in range(self.size_y):
                    state = self._grid[x][y][z]
                    if hide_ships and state == CellState3D.SHIP:
                        row.append(CellState3D.EMPTY.value)
                    else:
                        row.append(state.value)
                layer.append(row)
            layers.append(layer)

        return {
            "size": {"x": self.size_x, "y": self.size_y, "z": self.size_z},
            "total_cells": self.total_cells,
            "layers": layers,
            "ships": [ship.to_dict() for ship in self.ships] if not hide_ships else [],
            "shots_received": [list(s) for s in self.shots_received],
        }

    def to_observation(self) -> List[List[List[int]]]:
        """
        Convert board to numerical observation for RL.
        0 = unknown, 1 = miss, 2 = hit, 3 = sunk
        """
        obs = []
        for x in range(self.size_x):
            layer = []
            for y in range(self.size_y):
                row = []
                for z in range(self.size_z):
                    state = self._grid[x][y][z]
                    if state == CellState3D.EMPTY or state == CellState3D.SHIP:
                        row.append(0)  # Unknown
                    elif state == CellState3D.MISS:
                        row.append(1)
                    elif state == CellState3D.HIT:
                        row.append(2)
                    else:  # SUNK
                        row.append(3)
                layer.append(row)
            obs.append(layer)
        return obs
