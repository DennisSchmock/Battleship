"""Bot Interface for Fleet Commander.

Provides a clean API for AI bots to play the game.
"""
from abc import ABC, abstractmethod
from typing import List, Tuple, Optional, Dict, Set
from dataclasses import dataclass
import random

from .models import (
    Position, Direction, ShipType, AbilityType, CellStatus,
    Ship, GameConfig, Action, MoveAction, FireAction, ScanAction,
    AbilityAction, LockOnAction, TurnResult, SHIP_CONFIGS
)


@dataclass
class AbilityInfo:
    """Information about a ship ability."""
    ability_type: AbilityType
    can_use: bool  # Can use this turn (not on cooldown, has uses remaining)
    cooldown_remaining: int  # Turns until available
    range: int  # Range in cells
    damage: int  # Damage dealt (negative for healing)
    area_size: int  # Radius for area effects (0 = single target)
    uses_per_turn: int  # How many times can use per turn
    blocks_movement: bool  # Can't move if using this
    ap_cost: int = 1  # Action points cost to use this ability


@dataclass
class VisibleShip:
    """A ship visible to the bot (either own or detected enemy)."""
    id: str
    positions: List[Position]
    is_own: bool
    # Only available for own ships:
    ship_type: Optional[ShipType] = None
    hp: Optional[int] = None
    max_hp: Optional[int] = None
    speed: Optional[int] = None
    movement_remaining: Optional[int] = None
    action_points: int = 0  # Current AP remaining this turn
    max_action_points: int = 0  # Maximum AP per turn
    has_acted: bool = False  # Legacy: True if AP == 0
    abilities: Optional[Dict[AbilityType, bool]] = None  # ability -> can_use (legacy)
    ability_info: Optional[Dict[AbilityType, AbilityInfo]] = None  # Full ability details

    def can_act(self) -> bool:
        """Check if this ship can still act this turn (has AP remaining)."""
        return self.action_points > 0 and self.hp is not None and self.hp > 0

    def can_afford(self, cost: int) -> bool:
        """Check if ship has enough AP for an action."""
        return self.action_points >= cost

    def can_fire(self) -> bool:
        """Check if this ship can fire this turn (has ability and can afford it)."""
        if not self.ability_info:
            return False
        for ab_type in [AbilityType.FIRE, AbilityType.BURST_FIRE, AbilityType.AREA_BOMBARDMENT,
                        AbilityType.PRECISION_STRIKE, AbilityType.PIERCING_SHOT]:
            if ab_type in self.ability_info:
                info = self.ability_info[ab_type]
                if info.can_use and self.can_afford(info.ap_cost):
                    return True
        return False

    def can_scan(self) -> bool:
        """Check if this ship can scan this turn (has ability and can afford it)."""
        if not self.ability_info:
            return False
        for ab_type in [AbilityType.SCAN, AbilityType.LONG_RANGE_SCAN, AbilityType.ANTI_STEALTH_SCAN]:
            if ab_type in self.ability_info:
                info = self.ability_info[ab_type]
                if info.can_use and self.can_afford(info.ap_cost):
                    return True
        return False

    def can_move(self, distance: int = 1) -> bool:
        """Check if this ship can move at least 'distance' cells (has movement and AP)."""
        return (self.movement_remaining is not None and
                self.movement_remaining >= distance and
                self.can_afford(distance))

    def get_fire_range(self) -> int:
        """Get the maximum fire range of this ship."""
        if not self.ability_info:
            return 0
        max_range = 0
        for ab_type in [AbilityType.FIRE, AbilityType.BURST_FIRE, AbilityType.AREA_BOMBARDMENT,
                        AbilityType.PRECISION_STRIKE, AbilityType.PIERCING_SHOT]:
            if ab_type in self.ability_info:
                max_range = max(max_range, self.ability_info[ab_type].range)
        return max_range

    def get_scan_range(self) -> int:
        """Get the maximum scan range of this ship."""
        if not self.ability_info:
            return 0
        max_range = 0
        for ab_type in [AbilityType.SCAN, AbilityType.LONG_RANGE_SCAN, AbilityType.ANTI_STEALTH_SCAN]:
            if ab_type in self.ability_info:
                max_range = max(max_range, self.ability_info[ab_type].range)
        return max_range

    def get_best_fire_ability(self) -> Optional[AbilityType]:
        """Get the best available fire ability (highest damage that can be used and afforded)."""
        if not self.ability_info:
            return None
        best = None
        best_damage = 0
        for ab_type in [AbilityType.FIRE, AbilityType.BURST_FIRE, AbilityType.AREA_BOMBARDMENT,
                        AbilityType.PRECISION_STRIKE, AbilityType.PIERCING_SHOT]:
            if ab_type in self.ability_info:
                info = self.ability_info[ab_type]
                if info.can_use and self.can_afford(info.ap_cost) and info.damage > best_damage:
                    best_damage = info.damage
                    best = ab_type
        return best

    def get_affordable_fire_abilities(self) -> List[Tuple[AbilityType, AbilityInfo]]:
        """Get all fire abilities that can be used and afforded."""
        if not self.ability_info:
            return []
        result = []
        for ab_type in [AbilityType.FIRE, AbilityType.BURST_FIRE, AbilityType.AREA_BOMBARDMENT,
                        AbilityType.PRECISION_STRIKE, AbilityType.PIERCING_SHOT]:
            if ab_type in self.ability_info:
                info = self.ability_info[ab_type]
                if info.can_use and self.can_afford(info.ap_cost):
                    result.append((ab_type, info))
        return result

    @property
    def center(self) -> Position:
        """Get center position of ship."""
        return self.positions[len(self.positions) // 2]


@dataclass
class GameView:
    """The game state from a bot's perspective."""
    turn: int
    my_player_id: int
    grid_size: Tuple[int, int, int]

    # Ships - each ship has action points (AP) per turn
    # Move costs 1 AP per cell, abilities cost varies (see ability_info.ap_cost)
    my_ships: List[VisibleShip]
    visible_enemy_ships: List[VisibleShip]

    # Fog of war
    known_cells: Dict[Position, CellStatus]

    # My deployables
    my_mines: List[Tuple[str, Position]]
    my_sensors: List[Tuple[str, Position]]
    my_decoys: List[Tuple[str, Position]]
    my_drones: List[Tuple[str, Position, int]]  # id, pos, hp

    # Storm
    storm_min: Optional[Position]
    storm_max: Optional[Position]
    storm_turns_until_shrink: int
    storm_damage: int

    def is_in_storm(self, pos: Position) -> bool:
        """Check if a position is in the storm."""
        if self.storm_min is None or self.storm_max is None:
            return False
        return not (
            self.storm_min.x <= pos.x <= self.storm_max.x and
            self.storm_min.y <= pos.y <= self.storm_max.y and
            self.storm_min.z <= pos.z <= self.storm_max.z
        )

    def is_valid_position(self, pos: Position) -> bool:
        """Check if position is in grid."""
        x, y, z = self.grid_size
        return 0 <= pos.x < x and 0 <= pos.y < y and 0 <= pos.z < z

    def get_cell_status(self, pos: Position) -> CellStatus:
        """Get known status of a cell."""
        return self.known_cells.get(pos, CellStatus.UNKNOWN)

    def get_unknown_cells(self) -> List[Position]:
        """Get all cells we don't know about."""
        x, y, z = self.grid_size
        unknown = []
        for px in range(x):
            for py in range(y):
                for pz in range(z):
                    pos = Position(px, py, pz)
                    if pos not in self.known_cells:
                        unknown.append(pos)
        return unknown

    def find_ship_by_id(self, ship_id: str) -> Optional[VisibleShip]:
        """Find one of my ships by ID."""
        for ship in self.my_ships:
            if ship.id == ship_id:
                return ship
        return None

    def get_ships_that_can_act(self) -> List[VisibleShip]:
        """Get all my ships that can still act this turn (haven't acted yet)."""
        return [s for s in self.my_ships if s.can_act()]

    def get_ships_that_can_fire(self) -> List[VisibleShip]:
        """Get all my ships that can fire this turn."""
        return [s for s in self.my_ships if s.can_act() and s.can_fire()]

    def get_ships_that_can_scan(self) -> List[VisibleShip]:
        """Get all my ships that can scan this turn."""
        return [s for s in self.my_ships if s.can_act() and s.can_scan()]

    def get_ships_that_can_move(self) -> List[VisibleShip]:
        """Get all my ships that can move this turn."""
        return [s for s in self.my_ships if s.can_act() and s.can_move()]

    def get_ships_by_type(self, ship_type: ShipType) -> List[VisibleShip]:
        """Get all my ships of a specific type."""
        return [s for s in self.my_ships if s.ship_type == ship_type and s.hp and s.hp > 0]

    def get_alive_ships(self) -> List[VisibleShip]:
        """Get all my ships that are still alive."""
        return [s for s in self.my_ships if s.hp and s.hp > 0]

    def get_damaged_ships(self) -> List[VisibleShip]:
        """Get all my ships that are damaged but alive."""
        return [s for s in self.my_ships if s.hp and s.max_hp and 0 < s.hp < s.max_hp]

    def get_enemies_in_range_of(self, ship: VisibleShip) -> List[VisibleShip]:
        """Get all visible enemies within firing range of a ship."""
        fire_range = ship.get_fire_range()
        if fire_range == 0:
            return []
        return [e for e in self.visible_enemy_ships
                if any(ship.center.distance_to(p) <= fire_range for p in e.positions)]


class FleetBot(ABC):
    """
    Base class for Fleet Commander bots.

    Implement this class to create your own AI for Fleet Commander.
    """

    @abstractmethod
    def get_name(self) -> str:
        """Return the name of your bot."""
        pass

    @abstractmethod
    def place_fleet(self, config: GameConfig, zone_x_min: int, zone_x_max: int
                    ) -> List[Tuple[ShipType, Position, Direction]]:
        """
        Place your fleet in your starting zone.

        Args:
            config: Game configuration
            zone_x_min: Minimum X coordinate of your zone
            zone_x_max: Maximum X coordinate of your zone

        Returns:
            List of (ship_type, start_position, direction) for each ship
        """
        pass

    @abstractmethod
    def get_actions(self, view: GameView) -> List[Action]:
        """
        Decide what actions to take this turn.

        Args:
            view: Current game state from your perspective

        Returns:
            List of actions to execute
        """
        pass

    def on_turn_result(self, result: TurnResult) -> None:
        """
        Called after your turn with results.

        Override to learn from results (optional).
        """
        pass

    def on_game_start(self, config: GameConfig) -> None:
        """
        Called when game starts.

        Override to initialize state (optional).
        """
        pass

    def on_game_end(self, won: bool, view: GameView) -> None:
        """
        Called when game ends.

        Override to learn from the game (optional).
        """
        pass


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def random_fleet_placement(
    config: GameConfig,
    zone_x_min: int,
    zone_x_max: int
) -> List[Tuple[ShipType, Position, Direction]]:
    """Helper to randomly place a fleet."""
    placements = []
    occupied: Set[Position] = set()
    y_max, z_max = config.grid_size[1], config.grid_size[2]

    for ship_type in config.fleet_config.ships:
        ship_config = SHIP_CONFIGS[ship_type]
        placed = False

        for _ in range(1000):
            start = Position(
                random.randint(zone_x_min, zone_x_max),
                random.randint(0, y_max - 1),
                random.randint(0, z_max - 1)
            )
            direction = random.choice(list(Direction))

            # Calculate positions
            positions = [start]
            current = start
            valid = True

            for _ in range(ship_config.size - 1):
                current = current.move(direction)
                if not (0 <= current.x < config.grid_size[0] and
                        0 <= current.y < y_max and
                        0 <= current.z < z_max):
                    valid = False
                    break
                if not (zone_x_min <= current.x <= zone_x_max):
                    valid = False
                    break
                if current in occupied:
                    valid = False
                    break
                positions.append(current)

            if not valid or start in occupied:
                continue

            # Add placement
            placements.append((ship_type, start, direction))
            occupied.update(positions)
            placed = True
            break

        if not placed:
            raise RuntimeError(f"Could not place {ship_type.value}")

    return placements


def get_adjacent_positions(pos: Position, grid_size: Tuple[int, int, int]) -> List[Position]:
    """Get all valid adjacent positions."""
    x_max, y_max, z_max = grid_size
    adjacent = []
    for direction in Direction:
        new_pos = pos.move(direction)
        if 0 <= new_pos.x < x_max and 0 <= new_pos.y < y_max and 0 <= new_pos.z < z_max:
            adjacent.append(new_pos)
    return adjacent


def find_path(start: Position, end: Position, max_distance: int,
              grid_size: Tuple[int, int, int],
              blocked: Set[Position]) -> Optional[List[Position]]:
    """
    Find a path from start to end, avoiding blocked cells.

    Returns path (list of positions to move through) or None if no path.
    """
    if start.distance_to(end) > max_distance:
        return None

    # Simple BFS
    from collections import deque

    queue = deque([(start, [])])
    visited = {start}

    while queue:
        current, path = queue.popleft()

        if current == end:
            return path

        if len(path) >= max_distance:
            continue

        for adj in get_adjacent_positions(current, grid_size):
            if adj in visited or adj in blocked:
                continue
            visited.add(adj)
            queue.append((adj, path + [adj]))

    return None


def create_game_view(state_dict: dict) -> GameView:
    """Convert raw state dict to GameView."""
    # Parse my ships
    my_ships = []
    for s in state_dict["my_ships"]:
        abilities = {}
        ability_info = {}

        # Get ship config for ability details
        ship_type = ShipType(s["type"])
        ship_config = SHIP_CONFIGS[ship_type]

        for ab_name, ab_state in s.get("abilities", {}).items():
            try:
                ab_type = AbilityType(ab_name)
                abilities[ab_type] = ab_state["can_use"]

                # Find the ability config for full details
                ab_config = None
                for cfg in ship_config.abilities:
                    if cfg.ability_type == ab_type:
                        ab_config = cfg
                        break

                if ab_config:
                    ability_info[ab_type] = AbilityInfo(
                        ability_type=ab_type,
                        can_use=ab_state["can_use"],
                        cooldown_remaining=ab_state.get("cooldown", 0),
                        range=ab_config.range,
                        damage=ab_config.damage,
                        area_size=ab_config.area_size,
                        uses_per_turn=ab_config.uses_per_turn,
                        blocks_movement=ab_config.blocks_movement,
                        ap_cost=ab_config.ap_cost,
                    )
            except ValueError:
                pass

        my_ships.append(VisibleShip(
            id=s["id"],
            positions=[Position.from_tuple(p) for p in s["positions"]],
            is_own=True,
            ship_type=ship_type,
            hp=s["hp"],
            max_hp=s["max_hp"],
            speed=s["speed"],
            movement_remaining=s["movement_remaining"],
            action_points=s.get("action_points", 0),
            max_action_points=ship_config.max_action_points,
            has_acted=s.get("action_points", 0) == 0,  # Legacy: no AP = has acted
            abilities=abilities,
            ability_info=ability_info
        ))

    # Parse visible enemy ships
    visible_enemy = []
    for s in state_dict.get("visible_enemy_ships", []):
        visible_enemy.append(VisibleShip(
            id=s["id"],
            positions=[Position.from_tuple(p) for p in s["positions"]],
            is_own=False
        ))

    # Parse known cells
    known_cells = {}
    for pos_str, info in state_dict.get("known_cells", {}).items():
        # Parse "(x, y, z)" string
        pos_tuple = eval(pos_str)  # Safe since we control the input
        pos = Position.from_tuple(pos_tuple)
        status = CellStatus(info["status"])
        known_cells[pos] = status

    # Parse storm
    storm = state_dict.get("storm")
    storm_min = Position.from_tuple(storm["min"]) if storm else None
    storm_max = Position.from_tuple(storm["max"]) if storm else None
    storm_turns = storm["turns_until_shrink"] if storm else 0
    storm_damage = storm["damage"] if storm else 0

    return GameView(
        turn=state_dict["turn"],
        my_player_id=state_dict["my_player_id"],
        grid_size=tuple(state_dict["grid_size"]),
        my_ships=my_ships,
        visible_enemy_ships=visible_enemy,
        known_cells=known_cells,
        my_mines=[(m["id"], Position.from_tuple(m["pos"])) for m in state_dict.get("my_mines", [])],
        my_sensors=[(s["id"], Position.from_tuple(s["pos"])) for s in state_dict.get("my_sensors", [])],
        my_decoys=[(d["id"], Position.from_tuple(d["pos"])) for d in state_dict.get("my_decoys", [])],
        my_drones=[(d["id"], Position.from_tuple(d["pos"]), d["hp"]) for d in state_dict.get("my_drones", [])],
        storm_min=storm_min,
        storm_max=storm_max,
        storm_turns_until_shrink=storm_turns,
        storm_damage=storm_damage
    )
