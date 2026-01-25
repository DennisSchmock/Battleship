"""Fleet Commander - Advanced 3D Space Battle with Ship Abilities.

A strategic game where fleets with specialized ships battle in 3D space.
Features fog of war, unique ship abilities, and a shrinking battlefield (storm).
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Set, Tuple, Optional, Any
from abc import ABC, abstractmethod


# =============================================================================
# CORE TYPES
# =============================================================================

class Direction(Enum):
    """Movement directions in 3D space."""
    UP = (0, 0, 1)
    DOWN = (0, 0, -1)
    NORTH = (0, -1, 0)
    SOUTH = (0, 1, 0)
    EAST = (1, 0, 0)
    WEST = (-1, 0, 0)


class ShipType(Enum):
    """Types of ships with different roles."""
    SCOUT = "scout"
    DESTROYER = "destroyer"
    CRUISER = "cruiser"
    SUPPORT = "support"
    CARRIER = "carrier"
    ARTILLERY = "artillery"
    MINELAYER = "minelayer"


class AbilityType(Enum):
    """Types of abilities ships can have."""
    # Movement
    MOVE = "move"

    # Offensive
    FIRE = "fire"
    BURST_FIRE = "burst_fire"  # Multiple shots, can't move
    AREA_BOMBARDMENT = "area_bombardment"  # 3x3x3 area damage
    PRECISION_STRIKE = "precision_strike"  # Long range, needs lock-on
    PIERCING_SHOT = "piercing_shot"  # Damages multiple cells in line

    # Utility
    SCAN = "scan"
    LONG_RANGE_SCAN = "long_range_scan"
    ANTI_STEALTH_SCAN = "anti_stealth_scan"

    # Defensive
    SHIELD = "shield"
    REPAIR = "repair"

    # Special
    STEALTH = "stealth"  # Passive - harder to detect
    JAM = "jam"  # Block enemy scans
    DEPLOY_DECOY = "deploy_decoy"
    DEPLOY_MINE = "deploy_mine"
    DEPLOY_SENSOR = "deploy_sensor"
    LAUNCH_DRONE = "launch_drone"


class CellStatus(Enum):
    """What a player knows about a cell."""
    UNKNOWN = "unknown"
    EMPTY = "empty"  # Scanned/visited, no ship
    SHIP = "ship"  # Ship detected (scan reveals this)
    HIT = "hit"  # Confirmed hit
    DESTROYED = "destroyed"
    MINE = "mine"  # Detected mine
    DECOY = "decoy"  # Detected decoy
    STORM = "storm"  # Inside the storm


@dataclass(frozen=True)
class Position:
    """3D position in the game grid."""
    x: int
    y: int
    z: int

    def __add__(self, other: 'Position') -> 'Position':
        return Position(self.x + other.x, self.y + other.y, self.z + other.z)

    def to_tuple(self) -> Tuple[int, int, int]:
        return (self.x, self.y, self.z)

    @classmethod
    def from_tuple(cls, t: Tuple[int, int, int]) -> 'Position':
        return cls(t[0], t[1], t[2])

    def move(self, direction: Direction, distance: int = 1) -> 'Position':
        dx, dy, dz = direction.value
        return Position(self.x + dx * distance, self.y + dy * distance, self.z + dz * distance)

    def distance_to(self, other: 'Position') -> int:
        """Manhattan distance in 3D."""
        return abs(self.x - other.x) + abs(self.y - other.y) + abs(self.z - other.z)

    def in_range(self, other: 'Position', range_val: int) -> bool:
        """Check if other position is within range."""
        return self.distance_to(other) <= range_val


# =============================================================================
# SHIP ABILITIES
# =============================================================================

@dataclass
class AbilityConfig:
    """Configuration for a ship ability."""
    ability_type: AbilityType
    cooldown: int = 0  # Turns between uses
    range: int = 0  # Range in cells (0 = self only)
    damage: int = 0  # Damage dealt
    area_size: int = 0  # For area effects (radius)
    uses_per_turn: int = 1  # How many times can use per turn
    requires_lock: bool = False  # Needs to lock on turn before
    blocks_movement: bool = False  # Can't move if using this
    ap_cost: int = 1  # Action points cost to use this ability


@dataclass
class ActiveAbility:
    """Tracks an ability's current state on a ship."""
    config: AbilityConfig
    cooldown_remaining: int = 0
    uses_remaining: int = 0
    locked_target: Optional[Position] = None  # For precision strike

    def reset_turn(self):
        """Reset for new turn."""
        self.uses_remaining = self.config.uses_per_turn
        if self.cooldown_remaining > 0:
            self.cooldown_remaining -= 1

    def use(self):
        """Use the ability once."""
        self.uses_remaining -= 1
        self.cooldown_remaining = self.config.cooldown

    @property
    def can_use(self) -> bool:
        return self.uses_remaining > 0 and self.cooldown_remaining == 0


