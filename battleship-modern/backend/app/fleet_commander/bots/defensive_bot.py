"""DefensiveBot - Defensive-focused bot for Fleet Commander.

Prioritizes survival and counter-attacks from safe distance.
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


class DefensiveBot(FleetBot):
    """
    A defensive bot that prioritizes survival:

    Strategy:
    1. Support ships repair damaged allies
    2. Damaged ships retreat
    3. Counter-attack only from safe distance
    4. Deploy mines defensively
    """

    def __init__(self):
        self.config: Optional[GameConfig] = None
        self.safe_zone_center: Optional[Position] = None

    def get_name(self) -> str:
        return "DefensiveBot"

    def on_game_start(self, config: GameConfig) -> None:
        self.config = config

    def place_fleet(self, config: GameConfig, zone_x_min: int, zone_x_max: int
                    ) -> List[Tuple[ShipType, Position, Direction]]:
        # Set safe zone on our side
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

        # Collect enemy positions
        enemy_positions: List[Position] = []
        for enemy in view.visible_enemy_ships:
            enemy_positions.extend(enemy.positions)

        # Calculate danger zone
        danger_zone = self._calculate_danger_zone(enemy_positions)

        # Process ships by priority
        for ship in view.get_ships_that_can_act():
            action = self._get_ship_action(ship, view, enemy_positions, danger_zone)
            if action:
                actions.append(action)

        return actions

    def _get_ship_action(self, ship: VisibleShip, view: GameView,
                         enemies: List[Position], danger: Set[Position]) -> Optional[Action]:
        """Get action based on ship role and situation."""

        # Support ships: repair damaged allies
        if ship.ship_type == ShipType.SUPPORT:
            return self._support_action(ship, view)

        # Damaged ships: retreat or shield
        if ship.hp and ship.max_hp and ship.hp < ship.max_hp * 0.5:
            return self._retreat_action(ship, view, enemies)

        # Minelayers: deploy mines defensively
        if ship.ship_type == ShipType.MINELAYER:
            return self._minelayer_action(ship, view, enemies)

        # Combat ships: counter-attack from safe distance
        return self._counter_attack(ship, view, enemies, danger)

    def _support_action(self, ship: VisibleShip, view: GameView) -> Optional[Action]:
        """Repair damaged allies."""
        if ship.ability_info and AbilityType.REPAIR in ship.ability_info:
            if ship.ability_info[AbilityType.REPAIR].can_use:
                repair_range = ship.ability_info[AbilityType.REPAIR].range
                damaged = view.get_damaged_ships()

                # Find ally in range
                for ally in damaged:
                    if ship.center.distance_to(ally.center) <= repair_range:
                        return AbilityAction(
                            ship_id=ship.id,
                            ability=AbilityType.REPAIR,
                            target_ship_id=ally.id
                        )

                # Move toward most damaged ally
                if damaged:
                    most_damaged = min(damaged, key=lambda s: s.hp / s.max_hp if s.max_hp else 1)
                    return self._move_toward(ship, most_damaged.center, view)

        return self._move_toward_safe_zone(ship, view)

    def _retreat_action(self, ship: VisibleShip, view: GameView,
                        enemies: List[Position]) -> Optional[Action]:
        """Retreat to safety."""
        # Use shield if available and enemies nearby
        if ship.ability_info and AbilityType.SHIELD in ship.ability_info:
            if ship.ability_info[AbilityType.SHIELD].can_use:
                if any(ship.center.distance_to(e) <= 6 for e in enemies):
                    return AbilityAction(ship_id=ship.id, ability=AbilityType.SHIELD)

        # Move toward safe zone
        return self._move_toward_safe_zone(ship, view)

    def _minelayer_action(self, ship: VisibleShip, view: GameView,
                          enemies: List[Position]) -> Optional[Action]:
        """Deploy mines between us and enemies."""
        if ship.ability_info and AbilityType.DEPLOY_MINE in ship.ability_info:
            if ship.ability_info[AbilityType.DEPLOY_MINE].can_use:
                mine_pos = self._find_defensive_mine_pos(ship, view, enemies)
                if mine_pos:
                    return AbilityAction(
                        ship_id=ship.id,
                        ability=AbilityType.DEPLOY_MINE,
                        target=mine_pos
                    )

        # Fall back to counter-attack
        return self._counter_attack(ship, view, enemies, set())

    def _counter_attack(self, ship: VisibleShip, view: GameView,
                        enemies: List[Position], danger: Set[Position]) -> Optional[Action]:
        """Attack only if safe to do so."""
        # Only attack if not in danger zone
        if ship.center in danger:
            return self._move_toward_safe_zone(ship, view)

        # Fire at enemies in range
        if ship.can_fire() and enemies:
            fire_range = ship.get_fire_range()
            for enemy_pos in enemies:
                if ship.center.distance_to(enemy_pos) <= fire_range:
                    return FireAction(ship_id=ship.id, target=enemy_pos)

        # Move to maintain safe distance
        if enemies:
            closest = min(enemies, key=lambda e: ship.center.distance_to(e))
            if ship.center.distance_to(closest) < 8:
                # Too close - retreat
                return self._move_away_from(ship, closest, view)

        return None

    def _calculate_danger_zone(self, enemies: List[Position]) -> Set[Position]:
        """Mark positions near enemies as dangerous."""
        danger = set()
        for enemy in enemies:
            for dx in range(-6, 7):
                for dy in range(-6, 7):
                    for dz in range(-6, 7):
                        if abs(dx) + abs(dy) + abs(dz) <= 6:
                            danger.add(Position(enemy.x + dx, enemy.y + dy, enemy.z + dz))
        return danger

    def _move_toward(self, ship: VisibleShip, target: Position, view: GameView) -> Optional[MoveAction]:
        """Move toward a target."""
        if not ship.can_move():
            return None

        best_dir = None
        best_dist = ship.center.distance_to(target)

        for direction in Direction:
            new_pos = ship.center.move(direction)
            if not view.is_valid_position(new_pos) or view.is_in_storm(new_pos):
                continue
            dist = new_pos.distance_to(target)
            if dist < best_dist:
                best_dist = dist
                best_dir = direction

        if best_dir:
            return MoveAction(ship_id=ship.id, path=[ship.center.move(best_dir)])
        return None

    def _move_away_from(self, ship: VisibleShip, target: Position, view: GameView) -> Optional[MoveAction]:
        """Move away from a target."""
        if not ship.can_move():
            return None

        best_dir = None
        best_dist = ship.center.distance_to(target)

        for direction in Direction:
            new_pos = ship.center.move(direction)
            if not view.is_valid_position(new_pos) or view.is_in_storm(new_pos):
                continue
            dist = new_pos.distance_to(target)
            if dist > best_dist:
                best_dist = dist
                best_dir = direction

        if best_dir:
            return MoveAction(ship_id=ship.id, path=[ship.center.move(best_dir)])
        return None

    def _move_toward_safe_zone(self, ship: VisibleShip, view: GameView) -> Optional[MoveAction]:
        """Move toward safe zone."""
        if self.safe_zone_center:
            return self._move_toward(ship, self.safe_zone_center, view)
        return None

    def _find_defensive_mine_pos(self, ship: VisibleShip, view: GameView,
                                  enemies: List[Position]) -> Optional[Position]:
        """Find position for defensive mine (between us and enemies)."""
        for adj in get_adjacent_positions(ship.center, view.grid_size):
            if view.is_in_storm(adj):
                continue
            if any(m[1] == adj for m in view.my_mines):
                continue
            # Place between us and enemies (toward enemy)
            for enemy in enemies:
                if adj.distance_to(enemy) < ship.center.distance_to(enemy):
                    return adj
        return None

    def on_turn_result(self, result: TurnResult) -> None:
        pass
