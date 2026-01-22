"""3D Player classes for SpaceBattleship game."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Set
import random

from .board3d import Board3D, CellState3D
from .ship3d import Ship3D, Orientation3D, ORIENTATION_VECTORS


@dataclass
class Player3D(ABC):
    """Abstract base class for SpaceBattleship players."""

    name: str
    board: Board3D = field(default_factory=Board3D)
    shots_fired: Set[Tuple[int, int, int]] = field(default_factory=set)
    hits: int = 0
    misses: int = 0

    def reset(self) -> None:
        """Reset player for a new game."""
        self.board = Board3D()
        self.shots_fired = set()
        self.hits = 0
        self.misses = 0

    @abstractmethod
    def place_ships(self, fleet: List[Ship3D]) -> None:
        """Place all ships on the board."""
        pass

    @abstractmethod
    def get_shot(self, opponent_state: dict) -> Tuple[int, int, int]:
        """Determine where to shoot next."""
        pass

    def record_shot_result(self, x: int, y: int, z: int,
                           is_hit: bool, sunk_ship: Optional[Ship3D] = None) -> None:
        """Record the result of a shot."""
        self.shots_fired.add((x, y, z))
        if is_hit:
            self.hits += 1
        else:
            self.misses += 1

    @property
    def accuracy(self) -> float:
        """Calculate shot accuracy."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    def to_dict(self) -> dict:
        """Convert player stats to dictionary."""
        return {
            "name": self.name,
            "shots_fired": len(self.shots_fired),
            "hits": self.hits,
            "misses": self.misses,
            "accuracy": round(self.accuracy * 100, 1),
            "ships_remaining": len(self.board.remaining_ships),
        }


@dataclass
class RandomPlayer3D(Player3D):
    """AI that shoots randomly in 3D space."""

    def place_ships(self, fleet: List[Ship3D]) -> None:
        """Place ships randomly."""
        for ship in fleet:
            if not self.board.place_ship_randomly(ship):
                raise RuntimeError(f"Could not place ship: {ship.name}")

    def get_shot(self, opponent_state: dict) -> Tuple[int, int, int]:
        """Pick a random unshot position."""
        shots_received = set(tuple(s) for s in opponent_state.get("shots_received", []))
        size = opponent_state["size"]

        available = []
        for x in range(size["x"]):
            for y in range(size["y"]):
                for z in range(size["z"]):
                    if (x, y, z) not in shots_received and (x, y, z) not in self.shots_fired:
                        available.append((x, y, z))

        return random.choice(available) if available else (0, 0, 0)


