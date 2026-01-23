"""DefensiveBot - Defensive-focused bot for Fleet Commander.

Prioritizes:
- Keeping ships alive through shields and repairs
- Evasive movement
- Defensive positioning
- Counter-attacking only when safe
"""
import random
from typing import List, Tuple, Optional, Set

from ..bot_interface import (
    FleetBot, GameView, VisibleShip, random_fleet_placement,
    get_adjacent_positions
)
from ..models import (
    Position, Direction, ShipType, AbilityType, CellStatus,
    GameConfig, Action, MoveAction, FireAction, ScanAction, AbilityAction,
    TurnResult
)


class DefensiveBot(FleetBot):
    """
    A defensive bot that focuses on survival:

    1. Repair damaged ships
    2. Use shields when under fire
    3. Keep distance from enemies
    4. Counter-attack from safe distance
    5. Deploy mines for area denial
    """

    def __init__(self):
        self.config: Optional[GameConfig] = None
        self.ships_under_attack: Set[str] = set()  # Ship IDs that took damage recently
        self.safe_zone_center: Optional[Position] = None

    def get_name(self) -> str:
        return "DefensiveBot"

    def on_game_start(self, config: GameConfig) -> None:
        self.config = config
        self.ships_under_attack = set()
        self.safe_zone_center = Position(
            config.grid_size[0] // 4,  # Stay on our side
            config.grid_size[1] // 2,
            config.grid_size[2] // 2
        )

    def place_fleet(self, config: GameConfig, zone_x_min: int, zone_x_max: int
                    ) -> List[Tuple[ShipType, Position, Direction]]:
        # Set safe zone based on our side
        if zone_x_min < config.grid_size[0] // 2:
            self.safe_zone_center = Position(
                zone_x_max + 2,
                config.grid_size[1] // 2,
                config.grid_size[2] // 2
            )
        else:
            self.safe_zone_center = Position(
                zone_x_min - 2,
                config.grid_size[1] // 2,
                config.grid_size[2] // 2
            )
        return random_fleet_placement(config, zone_x_min, zone_x_max)

    def get_actions(self, view: GameView) -> List[Action]:
        actions = []
        action_points_used = 0

        # Identify threats
        enemy_positions: List[Position] = []
        for enemy in view.visible_enemy_ships:
            enemy_positions.extend(enemy.positions)

        # Calculate danger zones (positions near enemies)
        danger_zone = self._calculate_danger_zone(enemy_positions)

        # Process ships by priority: damaged first, then support, then others
        damaged_ships = view.get_damaged_ships()
        support_ships = view.get_ships_by_type(ShipType.SUPPORT)
        other_ships = [s for s in view.get_alive_ships()
                       if s not in damaged_ships and s not in support_ships]

        # Phase 1: Support ships repair damaged allies
        for support in support_ships:
            if action_points_used >= view.action_points:
                break

            cost = view.get_action_cost(support)
            if action_points_used + cost > view.action_points:
                continue

            # Find damaged friendly ship in range
            if support.ability_info and AbilityType.REPAIR in support.ability_info:
                if support.ability_info[AbilityType.REPAIR].can_use:
                    repair_range = support.ability_info[AbilityType.REPAIR].range
                    for damaged in damaged_ships:
                        if support.center.distance_to(damaged.center) <= repair_range:
                            actions.append(AbilityAction(
                                ship_id=support.id,
                                ability=AbilityType.REPAIR,
                                target_ship_id=damaged.id
                            ))
                            action_points_used += cost
                            break
                    else:
                        # No one to repair, move toward damaged ships
                        if damaged_ships:
                            move = self._move_toward(support, damaged_ships[0].center, view, danger_zone)
                            if move:
                                actions.append(move)
                                action_points_used += cost

        # Phase 2: Damaged ships retreat and shield
        for ship in damaged_ships:
            if action_points_used >= view.action_points:
                break

            cost = view.get_action_cost(ship)
            if action_points_used + cost > view.action_points:
                continue

            # Use shield if available and near enemies
            if ship.ability_info and AbilityType.SHIELD in ship.ability_info:
                if ship.ability_info[AbilityType.SHIELD].can_use:
                    in_danger = any(ship.center.distance_to(e) <= 5 for e in enemy_positions)
                    if in_danger:
                        actions.append(AbilityAction(
                            ship_id=ship.id,
                            ability=AbilityType.SHIELD
                        ))
                        action_points_used += cost
                        continue

            # Retreat from danger
            move = self._get_retreat_move(ship, view, danger_zone)
            if move:
                actions.append(move)
                action_points_used += cost

        # Phase 3: Healthy ships - counter-attack from safe distance
        for ship in other_ships:
            if action_points_used >= view.action_points:
                break

            cost = view.get_action_cost(ship)
            if action_points_used + cost > view.action_points:
                continue

            action = None

            # Minelayers deploy mines in strategic positions
            if ship.ship_type == ShipType.MINELAYER:
                if ship.ability_info and AbilityType.DEPLOY_MINE in ship.ability_info:
                    if ship.ability_info[AbilityType.DEPLOY_MINE].can_use:
                        mine_pos = self._find_mine_position(ship.center, view, enemy_positions)
                        if mine_pos:
                            action = AbilityAction(
                                ship_id=ship.id,
                                ability=AbilityType.DEPLOY_MINE,
                                target=mine_pos
                            )

            # Scouts scan for threats
            if not action and ship.ship_type == ShipType.SCOUT:
                if ship.can_scan():
                    scan_pos = self._find_scan_position(ship, view)
                    if scan_pos:
                        action = ScanAction(ship_id=ship.id, center=scan_pos)

            # Long-range ships counter-attack
            if not action and ship.can_fire():
                fire_range = ship.get_fire_range()
                target = self._find_safe_target(ship.center, enemy_positions, fire_range, danger_zone)
                if target:
                    action = FireAction(ship_id=ship.id, target=target)

            # If no good attack, maintain safe distance
            if not action:
                action = self._get_defensive_move(ship, view, enemy_positions, danger_zone)

            if action:
                actions.append(action)
                action_points_used += cost

        return actions

    def _calculate_danger_zone(self, enemies: List[Position]) -> Set[Position]:
        """Calculate positions that are in danger from enemies."""
        danger = set()
        for enemy in enemies:
            # Mark 6 cells around each enemy as dangerous
            for dx in range(-6, 7):
                for dy in range(-6, 7):
                    for dz in range(-6, 7):
                        if abs(dx) + abs(dy) + abs(dz) <= 6:
                            danger.add(Position(enemy.x + dx, enemy.y + dy, enemy.z + dz))
        return danger

    def _find_safe_target(self, ship_pos: Position, enemies: List[Position],
                          fire_range: int, danger: Set[Position]) -> Optional[Position]:
        """Find enemy to attack while staying safe."""
        # Only attack if we're not in immediate danger
        if ship_pos in danger:
            return None

        for enemy in enemies:
            if ship_pos.distance_to(enemy) <= fire_range:
                return enemy
        return None

    def _move_toward(self, ship: VisibleShip, target: Position, view: GameView,
                     danger: Set[Position]) -> Optional[MoveAction]:
        """Move toward a target, avoiding danger."""
        if not ship.can_move():
            return None

        best_dir = None
        best_dist = ship.center.distance_to(target)

        for direction in Direction:
            new_pos = ship.center.move(direction)
            if not view.is_valid_position(new_pos):
                continue
            if view.is_in_storm(new_pos):
                continue
            # Avoid danger zones
            if new_pos in danger:
                continue
            dist = new_pos.distance_to(target)
            if dist < best_dist:
                best_dist = dist
                best_dir = direction

        if best_dir:
            return MoveAction(ship_id=ship.id, path=[ship.center.move(best_dir)])
        return None

    def _get_retreat_move(self, ship: VisibleShip, view: GameView,
                          danger: Set[Position]) -> Optional[MoveAction]:
        """Move away from danger toward safe zone."""
        if not ship.can_move():
            return None

        if self.safe_zone_center:
            return self._move_toward(ship, self.safe_zone_center, view, set())  # Ignore danger when retreating

        return None

    def _get_defensive_move(self, ship: VisibleShip, view: GameView,
                            enemies: List[Position], danger: Set[Position]) -> Optional[MoveAction]:
        """Move to maintain safe distance from enemies."""
        if not ship.can_move() or not enemies:
            return None

        # Move away if too close
        closest_enemy = min(enemies, key=lambda e: ship.center.distance_to(e))
        if ship.center.distance_to(closest_enemy) < 5:
            # Find direction away from enemy
            best_dir = None
            best_dist = ship.center.distance_to(closest_enemy)

            for direction in Direction:
                new_pos = ship.center.move(direction)
                if not view.is_valid_position(new_pos):
                    continue
                if view.is_in_storm(new_pos):
                    continue
                dist = new_pos.distance_to(closest_enemy)
                if dist > best_dist:
                    best_dist = dist
                    best_dir = direction

            if best_dir:
                return MoveAction(ship_id=ship.id, path=[ship.center.move(best_dir)])

        return None

    def _find_mine_position(self, ship_pos: Position, view: GameView,
                            enemies: List[Position]) -> Optional[Position]:
        """Find good position for mine deployment."""
        if not enemies:
            return None

        # Place mines between us and enemies
        for adj in get_adjacent_positions(ship_pos, view.grid_size):
            if view.is_in_storm(adj):
                continue
            if any(m[1] == adj for m in view.my_mines):
                continue
            # Check if it's in enemy's likely path
            for enemy in enemies:
                if adj.distance_to(enemy) < ship_pos.distance_to(enemy):
                    return adj

        return None

    def _find_scan_position(self, ship: VisibleShip, view: GameView) -> Optional[Position]:
        """Find position to scan for enemies."""
        scan_range = ship.get_scan_range()
        if scan_range == 0:
            return None

        best_pos = None
        best_unknown = 0

        for _ in range(20):
            target = Position(
                ship.center.x + random.randint(-scan_range, scan_range),
                random.randint(0, view.grid_size[1] - 1),
                random.randint(0, view.grid_size[2] - 1)
            )

            if not view.is_valid_position(target):
                continue
            if ship.center.distance_to(target) > scan_range:
                continue

            unknown = sum(1 for dx in range(-2, 3) for dy in range(-2, 3) for dz in range(-2, 3)
                         if view.get_cell_status(Position(target.x + dx, target.y + dy, target.z + dz)) == CellStatus.UNKNOWN)

            if unknown > best_unknown:
                best_unknown = unknown
                best_pos = target

        return best_pos if best_unknown > 10 else None

    def on_turn_result(self, result: TurnResult) -> None:
        """Track which ships are under attack."""
        for action_result in result.actions_taken:
            if action_result.ships_hit:
                self.ships_under_attack.update(action_result.ships_hit)
