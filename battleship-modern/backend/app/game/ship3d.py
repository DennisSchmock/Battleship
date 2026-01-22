"""3D Ship class for SpaceBattleship game."""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Tuple, Set


class Orientation3D(Enum):
    """6 possible orientations in 3D space."""
    X_POSITIVE = "x+"   # Along X axis (right)
    X_NEGATIVE = "x-"   # Along X axis (left)
    Y_POSITIVE = "y+"   # Along Y axis (forward)
    Y_NEGATIVE = "y-"   # Along Y axis (backward)
    Z_POSITIVE = "z+"   # Along Z axis (up)
    Z_NEGATIVE = "z-"   # Along Z axis (down)


# Direction vectors for each orientation
ORIENTATION_VECTORS = {
    Orientation3D.X_POSITIVE: (1, 0, 0),
    Orientation3D.X_NEGATIVE: (-1, 0, 0),
    Orientation3D.Y_POSITIVE: (0, 1, 0),
    Orientation3D.Y_NEGATIVE: (0, -1, 0),
    Orientation3D.Z_POSITIVE: (0, 0, 1),
    Orientation3D.Z_NEGATIVE: (0, 0, -1),
}


@dataclass
class Ship3D:
    """Represents a spaceship in 3D space."""

    name: str
    size: int
    position: Tuple[int, int, int] | None = None  # (x, y, z)
    orientation: Orientation3D | None = None
    hits: Set[Tuple[int, int, int]] = field(default_factory=set)

    # Space fleet definitions
    SPACE_CARRIER = ("Space Carrier", 6)       # Largest capital ship
    BATTLECRUISER = ("Battlecruiser", 5)       # Heavy assault ship
    DESTROYER = ("Destroyer", 4)                # Multi-role warship
    FIGHTER = ("Fighter Squadron", 3)           # Fast attack craft
    SCOUT = ("Scout", 2)                        # Recon vessel

    @classmethod
    def create_space_fleet(cls) -> List["Ship3D"]:
        """Create the standard space fleet."""
        return [
            cls(*cls.SPACE_CARRIER),
            cls(*cls.BATTLECRUISER),
            cls(*cls.DESTROYER),
            cls(*cls.FIGHTER),
            cls(*cls.SCOUT),
        ]

    @classmethod
    def create_large_fleet(cls) -> List["Ship3D"]:
        """Create a larger fleet for bigger maps."""
        return [
            cls(*cls.SPACE_CARRIER),
            cls(*cls.BATTLECRUISER),
            cls(*cls.BATTLECRUISER),
            cls(*cls.DESTROYER),
            cls(*cls.DESTROYER),
            cls(*cls.FIGHTER),
            cls(*cls.FIGHTER),
            cls(*cls.SCOUT),
            cls(*cls.SCOUT),
        ]

    def place(self, x: int, y: int, z: int, orientation: Orientation3D) -> None:
        """Place the ship at the given position."""
        self.position = (x, y, z)
        self.orientation = orientation
        self.hits = set()

    def get_coordinates(self) -> List[Tuple[int, int, int]]:
        """Get all coordinates occupied by this ship."""
        if self.position is None or self.orientation is None:
            return []

        x, y, z = self.position
        dx, dy, dz = ORIENTATION_VECTORS[self.orientation]
        coords = []

        for i in range(self.size):
            coords.append((x + dx * i, y + dy * i, z + dz * i))

        return coords

    def receive_hit(self, x: int, y: int, z: int) -> bool:
        """Register a hit on the ship. Returns True if this was a new hit."""
        coord = (x, y, z)
        if coord in self.get_coordinates() and coord not in self.hits:
            self.hits.add(coord)
            return True
        return False

    @property
    def is_sunk(self) -> bool:
        """Check if the ship is completely destroyed."""
        return len(self.hits) >= self.size

    @property
    def is_placed(self) -> bool:
        """Check if the ship has been placed in space."""
        return self.position is not None and self.orientation is not None

    def to_dict(self) -> dict:
        """Convert ship to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "size": self.size,
            "position": list(self.position) if self.position else None,
            "orientation": self.orientation.value if self.orientation else None,
            "hits": [list(h) for h in self.hits],
            "is_sunk": self.is_sunk,
        }
