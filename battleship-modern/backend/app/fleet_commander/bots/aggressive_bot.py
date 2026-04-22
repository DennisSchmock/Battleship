"""AggressiveBot - Offensive-focused bot for Fleet Commander.

Prioritizes attacking over everything else.
Uses the AP system to move AND fire in the same turn when possible.
"""
import random as stdlib_random
from typing import List, Tuple, Optional, Set

from ..bot_interface import (
    FleetBot, GameView, VisibleShip, random_fleet_placement,
    get_adjacent_positions
)
from ..models import (
    Position, Direction, ShipType, AbilityType, CellStatus,
    GameConfig, Action, MoveAction, FireAction, AbilityAction,
    TurnResult
)


class AggressiveBot(FleetBot):
    """
    An aggressive bot that prioritizes attacking.

    Strategy:
    1. If enemy in range -> FIRE (use best affordable ability)
    2. If not in range but can afford move+fire -> MOVE then FIRE
    3. If can only move -> MOVE toward enemy
    """

    def __init__(self):
        self.config: Optional[GameConfig] = None
        self.enemy_side_x: int = 0

    def get_name(self) -> str:
        return "AggressiveBot"

    def on_game_start(self, config: GameConfig) -> None:
        self.config = config
        self.enemy_side_x = config.grid_size[0] - 1

    def place_fleet(self, config: GameConfig, zone_x_min: int, zone_x_max: int,
                    rng: 'stdlib_random.Random | None' = None,
                    ) -> List[Tuple[ShipType, Position, Direction]]:
        if zone_x_min < config.grid_size[0] // 2:
            self.enemy_side_x = config.grid_size[0] - 1
        else:
            self.enemy_side_x = 0
        return random_fleet_placement(config, zone_x_min, zone_x_max, rng=rng)

    def get_actions(self, view: GameView, rng: 'stdlib_random.Random | None' = None,
                    ) -> List[Action]:
        actions = []

        # Collect all enemy positions
        enemy_positions: List[Position] = []
        for enemy in view.visible_enemy_ships:
            enemy_positions.extend(enemy.positions)

        # Sort ships by firepower priority
        firepower_order = [ShipType.CRUISER, ShipType.ARTILLERY, ShipType.DESTROYER,
                          ShipType.MINELAYER]

        ships_to_act = sorted(
            view.get_ships_that_can_act(),
            key=lambda s: firepower_order.index(s.ship_type) if s.ship_type in firepower_order else 99
        )

        for ship in ships_to_act:
            ship_actions = self._get_ship_actions(ship, view, enemy_positions)
            actions.extend(ship_actions)

        return actions

    def _get_ship_actions(self, ship: VisibleShip, view: GameView,
                          enemy_positions: List[Position]) -> List[Action]:
        """Decide all actions for a single ship (can be multiple with AP system)."""
        actions = []

        # Track remaining AP for planning (actual deduction happens in engine)
        remaining_ap = ship.action_points
        current_pos = ship.center

        # First, try to fire if enemies are in range
        fire_action, fire_cost = self._get_best_fire_action(ship, current_pos, enemy_positions, remaining_ap)

        if fire_action:
            actions.append(fire_action)
            remaining_ap -= fire_cost
        else:
            # No enemy in range - try to move toward them then fire
            move_steps, fire_ability, fire_cost = self._plan_move_and_fire(
                ship, current_pos, enemy_positions, remaining_ap, view
            )

            if move_steps > 0:
                # Create move action
                path = self._create_path_toward_enemies(ship, current_pos, enemy_positions, move_steps, view)
                if path:
                    actions.append(MoveAction(ship_id=ship.id, path=path))
                    remaining_ap -= len(path)
                    current_pos = path[-1]

                    # Now try to fire from new position
                    if fire_ability and remaining_ap >= fire_cost:
                        target = self._find_closest_target(current_pos, enemy_positions,
                                                          ship.ability_info[fire_ability].range)
                        if target:
                            actions.append(FireAction(ship_id=ship.id, target=target, ability=fire_ability))
                            remaining_ap -= fire_cost

            # If we still have AP and couldn't reach firing range, just advance
            if remaining_ap > 0 and not actions:
                advance = self._get_advance_move(ship, view, enemy_positions, remaining_ap)
                if advance:
                    actions.append(advance)

        return actions

    def _get_best_fire_action(self, ship: VisibleShip, from_pos: Position,
                               enemies: List[Position], max_ap: int
                               ) -> Tuple[Optional[Action], int]:
        """Get the best fire action the ship can afford from current position."""
        if not ship.ability_info:
            return None, 0

        # Priority order: area attacks, burst fire, regular fire
        priority = [
            AbilityType.AREA_BOMBARDMENT,
            AbilityType.BURST_FIRE,
            AbilityType.PIERCING_SHOT,
            AbilityType.FIRE,
        ]

        for ab_type in priority:
            if ab_type not in ship.ability_info:
                continue
            info = ship.ability_info[ab_type]
            if not info.can_use or info.ap_cost > max_ap:
                continue

            # Find target in range
            if ab_type == AbilityType.AREA_BOMBARDMENT:
                target = self._find_bombardment_target(from_pos, enemies, info.range)
            else:
                target = self._find_closest_target(from_pos, enemies, info.range)

            if target:
                return FireAction(ship_id=ship.id, target=target, ability=ab_type), info.ap_cost

        return None, 0

    def _plan_move_and_fire(self, ship: VisibleShip, from_pos: Position,
                            enemies: List[Position], max_ap: int, view: GameView
                            ) -> Tuple[int, Optional[AbilityType], int]:
        """Plan how many steps to move and which ability to use."""
        if not enemies or not ship.ability_info:
            return 0, None, 0

        # Find closest enemy
        closest_enemy = min(enemies, key=lambda e: from_pos.distance_to(e))
        dist_to_enemy = from_pos.distance_to(closest_enemy)

        # Try each fire ability and see if we can reach firing range
        for ab_type in [AbilityType.FIRE, AbilityType.BURST_FIRE, AbilityType.PIERCING_SHOT]:
            if ab_type not in ship.ability_info:
                continue
            info = ship.ability_info[ab_type]
            if not info.can_use:
                continue

            fire_range = info.range
            fire_cost = info.ap_cost

            # How many steps to get in range?
            steps_needed = max(0, dist_to_enemy - fire_range)

            # Can we afford move + fire?
            total_cost = steps_needed + fire_cost
            if total_cost <= max_ap and steps_needed <= (ship.movement_remaining or 0):
                return steps_needed, ab_type, fire_cost

        return 0, None, 0

    def _create_path_toward_enemies(self, ship: VisibleShip, from_pos: Position,
                                     enemies: List[Position], steps: int, view: GameView
                                     ) -> List[Position]:
        """Create a path of 'steps' moves toward the closest enemy."""
        if not enemies or steps <= 0:
            return []

        target = min(enemies, key=lambda e: from_pos.distance_to(e))
        path = []
        current = from_pos

        for _ in range(steps):
            best_dir = None
            best_dist = current.distance_to(target)

            for direction in Direction:
                new_pos = current.move(direction)
                if not view.is_valid_position(new_pos):
                    continue
                if view.is_in_storm(new_pos):
                    continue
                dist = new_pos.distance_to(target)
                if dist < best_dist:
                    best_dist = dist
                    best_dir = direction

            if best_dir:
                current = current.move(best_dir)
                path.append(current)
            else:
                break

        return path

    def _find_bombardment_target(self, ship_pos: Position, enemies: List[Position],
                                  bomb_range: int) -> Optional[Position]:
        """Find best target for area bombardment (cluster of enemies)."""
        best_target = None
        best_count = 0

        for enemy in enemies:
            if ship_pos.distance_to(enemy) > bomb_range:
                continue
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

    def _get_advance_move(self, ship: VisibleShip, view: GameView,
                          enemies: List[Position], max_steps: int) -> Optional[MoveAction]:
        """Move toward enemies using up to max_steps."""
        if enemies:
            target = min(enemies, key=lambda e: ship.center.distance_to(e))
        else:
            target = Position(self.enemy_side_x, view.grid_size[1] // 2, view.grid_size[2] // 2)

        # Determine how many steps to take (limited by movement and AP)
        steps = min(max_steps, ship.movement_remaining or 0)
        if steps <= 0:
            return None

        path = []
        current = ship.center

        for _ in range(steps):
            best_dir = None
            best_dist = current.distance_to(target)

            for direction in Direction:
                new_pos = current.move(direction)
                if not view.is_valid_position(new_pos):
                    continue
                if view.is_in_storm(new_pos):
                    continue
                dist = new_pos.distance_to(target)
                if dist < best_dist:
                    best_dist = dist
                    best_dir = direction

            if best_dir:
                current = current.move(best_dir)
                path.append(current)
            else:
                break

        if path:
            return MoveAction(ship_id=ship.id, path=path)
        return None

    def on_turn_result(self, result: TurnResult) -> None:
        pass
