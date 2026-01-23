"""AggressiveBot - Offensive-focused bot for Fleet Commander.

Prioritizes:
- Maximum firepower usage
- Area bombardment on suspected enemy positions
- Pushing forward into enemy territory
- Using burst fire when available
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


class AggressiveBot(FleetBot):
    """
    An aggressive bot that focuses on attacking:

    1. Always fire when enemies are visible
    2. Use area bombardment liberally
    3. Push ships forward toward enemy territory
    4. Prioritize offense over defense
    """

    def __init__(self):
        self.config: Optional[GameConfig] = None
        self.hit_positions: Set[Position] = set()
        self.enemy_side_x: int = 0  # Which side enemies started on

    def get_name(self) -> str:
        return "AggressiveBot"

    def on_game_start(self, config: GameConfig) -> None:
        self.config = config
        self.hit_positions = set()
        # Assume enemy is on opposite side
        self.enemy_side_x = config.grid_size[0] - 1

    def place_fleet(self, config: GameConfig, zone_x_min: int, zone_x_max: int
                    ) -> List[Tuple[ShipType, Position, Direction]]:
        # Determine enemy side based on our zone
        if zone_x_min < config.grid_size[0] // 2:
            self.enemy_side_x = config.grid_size[0] - 1
        else:
            self.enemy_side_x = 0
        return random_fleet_placement(config, zone_x_min, zone_x_max)

    def get_actions(self, view: GameView) -> List[Action]:
        actions = []
        action_points_used = 0

        # Track enemy positions from this view
        enemy_positions: List[Position] = []
        for enemy in view.visible_enemy_ships:
            enemy_positions.extend(enemy.positions)

        # Sort ships: Cruisers first (most firepower), then artillery, destroyers, etc.
        firepower_order = [ShipType.CRUISER, ShipType.ARTILLERY, ShipType.DESTROYER,
                          ShipType.MINELAYER]

        ships_sorted = sorted(
            view.get_alive_ships(),
            key=lambda s: firepower_order.index(s.ship_type) if s.ship_type in firepower_order else 99
        )

        for ship in ships_sorted:
            if action_points_used >= view.action_points:
                break

            cost = view.get_action_cost(ship)
            if action_points_used + cost > view.action_points:
                continue

            action = None

            # Try to attack first using ability_info
            if ship.ability_info:
                # Use area bombardment if available and enemies are clustered
                if (AbilityType.AREA_BOMBARDMENT in ship.ability_info and
                    ship.ability_info[AbilityType.AREA_BOMBARDMENT].can_use and
                    len(enemy_positions) >= 2):
                    bomb_range = ship.ability_info[AbilityType.AREA_BOMBARDMENT].range
                    best_target = self._find_bombardment_target(ship.center, enemy_positions, bomb_range)
                    if best_target:
                        action = FireAction(
                            ship_id=ship.id,
                            target=best_target,
                            ability=AbilityType.AREA_BOMBARDMENT
                        )

                # Try burst fire for destroyers
                if not action and AbilityType.BURST_FIRE in ship.ability_info:
                    if ship.ability_info[AbilityType.BURST_FIRE].can_use and enemy_positions:
                        burst_range = ship.ability_info[AbilityType.BURST_FIRE].range
                        target = self._find_closest_target(ship.center, enemy_positions, burst_range)
                        if target:
                            action = FireAction(
                                ship_id=ship.id,
                                target=target,
                                ability=AbilityType.BURST_FIRE
                            )

                # Regular fire
                if not action and AbilityType.FIRE in ship.ability_info:
                    if ship.ability_info[AbilityType.FIRE].can_use:
                        fire_range = ship.get_fire_range()
                        target = self._find_closest_target(ship.center, enemy_positions, fire_range)
                        if target:
                            action = FireAction(ship_id=ship.id, target=target)
                        elif self.hit_positions:
                            # Fire at last known hit positions
                            for hit_pos in list(self.hit_positions)[:3]:
                                if ship.center.distance_to(hit_pos) <= fire_range:
                                    action = FireAction(ship_id=ship.id, target=hit_pos)
                                    break
                        else:
                            # Speculative fire toward enemy side
                            target = self._get_speculative_target(ship.center, view, fire_range)
                            if target:
                                action = FireAction(ship_id=ship.id, target=target)

            # If no attack possible, move toward enemies
            if not action:
                action = self._get_advance_move(ship, view, enemy_positions)

            if action:
                actions.append(action)
                action_points_used += cost

        return actions

    def _find_bombardment_target(self, ship_pos: Position, enemies: List[Position],
                                  bomb_range: int) -> Optional[Position]:
        """Find best target for area bombardment."""
        best_target = None
        best_count = 0

        for enemy in enemies:
            if ship_pos.distance_to(enemy) > bomb_range:
                continue
            # Count enemies in 3x3x3 area
            count = sum(1 for e in enemies if enemy.distance_to(e) <= 1)
            if count > best_count:
                best_count = count
                best_target = enemy

        return best_target if best_count >= 2 else None

    def _find_closest_target(self, ship_pos: Position, enemies: List[Position],
                             range_limit: int) -> Optional[Position]:
        """Find closest enemy in range."""
        best_target = None
        best_dist = float('inf')

        for enemy in enemies:
            dist = ship_pos.distance_to(enemy)
            if dist <= range_limit and dist < best_dist:
                best_dist = dist
                best_target = enemy

        return best_target

    def _get_speculative_target(self, ship_pos: Position, view: GameView,
                                 fire_range: int) -> Optional[Position]:
        """Fire speculatively toward enemy side."""
        # Target cells toward enemy that are unknown
        for _ in range(20):
            target = Position(
                ship_pos.x + random.randint(-fire_range, fire_range),
                random.randint(0, view.grid_size[1] - 1),
                random.randint(0, view.grid_size[2] - 1)
            )

            if not view.is_valid_position(target):
                continue
            if ship_pos.distance_to(target) > fire_range:
                continue
            if view.get_cell_status(target) in [CellStatus.EMPTY, CellStatus.HIT]:
                continue

            # Prefer targets toward enemy side
            if abs(target.x - self.enemy_side_x) < abs(ship_pos.x - self.enemy_side_x):
                return target

        return None

    def _get_advance_move(self, ship: VisibleShip, view: GameView,
                          enemies: List[Position]) -> Optional[MoveAction]:
        """Move aggressively toward enemies or enemy side."""
        if not ship.can_move():
            return None

        # Determine target: closest enemy or enemy side
        if enemies:
            target = min(enemies, key=lambda e: ship.center.distance_to(e))
        else:
            # Move toward enemy side
            target = Position(
                self.enemy_side_x,
                view.grid_size[1] // 2,
                view.grid_size[2] // 2
            )

        best_dir = None
        best_dist = ship.center.distance_to(target)

        for direction in Direction:
            new_pos = ship.center.move(direction)
            if not view.is_valid_position(new_pos):
                continue
            if view.is_in_storm(new_pos):
                continue
            dist = new_pos.distance_to(target)
            if dist < best_dist:
                best_dist = dist
                best_dir = direction

        if best_dir:
            return MoveAction(ship_id=ship.id, path=[ship.center.move(best_dir)])

        return None

    def on_turn_result(self, result: TurnResult) -> None:
        """Track successful hits."""
        for action_result in result.actions_taken:
            if action_result.ships_hit and hasattr(action_result.action, 'target'):
                self.hit_positions.add(action_result.action.target)
