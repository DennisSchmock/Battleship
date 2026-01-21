"""Ship class for Battleship game."""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Tuple, Set


class Orientation(Enum):
    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"


@dataclass
class Ship:
    """Represents a ship on the battlefield."""

    name: str
    size: int
    position: Tuple[int, int] | None = None  # (row, col)
    orientation: Orientation | None = None
    hits: Set[Tuple[int, int]] = field(default_factory=set)

    # Standard Battleship fleet
    CARRIER = ("Carrier", 5)
    BATTLESHIP = ("Battleship", 4)
    CRUISER = ("Cruiser", 3)
    SUBMARINE = ("Submarine", 3)
    DESTROYER = ("Destroyer", 2)

    @classmethod
    def create_standard_fleet(cls) -> List["Ship"]:
        """Create the standard Battleship fleet."""
        return [
            cls(*cls.CARRIER),
            cls(*cls.BATTLESHIP),
            cls(*cls.CRUISER),
            cls(*cls.SUBMARINE),
            cls(*cls.DESTROYER),
        ]

    def place(self, row: int, col: int, orientation: Orientation) -> None:
        """Place the ship at the given position."""
        self.position = (row, col)
        self.orientation = orientation
        self.hits = set()

    def get_coordinates(self) -> List[Tuple[int, int]]:
        """Get all coordinates occupied by this ship."""
        if self.position is None or self.orientation is None:
            return []

        row, col = self.position
        coords = []

        for i in range(self.size):
            if self.orientation == Orientation.HORIZONTAL:
                coords.append((row, col + i))
            else:
                coords.append((row + i, col))

        return coords

    def receive_hit(self, row: int, col: int) -> bool:
        """Register a hit on the ship. Returns True if this was a new hit."""
        coord = (row, col)
        if coord in self.get_coordinates() and coord not in self.hits:
            self.hits.add(coord)
            return True
        return False

    @property
    def is_sunk(self) -> bool:
        """Check if the ship is completely sunk."""
        return len(self.hits) >= self.size

    @property
    def is_placed(self) -> bool:
        """Check if the ship has been placed on the board."""
        return self.position is not None and self.orientation is not None

    def to_dict(self) -> dict:
        """Convert ship to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "size": self.size,
            "position": self.position,
            "orientation": self.orientation.value if self.orientation else None,
            "hits": list(self.hits),
            "is_sunk": self.is_sunk,
        }