@dataclass
class HunterAI3D(Player3D):
    """
    3D Hunter AI - based on the original Java R58 strategy.

    Uses:
    - 3D checkerboard pattern for initial search
    - 6-directional hunting when a hit is found
    - Target queue for systematic destruction
    """

    hunt_targets: List[Tuple[int, int, int]] = field(default_factory=list)
    confirmed_hits: Set[Tuple[int, int, int]] = field(default_factory=set)

    def place_ships(self, fleet: List[Ship3D]) -> None:
        """Place ships randomly (could be made smarter)."""
        for ship in fleet:
            if not self.board.place_ship_randomly(ship):
                raise RuntimeError(f"Could not place ship: {ship.name}")

    def get_shot(self, opponent_state: dict) -> Tuple[int, int, int]:
        """Get next shot using hunt/target mode."""
        shots_received = set(tuple(s) for s in opponent_state.get("shots_received", []))
        size = opponent_state["size"]

        def is_valid(pos: Tuple[int, int, int]) -> bool:
            x, y, z = pos
            return (0 <= x < size["x"] and
                    0 <= y < size["y"] and
                    0 <= z < size["z"])

        # Filter out already-shot and invalid positions from hunt targets
        self.hunt_targets = [
            t for t in self.hunt_targets
            if is_valid(t) and t not in shots_received and t not in self.shots_fired
        ]

        # Target mode: if we have hunting targets, pursue them
        if self.hunt_targets:
            return self.hunt_targets.pop(0)

        # Hunt mode: use 3D checkerboard pattern
        return self._checkerboard_shot(size, shots_received)

    def _checkerboard_shot(self, size: dict, shots: Set[Tuple[int, int, int]]) -> Tuple[int, int, int]:
        """
        3D checkerboard pattern - only hit cells where (x + y + z) % 2 == 0.
        This is optimal for finding ships of size 2+.
        """
        candidates = []

        for x in range(size["x"]):
            for y in range(size["y"]):
                for z in range(size["z"]):
                    if (x, y, z) not in shots and (x, y, z) not in self.shots_fired:
                        # 3D checkerboard: alternating pattern
                        if (x + y + z) % 2 == 0:
                            candidates.append((x, y, z))

        # If no checkerboard cells left, fall back to any available
        if not candidates:
            for x in range(size["x"]):
                for y in range(size["y"]):
                    for z in range(size["z"]):
                        if (x, y, z) not in shots and (x, y, z) not in self.shots_fired:
                            candidates.append((x, y, z))

        return random.choice(candidates) if candidates else (0, 0, 0)

    def record_shot_result(self, x: int, y: int, z: int,
                           is_hit: bool, sunk_ship: Optional[Ship3D] = None) -> None:
        """Record result and update hunt targets if hit."""
        super().record_shot_result(x, y, z, is_hit, sunk_ship)

        if is_hit:
            self.confirmed_hits.add((x, y, z))

            if sunk_ship:
                # Ship sunk - remove its coordinates from confirmed hits
                sunk_coords = set(tuple(c) for c in sunk_ship.get_coordinates())
                self.confirmed_hits -= sunk_coords
                # Clear hunt targets related to this ship
                self.hunt_targets = [
                    t for t in self.hunt_targets
                    if not self._is_adjacent_to_any(t, sunk_coords)
                ]
            else:
                # Hit but not sunk - add all 6 neighbors to hunt targets
                for dx, dy, dz in ORIENTATION_VECTORS.values():
                    neighbor = (x + dx, y + dy, z + dz)
                    if (neighbor not in self.shots_fired and
                            neighbor not in self.hunt_targets):
                        self.hunt_targets.append(neighbor)

    def _is_adjacent_to_any(self, pos: Tuple[int, int, int],
                            coords: Set[Tuple[int, int, int]]) -> bool:
        """Check if position is adjacent to any coordinate in the set."""
        x, y, z = pos
        for dx, dy, dz in ORIENTATION_VECTORS.values():
            if (x + dx, y + dy, z + dz) in coords:
                return True
        return False


@dataclass
class SmartHunter3D(HunterAI3D):
    """
    Enhanced 3D Hunter with directional tracking.

    When multiple hits are found in a line, prioritizes continuing
    that line in both directions.
    """

    hit_directions: dict = field(default_factory=dict)

    def record_shot_result(self, x: int, y: int, z: int,
                           is_hit: bool, sunk_ship: Optional[Ship3D] = None) -> None:
        """Record result with directional analysis."""
        super().record_shot_result(x, y, z, is_hit, sunk_ship)

        if is_hit and not sunk_ship:
            # Check if this hit extends a line from previous hits
            for prev_hit in self.confirmed_hits:
                if prev_hit == (x, y, z):
                    continue

                dx = x - prev_hit[0]
                dy = y - prev_hit[1]
                dz = z - prev_hit[2]

                # Check if it's a unit direction (adjacent)
                if abs(dx) + abs(dy) + abs(dz) == 1:
                    # Found a direction - prioritize continuing this line
                    direction = (dx, dy, dz)
                    opposite = (-dx, -dy, -dz)

                    # Add cells in this direction to front of hunt queue
                    next_forward = (x + dx, y + dy, z + dz)
                    next_backward = (prev_hit[0] - dx, prev_hit[1] - dy, prev_hit[2] - dz)

                    for next_pos in [next_forward, next_backward]:
                        if (next_pos not in self.shots_fired and
                                next_pos not in self.hunt_targets):
                            self.hunt_targets.insert(0, next_pos)