# =============================================================================
# SHIP DEFINITIONS
# =============================================================================

@dataclass
class ShipConfig:
    """Configuration for a ship type."""
    ship_type: ShipType
    name: str
    size: int  # Number of cells
    max_hp: int
    speed: int  # Max cells moved per turn
    stealth: float = 0.0  # 0-1, chance to avoid detection
    abilities: List[AbilityConfig] = field(default_factory=list)
    max_action_points: int = 3  # Action points available per turn (smaller ships = more AP)


# Define all ship types
SHIP_CONFIGS = {
    ShipType.SCOUT: ShipConfig(
        ship_type=ShipType.SCOUT,
        name="Scout",
        size=2,
        max_hp=2,
        speed=3,
        stealth=0.5,
        max_action_points=4,  # Small ship = more AP
        abilities=[
            AbilityConfig(AbilityType.SCAN, range=5, area_size=2),  # 5x5x5 area
            AbilityConfig(AbilityType.FIRE, range=2, damage=1),
        ]
    ),
    ShipType.DESTROYER: ShipConfig(
        ship_type=ShipType.DESTROYER,
        name="Destroyer",
        size=3,
        max_hp=4,
        speed=2,
        max_action_points=3,  # Medium ship
        abilities=[
            AbilityConfig(AbilityType.FIRE, range=4, damage=1),
            AbilityConfig(AbilityType.BURST_FIRE, range=4, damage=1, uses_per_turn=3, blocks_movement=True, cooldown=2, ap_cost=2),
            AbilityConfig(AbilityType.ANTI_STEALTH_SCAN, range=4, area_size=2),
        ]
    ),
    ShipType.CRUISER: ShipConfig(
        ship_type=ShipType.CRUISER,
        name="Cruiser",
        size=4,
        max_hp=6,
        speed=2,
        max_action_points=2,  # Large ship = fewer AP
        abilities=[
            AbilityConfig(AbilityType.FIRE, range=6, damage=2, ap_cost=2),  # Strong shot costs more
            AbilityConfig(AbilityType.AREA_BOMBARDMENT, range=5, damage=1, area_size=1, cooldown=3, ap_cost=2),
            AbilityConfig(AbilityType.SHIELD, uses_per_turn=1),  # Free defensive ability
        ]
    ),
    ShipType.SUPPORT: ShipConfig(
        ship_type=ShipType.SUPPORT,
        name="Support",
        size=3,
        max_hp=3,
        speed=1,
        max_action_points=3,  # Medium ship
        abilities=[
            AbilityConfig(AbilityType.REPAIR, range=2, damage=-1),  # 1 AP to heal
            AbilityConfig(AbilityType.JAM, range=0, area_size=2, cooldown=2, ap_cost=2),
            AbilityConfig(AbilityType.DEPLOY_DECOY, range=3, cooldown=3),
        ]
    ),
    ShipType.CARRIER: ShipConfig(
        ship_type=ShipType.CARRIER,
        name="Carrier",
        size=5,
        max_hp=8,
        speed=1,
        max_action_points=2,  # Very large ship
        abilities=[
            AbilityConfig(AbilityType.LONG_RANGE_SCAN, range=7, area_size=3),  # 1 AP
            AbilityConfig(AbilityType.LAUNCH_DRONE, range=0, cooldown=2),  # 1 AP
            AbilityConfig(AbilityType.FIRE, range=2, damage=1),  # 1 AP weak defense
        ]
    ),
    ShipType.ARTILLERY: ShipConfig(
        ship_type=ShipType.ARTILLERY,
        name="Artillery",
        size=3,
        max_hp=3,
        speed=1,
        max_action_points=3,  # Medium ship
        abilities=[
            AbilityConfig(AbilityType.PRECISION_STRIKE, range=12, damage=3, requires_lock=True, blocks_movement=True, ap_cost=3),
            AbilityConfig(AbilityType.PIERCING_SHOT, range=8, damage=2, blocks_movement=True, ap_cost=2),
            AbilityConfig(AbilityType.SCAN, range=3, area_size=1),  # 1 AP to scan
        ]
    ),
    ShipType.MINELAYER: ShipConfig(
        ship_type=ShipType.MINELAYER,
        name="Minelayer",
        size=2,
        max_hp=2,
        speed=2,
        stealth=0.3,
        max_action_points=4,  # Small nimble ship
        abilities=[
            AbilityConfig(AbilityType.DEPLOY_MINE, range=1, damage=2, cooldown=1, ap_cost=2),
            AbilityConfig(AbilityType.DEPLOY_SENSOR, range=2, cooldown=2),
            AbilityConfig(AbilityType.FIRE, range=2, damage=1),
        ]
    ),
}


