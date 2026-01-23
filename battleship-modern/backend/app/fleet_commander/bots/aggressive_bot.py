"""AggressiveBot - Offensive-focused bot for Fleet Commander.

Prioritizes attacking over everything else.
Each ship gets 1 action per turn.
"""
import random
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
    1. If enemy in range -> FIRE
    2. If not in range -> MOVE toward enemy
    3. Use special abilities when available
    """

    def __init__(self):
        self.config: Optional[GameConfig] = None
        self.enemy_side_x: int = 0

    def get_name(self) -> str:
        return "AggressiveBot"

    def on_game_start(self, config: GameConfig) -> None:
        self.config = config
        self.enemy_side_x = config.grid_size[0] - 1

    def place_fleet(self, config: GameConfig, zone_x_min: int, zone_x_max: int
                    ) -> List[Tuple[ShipType, Position, Direction]]:
        if zone_x_min < config.grid_size[0] // 2:
            self.enemy_side_x = config.grid_size[0] - 1
        else:
            self.enemy_side_x = 0
        return random_fleet_placement(config, zone_x_min, zone_x_max)

    def get_actions(self, view: GameView) -> List[Action]:
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
            action = self._get_ship_action(ship, view, enemy_positions)
            if action:
                actions.append(action)

        return actions

    def _get_ship_action(self, ship: VisibleShip, view: GameView,
                         enemy_positions: List[Position]) -> Optional[Action]:
        """Decide action for a single ship."""

        # Priority 1: Use area bombardment if available and enemies are clustered
        if ship.ability_info and AbilityType.AREA_BOMBARDMENT in ship.ability_info:
            if ship.ability_info[AbilityType.AREA_BOMBARDMENT].can_use:
                bomb_range = ship.ability_info[AbilityType.AREA_BOMBARDMENT].range
                target = self._find_bombardment_target(ship.center, enemy_positions, bomb_range)
                if target:
                    return FireAction(ship_id=ship.id, target=target,
                                     ability=AbilityType.AREA_BOMBARDMENT)

        # Priority 2: Use burst fire on nearby enemies
        if ship.ability_info and AbilityType.BURST_FIRE in ship.ability_info:
            if ship.ability_info[AbilityType.BURST_FIRE].can_use:
                burst_range = ship.ability_info[AbilityType.BURST_FIRE].range
                target = self._find_closest_target(ship.center, enemy_positions, burst_range)
                if target:
                    return FireAction(ship_id=ship.id, target=target,
                                     ability=AbilityType.BURST_FIRE)

        # Priority 3: Regular fire at enemies in range
        if ship.can_fire() and enemy_positions:
            fire_range = ship.get_fire_range()
            target = self._find_closest_target(ship.center, enemy_positions, fire_range)
            if target:
                return FireAction(ship_id=ship.id, target=target)

        # Priority 4: Move toward enemies
        if ship.can_move():
            return self._get_advance_move(ship, view, enemy_positions)

        return None

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
                          enemies: List[Position]) -> Optional[MoveAction]:
        """Move toward enemies or enemy side."""
        if enemies:
            target = min(enemies, key=lambda e: ship.center.distance_to(e))
        else:
            target = Position(self.enemy_side_x, view.grid_size[1] // 2, view.grid_size[2] // 2)

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
        pass
