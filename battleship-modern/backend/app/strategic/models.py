"""Core models for Strategic SpaceBattleship."""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Set, Tuple, Optional
from abc import ABC


class Direction(Enum):
    """Movement directions in 3D space."""
    UP = (0, 0, 1)      # +Z
    DOWN = (0, 0, -1)   # -Z
    NORTH = (0, -1, 0)  # -Y
    SOUTH = (0, 1, 0)   # +Y
    EAST = (1, 0, 0)    # +X
    WEST = (-1, 0, 0)   # -X


class ActionType(Enum):
    """Types of actions a bot can take."""
    FIRE = "fire"
    MOVE = "move"
    SCAN = "scan"


class CellStatus(Enum):
    """Status of a cell from the bot's perspective."""
    UNKNOWN = "unknown"
    EMPTY = "empty"      # Scanned, no ship
    HIT = "hit"          # Confirmed hit
    MISS = "miss"        # Shot missed
    DESTROYED = "destroyed"  # Ship fully destroyed here


@dataclass
class Position:
    """3D position in the game grid."""
    x: int
    y: int
    z: int

    def __add__(self, other: 'Position') -> 'Position':
        return Position(self.x + other.x, self.y + other.y, self.z + other.z)

    def __eq__(self, other) -> bool:
        if isinstance(other, Position):
            return self.x == other.x and self.y == other.y and self.z == other.z
        return False

    def __hash__(self) -> int:
        return hash((self.x, self.y, self.z))

    def to_tuple(self) -> Tuple[int, int, int]:
        return (self.x, self.y, self.z)

    @classmethod
    def from_tuple(cls, t: Tuple[int, int, int]) -> 'Position':
        return cls(t[0], t[1], t[2])

    def move(self, direction: Direction) -> 'Position':
        dx, dy, dz = direction.value
        return Position(self.x + dx, self.y + dy, self.z + dz)


@dataclass
class Ship:
    """A ship in the strategic game."""
    id: str
    name: str
    size: int
    positions: List[Position] = field(default_factory=list)
    hits: Set[Position] = field(default_factory=set)
    move_cooldown: int = 0  # Turns until this ship can move again

    @property
    def is_destroyed(self) -> bool:
        return len(self.hits) >= self.size

    @property
    def health(self) -> int:
        return self.size - len(self.hits)

    @property
    def can_move(self) -> bool:
        return self.move_cooldown == 0 and not self.is_destroyed

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "size": self.size,
            "positions": [p.to_tuple() for p in self.positions],
            "health": self.health,
            "can_move": self.can_move,
            "is_destroyed": self.is_destroyed
        }


# === ACTIONS ===

@dataclass
class Action(ABC):
    """Base class for all actions."""
    action_type: ActionType


@dataclass
class FireAction(Action):
    """Fire at a position."""
    target: Position
    action_type: ActionType = field(default=ActionType.FIRE, init=False)

    def to_dict(self) -> dict:
        return {"type": "fire", "target": self.target.to_tuple()}


@dataclass
class MoveAction(Action):
    """Move a ship in a direction."""
    ship_id: str
    direction: Direction
    action_type: ActionType = field(default=ActionType.MOVE, init=False)

    def to_dict(self) -> dict:
        return {"type": "move", "ship_id": self.ship_id, "direction": self.direction.name}


@dataclass
class ScanAction(Action):
    """Scan a 3x3x3 area centered on a position."""
    center: Position
    action_type: ActionType = field(default=ActionType.SCAN, init=False)

    def to_dict(self) -> dict:
        return {"type": "scan", "center": self.center.to_tuple()}


# === ACTION RESULTS ===

@dataclass
class FireResult:
    """Result of a fire action."""
    target: Position
    hit: bool
    destroyed_ship: Optional[str] = None  # Ship name if destroyed


@dataclass
class MoveResult:
    """Result of a move action."""
    ship_id: str
    success: bool
    new_positions: Optional[List[Position]] = None
    reason: Optional[str] = None  # Why it failed


@dataclass
class ScanResult:
    """Result of a scan action."""
    center: Position
    revealed: Dict[Position, CellStatus]  # What was found


@dataclass
class TurnResult:
    """Complete result of a turn's actions."""
    fire_results: List[FireResult] = field(default_factory=list)
    move_results: List[MoveResult] = field(default_factory=list)
    scan_results: List[ScanResult] = field(default_factory=list)
    incoming_hits: List[Position] = field(default_factory=list)  # Where enemy hit you
    ships_lost: List[str] = field(default_factory=list)  # Your ships that were destroyed


# === GAME STATE (what the bot sees) ===

@dataclass
class GameState:
    """The game state visible to a bot."""
    turn: int
    grid_size: Tuple[int, int, int]  # (x, y, z) dimensions

    # Your ships
    my_ships: List[Ship]

    # What you know about enemy territory
    known_cells: Dict[Position, CellStatus]

    # History
    my_shots: List[Position]
    enemy_shots_on_me: List[Position]

    # Actions available this turn
    actions_remaining: int

    # Enemy ships destroyed
    enemy_ships_destroyed: List[str]

    def get_cell_status(self, pos: Position) -> CellStatus:
        return self.known_cells.get(pos, CellStatus.UNKNOWN)

    def get_unknown_cells(self) -> List[Position]:
        """Get all cells we haven't explored."""
        x_size, y_size, z_size = self.grid_size
        unknown = []
        for x in range(x_size):
            for y in range(y_size):
                for z in range(z_size):
                    pos = Position(x, y, z)
                    if pos not in self.known_cells:
                        unknown.append(pos)
        return unknown

    def get_hits(self) -> List[Position]:
        """Get all confirmed hit positions."""
        return [pos for pos, status in self.known_cells.items()
                if status == CellStatus.HIT]

    def to_dict(self) -> dict:
        return {
            "turn": self.turn,
            "grid_size": self.grid_size,
            "my_ships": [s.to_dict() for s in self.my_ships],
            "known_cells": {str(p.to_tuple()): s.value for p, s in self.known_cells.items()},
            "actions_remaining": self.actions_remaining,
            "enemy_ships_destroyed": self.enemy_ships_destroyed
        }


# === GAME CONFIG ===

@dataclass
class GameConfig:
    """Configuration for a strategic game."""
    grid_size: Tuple[int, int, int] = (12, 12, 8)
    actions_per_turn: int = 3
    move_cooldown: int = 2  # Turns after moving before ship can move again
    scan_radius: int = 1    # Scan reveals (2r+1)^3 cube, so 1 = 3x3x3
    ships: List[Tuple[str, int]] = field(default_factory=lambda: [
        ("Carrier", 5),
        ("Battleship", 4),
        ("Cruiser", 3),
        ("Submarine", 3),
        ("Destroyer", 2),
    ])

    # Fog of war: you don't know if you hit unless you scan or destroy
    fog_of_war: bool = True

    @classmethod
    def small(cls) -> 'GameConfig':
        """Smaller config for quick testing (8x8x4 grid)."""
        return cls(
            grid_size=(8, 8, 4),
            ships=[
                ("Cruiser", 3),
                ("Submarine", 3),
                ("Destroyer", 2),
            ]
        )

    @classmethod
    def standard(cls) -> 'GameConfig':
        """Standard 12x12x8 grid."""
        return cls()