# =============================================================================
# GAME ENTITIES
# =============================================================================

@dataclass
class Ship:
    """A ship in the game."""
    id: str
    config: ShipConfig
    owner: int  # Player 0 or 1
    positions: List[Position]  # Cells occupied
    hp: int
    abilities: Dict[AbilityType, ActiveAbility] = field(default_factory=dict)
    movement_remaining: int = 0
    has_moved_this_turn: bool = False
    action_points: int = 0  # Current AP remaining this turn
    is_destroyed: bool = False

    def __post_init__(self):
        # Initialize abilities from config
        for ability_cfg in self.config.abilities:
            self.abilities[ability_cfg.ability_type] = ActiveAbility(ability_cfg)
        # Initialize action points
        self.action_points = self.config.max_action_points

    @property
    def center(self) -> Position:
        """Get center position of ship."""
        if not self.positions:
            raise ValueError("Ship has no positions")
        return self.positions[len(self.positions) // 2]

    def can_afford(self, cost: int) -> bool:
        """Check if ship has enough action points."""
        return self.action_points >= cost

    def spend_ap(self, cost: int) -> bool:
        """Spend action points. Returns True if successful."""
        if not self.can_afford(cost):
            return False
        self.action_points -= cost
        return True

    def reset_turn(self):
        """Reset ship for new turn."""
        self.movement_remaining = self.config.speed
        self.has_moved_this_turn = False
        self.action_points = self.config.max_action_points
        for ability in self.abilities.values():
            ability.reset_turn()

    def take_damage(self, damage: int) -> int:
        """Take damage, return actual damage taken."""
        # Check for shield
        if AbilityType.SHIELD in self.abilities:
            shield = self.abilities[AbilityType.SHIELD]
            if shield.can_use:
                shield.use()
                damage = max(0, damage - 2)  # Shield absorbs 2

        actual = min(damage, self.hp)
        self.hp -= actual
        if self.hp <= 0:
            self.is_destroyed = True
        return actual

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.config.ship_type.value,
            "name": self.config.name,
            "owner": self.owner,
            "positions": [p.to_tuple() for p in self.positions],
            "hp": self.hp,
            "max_hp": self.config.max_hp,
            "speed": self.config.speed,
            "movement_remaining": self.movement_remaining,
            "action_points": self.action_points,
            "max_action_points": self.config.max_action_points,
            "has_acted": self.action_points == 0,  # Legacy: true if no AP left
            "is_destroyed": self.is_destroyed,
            "abilities": {
                k.value: {"can_use": v.can_use, "cooldown": v.cooldown_remaining}
                for k, v in self.abilities.items()
            }
        }


@dataclass
class Drone:
    """A small drone launched by a carrier."""
    id: str
    owner: int
    position: Position
    hp: int = 1
    speed: int = 2
    scan_range: int = 3
    attack_damage: int = 1
    attack_range: int = 1
    is_destroyed: bool = False


