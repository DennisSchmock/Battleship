"""TacticalBot - A strategic bot for Fleet Commander.

Uses all ship abilities tactically:
- Scouts scan ahead and harass
- Destroyers hunt detected enemies
- Cruisers provide heavy firepower
- Minelayers control territory
- All ships retreat from the storm
"""
import random
from typing import List, Tuple, Optional, Set

from ..bot_interface import (
    FleetBot, GameView, VisibleShip, random_fleet_placement,
    get_adjacent_positions, find_path
)
from ..models import (
    Position, Direction, ShipType, AbilityType, CellStatus,
    GameConfig, Action, MoveAction, FireAction, ScanAction, AbilityAction,
    TurnResult
)


class TacticalBot(FleetBot):
    """
    A bot that uses tactical principles:

    1. RECON: Use scouts to find enemies
    2. ENGAGE: Move destroyers/cruisers to attack
    3. CONTROL: Place mines in chokepoints
    4. SURVIVE: Retreat from storm, repair damaged ships
    """

    def __init__(self):
        self.config: Optional[GameConfig] = None
        self.enemy_last_seen: dict = {}  # ship_id -> (position, turn)
        self.scanned_areas: Set[Position] = set()

    def get_name(self) -> str:
        return "TacticalBot"

    def on_game_start(self, config: GameConfig) -> None:
        self.config = config
        self.enemy_last_seen = {}
        self.scanned_areas = set()

    def place_fleet(self, config: GameConfig, zone_x_min: int, zone_x_max: int
                    ) -> List[Tuple[ShipType, Position, Direction]]:
        """Place fleet using helper function."""
        return random_fleet_placement(config, zone_x_min, zone_x_max)

    def get_actions(self, view: GameView) -> List[Action]:
        """Decide actions for this turn."""
        actions = []
        action_points_used = 0

        # Update enemy tracking
        for enemy in view.visible_enemy_ships:
            self.enemy_last_seen[enemy.id] = (enemy.positions[0], view.turn)

        # Sort ships by priority (scouts first for recon)
        ships_by_type = self._sort_ships_by_role(view.get_alive_ships())

        # === Phase 1: SURVIVAL - Move ships out of storm ===
        for ship in view.get_alive_ships():
            in_storm = any(view.is_in_storm(p) for p in ship.positions)
            if in_storm:
                move = self._get_storm_escape_move(ship, view)
                if move:
                    cost = view.get_action_cost(ship)
                    if action_points_used + cost <= view.action_points:
                        actions.append(move)
                        action_points_used += cost

        # === Phase 2: RECON - Scouts scan unknown areas ===
        for ship in ships_by_type.get(ShipType.SCOUT, []):
            if action_points_used >= view.action_points:
                break

            # Try to scan
            scan_action = self._get_scan_action(ship, view)
            if scan_action:
                cost = view.get_action_cost(ship)
                if action_points_used + cost <= view.action_points:
                    actions.append(scan_action)
                    action_points_used += cost
                    continue

            # Otherwise move toward center/unexplored
            move = self._get_explore_move(ship, view)
            if move:
                cost = view.get_action_cost(ship)
                if action_points_used + cost <= view.action_points:
                    actions.append(move)
                    action_points_used += cost

        # === Phase 3: ENGAGE - Combat ships attack visible enemies ===
        combat_types = [ShipType.DESTROYER, ShipType.CRUISER, ShipType.ARTILLERY]
        for ship_type in combat_types:
            for ship in ships_by_type.get(ship_type, []):
                if action_points_used >= view.action_points:
                    break

                # Try to attack
                attack = self._get_attack_action(ship, view)
                if attack:
                    cost = view.get_action_cost(ship)
                    if action_points_used + cost <= view.action_points:
                        actions.append(attack)
                        action_points_used += cost
                        continue

                # Move toward last known enemy position
                move = self._get_pursuit_move(ship, view)
                if move:
                    cost = view.get_action_cost(ship)
                    if action_points_used + cost <= view.action_points:
                        actions.append(move)
                        action_points_used += cost

        # === Phase 4: CONTROL - Minelayers place mines ===
        for ship in ships_by_type.get(ShipType.MINELAYER, []):
            if action_points_used >= view.action_points:
                break

            mine_action = self._get_mine_action(ship, view)
            if mine_action:
                cost = view.get_action_cost(ship)
                if action_points_used + cost <= view.action_points:
                    actions.append(mine_action)
                    action_points_used += cost

        return actions

    def _sort_ships_by_role(self, ships: List[VisibleShip]) -> dict:
        """Group ships by type."""
        result = {}
        for ship in ships:
            if ship.ship_type is None:
                continue
            if ship.ship_type not in result:
                result[ship.ship_type] = []
            result[ship.ship_type].append(ship)
        return result

    def _get_storm_escape_move(self, ship: VisibleShip, view: GameView) -> Optional[MoveAction]:
        """Get move to escape the storm."""
        if not view.storm_min or not view.storm_max or not ship.can_move():
            return None

        # Find direction toward safe zone center
        safe_center = Position(
            (view.storm_min.x + view.storm_max.x) // 2,
            (view.storm_min.y + view.storm_max.y) // 2,
            (view.storm_min.z + view.storm_max.z) // 2
        )

        best_dir = None
        best_dist = ship.center.distance_to(safe_center)

        for direction in Direction:
            new_pos = ship.center.move(direction)
            if not view.is_valid_position(new_pos):
                continue
            dist = new_pos.distance_to(safe_center)
            if dist < best_dist:
                best_dist = dist
                best_dir = direction

        if best_dir:
            target = ship.center.move(best_dir)
            return MoveAction(ship_id=ship.id, path=[target])

        return None

    def _get_scan_action(self, ship: VisibleShip, view: GameView) -> Optional[ScanAction]:
        """Get a scan action for a scout."""
        if not ship.can_scan():
            return None

        scan_range = ship.get_scan_range()
        if scan_range == 0:
            return None

        # Get scan area size from ability info
        scan_radius = 2  # Default
        if ship.ability_info:
            for ab_type in [AbilityType.SCAN, AbilityType.LONG_RANGE_SCAN]:
                if ab_type in ship.ability_info:
                    scan_radius = ship.ability_info[ab_type].area_size
                    break

        # Find unexplored area to scan
        best_target = None
        best_unknown_count = 0

        # Check several candidate positions
        for _ in range(20):
            target = Position(
                random.randint(0, view.grid_size[0] - 1),
                random.randint(0, view.grid_size[1] - 1),
                random.randint(0, view.grid_size[2] - 1)
            )

            if ship.center.distance_to(target) > scan_range:
                continue

            # Count unknown cells in scan area
            unknown_count = 0
            for dx in range(-scan_radius, scan_radius + 1):
                for dy in range(-scan_radius, scan_radius + 1):
                    for dz in range(-scan_radius, scan_radius + 1):
                        check = Position(target.x + dx, target.y + dy, target.z + dz)
                        if view.get_cell_status(check) == CellStatus.UNKNOWN:
                            unknown_count += 1

            if unknown_count > best_unknown_count:
                best_unknown_count = unknown_count
                best_target = target

        if best_target and best_unknown_count > 5:
            return ScanAction(ship_id=ship.id, center=best_target)

        return None

    def _get_explore_move(self, ship: VisibleShip, view: GameView) -> Optional[MoveAction]:
        """Get move toward unexplored territory."""
        if not ship.can_move():
            return None

        # Move toward center of map if far from it
        map_center = Position(
            view.grid_size[0] // 2,
            view.grid_size[1] // 2,
            view.grid_size[2] // 2
        )

        best_dir = None
        best_dist = ship.center.distance_to(map_center)

        for direction in Direction:
            new_pos = ship.center.move(direction)
            if not view.is_valid_position(new_pos):
                continue
            if view.is_in_storm(new_pos):
                continue
            dist = new_pos.distance_to(map_center)
            if dist < best_dist:
                best_dist = dist
                best_dir = direction

        if best_dir:
            return MoveAction(ship_id=ship.id, path=[ship.center.move(best_dir)])

        return None

    def _get_attack_action(self, ship: VisibleShip, view: GameView) -> Optional[FireAction]:
        """Get attack action against visible enemy."""
        if not ship.can_fire():
            return None

        fire_range = ship.get_fire_range()
        if fire_range == 0:
            return None

        # Find target in range
        for enemy in view.visible_enemy_ships:
            for enemy_pos in enemy.positions:
                if ship.center.distance_to(enemy_pos) <= fire_range:
                    return FireAction(ship_id=ship.id, target=enemy_pos)

        # Also check known SHIP cells
        for pos, status in view.known_cells.items():
            if status == CellStatus.SHIP:
                if ship.center.distance_to(pos) <= fire_range:
                    return FireAction(ship_id=ship.id, target=pos)

        return None

    def _get_pursuit_move(self, ship: VisibleShip, view: GameView) -> Optional[MoveAction]:
        """Move toward last known enemy position."""
        if not ship.can_move():
            return None

        if not self.enemy_last_seen:
            return self._get_explore_move(ship, view)

        # Find closest last-seen enemy
        best_target = None
        best_dist = float('inf')

        for enemy_id, (pos, turn) in self.enemy_last_seen.items():
            # Ignore old info
            if view.turn - turn > 10:
                continue
            dist = ship.center.distance_to(pos)
            if dist < best_dist:
                best_dist = dist
                best_target = pos

        if best_target:
            # Move toward target
            best_dir = None
            for direction in Direction:
                new_pos = ship.center.move(direction)
                if not view.is_valid_position(new_pos):
                    continue
                if view.is_in_storm(new_pos):
                    continue
                if new_pos.distance_to(best_target) < best_dist:
                    best_dist = new_pos.distance_to(best_target)
                    best_dir = direction

            if best_dir:
                return MoveAction(ship_id=ship.id, path=[ship.center.move(best_dir)])

        return self._get_explore_move(ship, view)

    def _get_mine_action(self, ship: VisibleShip, view: GameView) -> Optional[AbilityAction]:
        """Place a mine in a strategic location."""
        if not ship.ability_info or AbilityType.DEPLOY_MINE not in ship.ability_info:
            return None
        if not ship.ability_info[AbilityType.DEPLOY_MINE].can_use:
            return None

        # Place mine toward center of map (likely path)
        map_center = Position(
            view.grid_size[0] // 2,
            view.grid_size[1] // 2,
            view.grid_size[2] // 2
        )

        # Find adjacent cell closest to center
        best_pos = None
        best_dist = float('inf')

        for adj in get_adjacent_positions(ship.center, view.grid_size):
            if view.is_in_storm(adj):
                continue
            # Don't place on own mines
            if any(m[1] == adj for m in view.my_mines):
                continue
            dist = adj.distance_to(map_center)
            if dist < best_dist:
                best_dist = dist
                best_pos = adj

        if best_pos:
            return AbilityAction(
                ship_id=ship.id,
                ability=AbilityType.DEPLOY_MINE,
                target=best_pos
            )

        return None

    def on_turn_result(self, result: TurnResult) -> None:
        """Update tracking based on turn results."""
        # Track damage dealt to learn enemy positions
        for action_result in result.actions_taken:
            if action_result.ships_hit:
                # We hit something - remember this position
                if hasattr(action_result.action, 'target'):
                    for ship_id in action_result.ships_hit:
                        self.enemy_last_seen[ship_id] = (
                            action_result.action.target,
                            result.turn
                        )
