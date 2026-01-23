"""TacticalBot - A strategic bot for Fleet Commander.

Uses different strategies based on ship type.
Each ship gets 1 action per turn.
"""
import random
from typing import List, Tuple, Optional, Set, Dict

from ..bot_interface import (
    FleetBot, GameView, VisibleShip, random_fleet_placement,
    get_adjacent_positions
)
from ..models import (
    Position, Direction, ShipType, AbilityType, CellStatus,
    GameConfig, Action, MoveAction, FireAction, AbilityAction,
    TurnResult
)


class TacticalBot(FleetBot):
    """
    A bot that uses different tactics for each ship type:

    - Destroyers: Hunt with burst fire
    - Cruisers: Area bombardment when enemies cluster
    - Artillery: Long-range precision strikes
    - Support: Repair damaged allies
    - Minelayers: Deploy mines in enemy paths
    - Carrier: Launch drones, stay back
    """

    def __init__(self):
        self.config: Optional[GameConfig] = None
        self.enemy_last_seen: Dict[str, Tuple[Position, int]] = {}

    def get_name(self) -> str:
        return "TacticalBot"

    def on_game_start(self, config: GameConfig) -> None:
        self.config = config
        self.enemy_last_seen = {}

    def place_fleet(self, config: GameConfig, zone_x_min: int, zone_x_max: int
                    ) -> List[Tuple[ShipType, Position, Direction]]:
        return random_fleet_placement(config, zone_x_min, zone_x_max)

    def get_actions(self, view: GameView) -> List[Action]:
        actions = []

        # Track enemy positions
        enemy_positions: List[Position] = []
        for enemy in view.visible_enemy_ships:
            enemy_positions.extend(enemy.positions)
            self.enemy_last_seen[enemy.id] = (enemy.positions[0], view.turn)

        # Process each ship that can act
        for ship in view.get_ships_that_can_act():
            action = self._get_ship_action(ship, view, enemy_positions)
            if action:
                actions.append(action)

        return actions

    def _get_ship_action(self, ship: VisibleShip, view: GameView,
                         enemy_positions: List[Position]) -> Optional[Action]:
        """Get action based on ship type."""

        # First: Escape storm if in danger
        if any(view.is_in_storm(p) for p in ship.positions):
            return self._get_storm_escape_move(ship, view)

        # Type-specific tactics
        if ship.ship_type == ShipType.SUPPORT:
            return self._support_action(ship, view)
        elif ship.ship_type == ShipType.MINELAYER:
            return self._minelayer_action(ship, view, enemy_positions)
        elif ship.ship_type == ShipType.ARTILLERY:
            return self._artillery_action(ship, view, enemy_positions)
        elif ship.ship_type == ShipType.CARRIER:
            return self._carrier_action(ship, view, enemy_positions)
        else:
            # Combat ships (Destroyer, Cruiser)
            return self._combat_action(ship, view, enemy_positions)

    def _support_action(self, ship: VisibleShip, view: GameView) -> Optional[Action]:
        """Support ships repair damaged allies."""
        if ship.ability_info and AbilityType.REPAIR in ship.ability_info:
            if ship.ability_info[AbilityType.REPAIR].can_use:
                repair_range = ship.ability_info[AbilityType.REPAIR].range
                for ally in view.get_damaged_ships():
                    if ship.center.distance_to(ally.center) <= repair_range:
                        return AbilityAction(
                            ship_id=ship.id,
                            ability=AbilityType.REPAIR,
                            target_ship_id=ally.id
                        )
                # Move toward damaged ally
                if view.get_damaged_ships():
                    return self._move_toward(ship, view.get_damaged_ships()[0].center, view)

        # Default: move toward center of fleet
        return self._move_toward_fleet_center(ship, view)

    def _minelayer_action(self, ship: VisibleShip, view: GameView,
                          enemies: List[Position]) -> Optional[Action]:
        """Deploy mines or attack."""
        if ship.ability_info and AbilityType.DEPLOY_MINE in ship.ability_info:
            if ship.ability_info[AbilityType.DEPLOY_MINE].can_use:
                mine_pos = self._find_mine_position(ship, view, enemies)
                if mine_pos:
                    return AbilityAction(
                        ship_id=ship.id,
                        ability=AbilityType.DEPLOY_MINE,
                        target=mine_pos
                    )

        # Fall back to combat
        return self._combat_action(ship, view, enemies)

    def _artillery_action(self, ship: VisibleShip, view: GameView,
                          enemies: List[Position]) -> Optional[Action]:
        """Long-range precision strikes."""
        # Precision strike if available
        if ship.ability_info and AbilityType.PRECISION_STRIKE in ship.ability_info:
            if ship.ability_info[AbilityType.PRECISION_STRIKE].can_use:
                strike_range = ship.ability_info[AbilityType.PRECISION_STRIKE].range
                for enemy_pos in enemies:
                    if ship.center.distance_to(enemy_pos) <= strike_range:
                        return FireAction(ship_id=ship.id, target=enemy_pos,
                                         ability=AbilityType.PRECISION_STRIKE)

        # Piercing shot
        if ship.ability_info and AbilityType.PIERCING_SHOT in ship.ability_info:
            if ship.ability_info[AbilityType.PIERCING_SHOT].can_use:
                pierce_range = ship.ability_info[AbilityType.PIERCING_SHOT].range
                for enemy_pos in enemies:
                    if ship.center.distance_to(enemy_pos) <= pierce_range:
                        return FireAction(ship_id=ship.id, target=enemy_pos,
                                         ability=AbilityType.PIERCING_SHOT)

        # Stay back but in range - move away if too close
        if enemies:
            closest = min(enemies, key=lambda e: ship.center.distance_to(e))
            if ship.center.distance_to(closest) < 6:
                return self._move_away_from(ship, closest, view)

        return None

    def _carrier_action(self, ship: VisibleShip, view: GameView,
                        enemies: List[Position]) -> Optional[Action]:
        """Launch drones, stay back."""
        if ship.ability_info and AbilityType.LAUNCH_DRONE in ship.ability_info:
            if ship.ability_info[AbilityType.LAUNCH_DRONE].can_use:
                return AbilityAction(ship_id=ship.id, ability=AbilityType.LAUNCH_DRONE)

        # Stay back - move toward our side
        return self._move_toward_fleet_center(ship, view)

    def _combat_action(self, ship: VisibleShip, view: GameView,
                       enemies: List[Position]) -> Optional[Action]:
        """Standard combat: fire if in range, else move toward enemy."""
        # Try special abilities first
        if ship.ability_info:
            if AbilityType.BURST_FIRE in ship.ability_info:
                if ship.ability_info[AbilityType.BURST_FIRE].can_use:
                    burst_range = ship.ability_info[AbilityType.BURST_FIRE].range
                    for enemy_pos in enemies:
                        if ship.center.distance_to(enemy_pos) <= burst_range:
                            return FireAction(ship_id=ship.id, target=enemy_pos,
                                             ability=AbilityType.BURST_FIRE)

            if AbilityType.AREA_BOMBARDMENT in ship.ability_info:
                if ship.ability_info[AbilityType.AREA_BOMBARDMENT].can_use:
                    bomb_range = ship.ability_info[AbilityType.AREA_BOMBARDMENT].range
                    # Find cluster
                    for enemy_pos in enemies:
                        if ship.center.distance_to(enemy_pos) <= bomb_range:
                            nearby = sum(1 for e in enemies if enemy_pos.distance_to(e) <= 1)
                            if nearby >= 2:
                                return FireAction(ship_id=ship.id, target=enemy_pos,
                                                 ability=AbilityType.AREA_BOMBARDMENT)

        # Regular fire
        if ship.can_fire() and enemies:
            fire_range = ship.get_fire_range()
            for enemy_pos in enemies:
                if ship.center.distance_to(enemy_pos) <= fire_range:
                    return FireAction(ship_id=ship.id, target=enemy_pos)

        # Move toward closest enemy
        if ship.can_move() and enemies:
            closest = min(enemies, key=lambda e: ship.center.distance_to(e))
            return self._move_toward(ship, closest, view)

        return None

    def _get_storm_escape_move(self, ship: VisibleShip, view: GameView) -> Optional[MoveAction]:
        """Move out of storm."""
        if not view.storm_min or not view.storm_max or not ship.can_move():
            return None

        safe_center = Position(
            (view.storm_min.x + view.storm_max.x) // 2,
            (view.storm_min.y + view.storm_max.y) // 2,
            (view.storm_min.z + view.storm_max.z) // 2
        )
        return self._move_toward(ship, safe_center, view)

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

    def _move_toward_fleet_center(self, ship: VisibleShip, view: GameView) -> Optional[MoveAction]:
        """Move toward center of own fleet."""
        allies = view.get_alive_ships()
        if not allies:
            return None

        center_x = sum(s.center.x for s in allies) // len(allies)
        center_y = sum(s.center.y for s in allies) // len(allies)
        center_z = sum(s.center.z for s in allies) // len(allies)

        return self._move_toward(ship, Position(center_x, center_y, center_z), view)

    def _find_mine_position(self, ship: VisibleShip, view: GameView,
                            enemies: List[Position]) -> Optional[Position]:
        """Find good position for mine."""
        for adj in get_adjacent_positions(ship.center, view.grid_size):
            if view.is_in_storm(adj):
                continue
            if any(m[1] == adj for m in view.my_mines):
                continue
            # Place between us and enemies
            for enemy in enemies:
                if adj.distance_to(enemy) < ship.center.distance_to(enemy):
                    return adj
        return None

    def on_turn_result(self, result: TurnResult) -> None:
        pass