@dataclass
class Mine:
    """An invisible mine placed by a minelayer."""
    id: str
    owner: int
    position: Position
    damage: int = 2
    triggered: bool = False


@dataclass
class Sensor:
    """An invisible sensor that detects ships passing through."""
    id: str
    owner: int
    position: Position
    range: int = 2  # Detection radius


@dataclass
class Decoy:
    """A fake signal that appears as a ship on scans."""
    id: str
    owner: int
    position: Position
    turns_remaining: int = 5


# =============================================================================
# STORM MECHANIC
# =============================================================================

@dataclass
class Storm:
    """The shrinking battlefield storm."""
    # Storm shrinks the playable area over time
    current_bounds: Tuple[Position, Position]  # Min and max corners
    final_bounds: Tuple[Position, Position]  # Where storm stops
    shrink_rate: int = 1  # Cells to shrink per interval
    shrink_interval: int = 10  # Turns between shrinks
    damage_per_turn: int = 1  # Damage to ships in storm
    turns_until_shrink: int = 10

    def is_in_storm(self, pos: Position) -> bool:
        """Check if position is inside the storm (outside safe zone)."""
        min_pos, max_pos = self.current_bounds
        return not (
            min_pos.x <= pos.x <= max_pos.x and
            min_pos.y <= pos.y <= max_pos.y and
            min_pos.z <= pos.z <= max_pos.z
        )

    def shrink(self):
        """Shrink the safe zone."""
        min_pos, max_pos = self.current_bounds
        final_min, final_max = self.final_bounds

        new_min = Position(
            min(min_pos.x + self.shrink_rate, final_min.x),
            min(min_pos.y + self.shrink_rate, final_min.y),
            min(min_pos.z + self.shrink_rate, final_min.z)
        )
        new_max = Position(
            max(max_pos.x - self.shrink_rate, final_max.x),
            max(max_pos.y - self.shrink_rate, final_max.y),
            max(max_pos.z - self.shrink_rate, final_max.z)
        )

        self.current_bounds = (new_min, new_max)
        self.turns_until_shrink = self.shrink_interval

    def tick(self) -> bool:
        """Advance storm timer, return True if shrunk this tick."""
        self.turns_until_shrink -= 1
        if self.turns_until_shrink <= 0:
            self.shrink()
            return True
        return False


# =============================================================================
# GAME STATE
# =============================================================================

@dataclass
class FleetConfig:
    """Configuration for a player's starting fleet."""
    ships: List[ShipType] = field(default_factory=lambda: [
        ShipType.DESTROYER,
        ShipType.DESTROYER,
        ShipType.CRUISER,
        ShipType.SUPPORT,
        ShipType.CARRIER,
        ShipType.ARTILLERY,
        ShipType.MINELAYER,
    ])


@dataclass
class GameConfig:
    """Configuration for a Fleet Commander game."""
    # Grid size
    grid_size: Tuple[int, int, int] = (32, 32, 16)  # Large 3D battlefield

    # Starting zones (x ranges for each player)
    player1_zone: Tuple[int, int] = (0, 7)  # x = 0-7
    player2_zone: Tuple[int, int] = (24, 31)  # x = 24-31

    # Fleet configuration
    fleet_config: FleetConfig = field(default_factory=FleetConfig)

    # Each ship gets 1 action per turn (move OR fire OR ability)
    # No global action points - simpler, more chess-like

    # Storm configuration - slow nudging, not stressful
    storm_start_turn: int = 50  # Storm doesn't start until turn 50
    storm_shrink_interval: int = 15  # Shrinks every 15 turns
    storm_shrink_rate: int = 1  # 1 cell at a time
    storm_damage: int = 1

    # Fog of war - disabled for tactical chess-like gameplay
    fog_of_war: bool = False
    memory_decay_turns: int = 0  # Not used when fog_of_war is False

    # Victory conditions
    max_turns: int = 500  # Allow long games

    @classmethod
    def small(cls) -> 'GameConfig':
        """Smaller config for faster games."""
        return cls(
            grid_size=(24, 24, 12),
            player1_zone=(0, 5),
            player2_zone=(18, 23),
            fleet_config=FleetConfig(ships=[
                ShipType.DESTROYER,
                ShipType.DESTROYER,
                ShipType.CRUISER,
                ShipType.SUPPORT,
                ShipType.CARRIER,
                ShipType.ARTILLERY,
                ShipType.MINELAYER,
            ]),
            storm_start_turn=40,
            storm_shrink_interval=12,
            storm_damage=1,
            max_turns=300,
        )


@dataclass
class KnownCell:
    """What a player knows about a cell."""
    status: CellStatus
    turn_observed: int
    ship_id: Optional[str] = None  # If ship detected


@dataclass
class PlayerState:
    """State for one player."""
    player_id: int
    name: str
    ships: List[Ship] = field(default_factory=list)
    drones: List[Drone] = field(default_factory=list)
    mines: List[Mine] = field(default_factory=list)
    sensors: List[Sensor] = field(default_factory=list)
    decoys: List[Decoy] = field(default_factory=list)

    # Fog of war - what this player knows
    known_cells: Dict[Position, KnownCell] = field(default_factory=dict)
    visited_cells: Set[Position] = field(default_factory=set)

    @property
    def ships_alive(self) -> int:
        """Count of all ships still alive."""
        return sum(1 for s in self.ships if not s.is_destroyed)

    @property
    def combat_ships_alive(self) -> int:
        """Count of all ships still alive (legacy name for compatibility)."""
        return self.ships_alive


# =============================================================================
# ACTIONS
# =============================================================================

@dataclass
class Action(ABC):
    """Base class for all actions."""
    ship_id: str

    @abstractmethod
    def to_dict(self) -> dict:
        pass


@dataclass
class MoveAction(Action):
    """Move a ship."""
    path: List[Position]  # Path to follow (can be multiple cells based on speed)

    def to_dict(self) -> dict:
        return {
            "type": "move",
            "ship_id": self.ship_id,
            "path": [p.to_tuple() for p in self.path]
        }


@dataclass
class FireAction(Action):
    """Fire at a target."""
    target: Position
    ability: AbilityType = AbilityType.FIRE

    def to_dict(self) -> dict:
        return {
            "type": "fire",
            "ship_id": self.ship_id,
            "target": self.target.to_tuple(),
            "ability": self.ability.value if self.ability else None
        }


@dataclass
class ScanAction(Action):
    """Scan an area."""
    center: Position
    ability: AbilityType = AbilityType.SCAN

    def to_dict(self) -> dict:
        return {
            "type": "scan",
            "ship_id": self.ship_id,
            "center": self.center.to_tuple(),
            "ability": self.ability.value if self.ability else None
        }


@dataclass
class AbilityAction(Action):
    """Use a special ability."""
    ability: AbilityType
    target: Optional[Position] = None
    target_ship_id: Optional[str] = None  # For repair

    def to_dict(self) -> dict:
        return {
            "type": "ability",
            "ship_id": self.ship_id,
            "ability": self.ability.value,
            "target": self.target.to_tuple() if self.target else None,
            "target_ship_id": self.target_ship_id
        }


@dataclass
class LockOnAction(Action):
    """Lock on to a target for precision strike."""
    target: Position

    def to_dict(self) -> dict:
        return {
            "type": "lock_on",
            "ship_id": self.ship_id,
            "target": self.target.to_tuple()
        }


# =============================================================================
# ACTION RESULTS
# =============================================================================

@dataclass
class ActionResult:
    """Result of an action."""
    success: bool
    action: Action
    message: str = ""
    damage_dealt: int = 0
    ships_hit: List[str] = field(default_factory=list)
    ships_destroyed: List[str] = field(default_factory=list)
    cells_revealed: Dict[Position, CellStatus] = field(default_factory=dict)
    triggered_mines: List[str] = field(default_factory=list)


@dataclass
class TurnResult:
    """Result of a player's turn."""
    player_id: int
    turn: int
    actions_taken: List[ActionResult] = field(default_factory=list)
    storm_damage_taken: Dict[str, int] = field(default_factory=dict)  # ship_id -> damage
    storm_shrunk: bool = False
