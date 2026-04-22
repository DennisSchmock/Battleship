"""DefensiveBot - Defensive-focused bot for Fleet Commander.

Prioritizes survival and counter-attacks from safe distance.
Uses AP system to retreat + shield, or fire + retreat.
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


class DefensiveBot(FleetBot):
    """
    A defensive bot that prioritizes survival:

    Strategy:
    1. Support ships: move to allies + repair
    2. Damaged ships: retreat + shield
    3. Counter-attack from safe distance, then retreat
    4. Deploy mines defensively
    """

    def __init__(self):
        self.config: Optional[GameConfig] = None
        self.safe_zone_center: Optional[Position] = None

    def get_name(self) -> str:
        return "DefensiveBot"

    def on_game_start(self, config: GameConfig) -> None:
        self.config = config

    def place_fleet(self, config: GameConfig, zone_x_min: int, zone_x_max: int,
                    rng: 'stdlib_random.Random | None' = None,
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
        return random_fleet_placement(config, zone_x_min, zone_x_max, rng=rng)

    def get_actions(self, view: GameView, rng: 'stdlib_random.Random | None' = None,
                    ) -> List[Action]:
        actions = []

        # Collect enemy positions
        enemy_positions: List[Position] = []
        for enemy in view.visible_enemy_ships:
            enemy_positions.extend(enemy.positions)

        # Calculate danger zone
        danger_zone = self._calculate_danger_zone(enemy_positions)

        # Process ships by priority
        for ship in view.get_ships_that_can_act():
            ship_actions = self._get_ship_actions(ship, view, enemy_positions, danger_zone)
            actions.extend(ship_actions)

        return actions

    def _get_ship_actions(self, ship: VisibleShip, view: GameView,
                          enemies: List[Position], danger: Set[Position]) -> List[Action]:
        """Get all actions for a ship based on its role and situation."""
        ap = ship.action_points

        # Support ships: repair damaged allies
        if ship.ship_type == ShipType.SUPPORT:
            return self._support_actions(ship, view, ap)

        # Damaged ships: retreat or shield
        if ship.hp and ship.max_hp and ship.hp < ship.max_hp * 0.5:
            return self._retreat_actions(ship, view, enemies, ap)

        # Minelayers: deploy mines defensively
        if ship.ship_type == ShipType.MINELAYER:
            return self._minelayer_actions(ship, view, enemies, ap)

        # Combat ships: counter-attack from safe distance
        return self._counter_attack_actions(ship, view, enemies, danger, ap)

    def _support_actions(self, ship: VisibleShip, view: GameView, ap: int) -> List[Action]:
        """Repair damaged allies, moving closer if needed."""
        actions = []

        if not ship.ability_info or AbilityType.REPAIR not in ship.ability_info:
            return self._retreat_to_safe_zone(ship, view, ap)

        repair_info = ship.ability_info[AbilityType.REPAIR]
        repair_range = repair_info.range
        repair_cost = repair_info.ap_cost

        damaged = view.get_damaged_ships()
        if not damaged:
            return self._retreat_to_safe_zone(ship, view, ap)

        # Find most damaged ally
        most_damaged = min(damaged, key=lambda s: s.hp / s.max_hp if s.max_hp else 1)
        dist = ship.center.distance_to(most_damaged.center)

        # If in range, repair first
        if dist <= repair_range and repair_info.can_use and ap >= repair_cost:
            actions.append(AbilityAction(
                ship_id=ship.id,
                ability=AbilityType.REPAIR,
                target_ship_id=most_damaged.id
            ))
            ap -= repair_cost

        # If not in range, move closer then repair
        elif dist > repair_range and repair_info.can_use:
            steps_needed = dist - repair_range
            max_move = min(ap - repair_cost, ship.movement_remaining or 0)

            if max_move > 0:
                path = self._create_path_toward(ship.center, most_damaged.center,
                                                min(steps_needed, max_move), view)
                if path:
                    actions.append(MoveAction(ship_id=ship.id, path=path))
                    ap -= len(path)
                    new_pos = path[-1]

                    # Check if now in range
                    if new_pos.distance_to(most_damaged.center) <= repair_range and ap >= repair_cost:
                        actions.append(AbilityAction(
                            ship_id=ship.id,
                            ability=AbilityType.REPAIR,
                            target_ship_id=most_damaged.id
                        ))
                        ap -= repair_cost

        # Use remaining AP to stay near fleet
        if ap > 0 and ship.movement_remaining:
            move = self._move_toward_fleet_center(ship, view, ap)
            if move:
                actions.append(move)

        return actions

    def _retreat_actions(self, ship: VisibleShip, view: GameView,
                         enemies: List[Position], ap: int) -> List[Action]:
        """Retreat to safety, use shield if needed."""
        actions = []

        # Fire first if enemies are close (might as well damage them)
        if enemies and ship.can_fire():
            fire_range = ship.get_fire_range()
            for enemy_pos in enemies:
                if ship.center.distance_to(enemy_pos) <= fire_range:
                    # Find cheapest fire option
                    if ship.ability_info and AbilityType.FIRE in ship.ability_info:
                        fire_info = ship.ability_info[AbilityType.FIRE]
                        if fire_info.can_use and ap >= fire_info.ap_cost:
                            actions.append(FireAction(ship_id=ship.id, target=enemy_pos))
                            ap -= fire_info.ap_cost
                            break

        # Use shield if available and enemies very close
        if ship.ability_info and AbilityType.SHIELD in ship.ability_info:
            shield_info = ship.ability_info[AbilityType.SHIELD]
            if shield_info.can_use and ap >= shield_info.ap_cost:
                if any(ship.center.distance_to(e) <= 4 for e in enemies):
                    actions.append(AbilityAction(ship_id=ship.id, ability=AbilityType.SHIELD))
                    ap -= shield_info.ap_cost

        # Retreat with remaining AP
        if ap > 0 and ship.movement_remaining and enemies:
            closest = min(enemies, key=lambda e: ship.center.distance_to(e))
            path = self._create_path_away(ship.center, closest, min(ap, ship.movement_remaining), view)
            if path:
                actions.append(MoveAction(ship_id=ship.id, path=path))

        return actions

    def _minelayer_actions(self, ship: VisibleShip, view: GameView,
                           enemies: List[Position], ap: int) -> List[Action]:
        """Deploy mines between us and enemies, then retreat."""
        actions = []

        if ship.ability_info and AbilityType.DEPLOY_MINE in ship.ability_info:
            mine_info = ship.ability_info[AbilityType.DEPLOY_MINE]
            if mine_info.can_use and ap >= mine_info.ap_cost:
                mine_pos = self._find_defensive_mine_pos(ship, view, enemies)
                if mine_pos:
                    actions.append(AbilityAction(
                        ship_id=ship.id,
                        ability=AbilityType.DEPLOY_MINE,
                        target=mine_pos
                    ))
                    ap -= mine_info.ap_cost

        # Retreat toward safe zone with remaining AP
        if ap > 0 and ship.movement_remaining:
            retreat = self._retreat_to_safe_zone(ship, view, ap)
            actions.extend(retreat)

        return actions

    def _counter_attack_actions(self, ship: VisibleShip, view: GameView,
                                 enemies: List[Position], danger: Set[Position],
                                 ap: int) -> List[Action]:
        """Attack from safe distance, then retreat."""
        actions = []
        current_pos = ship.center

        # If in danger zone, retreat first
        if current_pos in danger:
            return self._retreat_to_safe_zone(ship, view, ap)

        # Fire at enemies in range
        if enemies and ship.ability_info:
            # Find best attack we can afford
            best_attack = None
            best_cost = 0
            best_range = 0

            for ab_type in [AbilityType.FIRE, AbilityType.BURST_FIRE, AbilityType.AREA_BOMBARDMENT,
                            AbilityType.PIERCING_SHOT, AbilityType.PRECISION_STRIKE]:
                if ab_type in ship.ability_info:
                    info = ship.ability_info[ab_type]
                    if info.can_use and info.ap_cost <= ap:
                        best_attack = ab_type
                        best_cost = info.ap_cost
                        best_range = info.range
                        break  # Take first available

            if best_attack:
                for enemy_pos in enemies:
                    if current_pos.distance_to(enemy_pos) <= best_range:
                        actions.append(FireAction(ship_id=ship.id, target=enemy_pos,
                                                 ability=best_attack))
                        ap -= best_cost
                        break

        # After attacking, retreat if enemies are close
        if enemies and ap > 0 and ship.movement_remaining:
            closest = min(enemies, key=lambda e: current_pos.distance_to(e))
            if current_pos.distance_to(closest) < 8:
                path = self._create_path_away(current_pos, closest,
                                              min(ap, ship.movement_remaining), view)
                if path:
                    actions.append(MoveAction(ship_id=ship.id, path=path))

        return actions

    def _retreat_to_safe_zone(self, ship: VisibleShip, view: GameView, ap: int) -> List[Action]:
        """Move toward safe zone."""
        if not self.safe_zone_center:
            return []

        max_move = min(ap, ship.movement_remaining or 0)
        if max_move <= 0:
            return []

        path = self._create_path_toward(ship.center, self.safe_zone_center, max_move, view)
        if path:
            return [MoveAction(ship_id=ship.id, path=path)]
        return []

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

    def _create_path_toward(self, from_pos: Position, target: Position,
                            max_steps: int, view: GameView) -> List[Position]:
        """Create path toward target."""
        path = []
        current = from_pos

        for _ in range(max_steps):
            best_dir = None
            best_dist = current.distance_to(target)

            for direction in Direction:
                new_pos = current.move(direction)
                if not view.is_valid_position(new_pos) or view.is_in_storm(new_pos):
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

    def _create_path_away(self, from_pos: Position, target: Position,
                          max_steps: int, view: GameView) -> List[Position]:
        """Create path away from target."""
        path = []
        current = from_pos

        for _ in range(max_steps):
            best_dir = None
            best_dist = current.distance_to(target)

            for direction in Direction:
                new_pos = current.move(direction)
                if not view.is_valid_position(new_pos) or view.is_in_storm(new_pos):
                    continue
                dist = new_pos.distance_to(target)
                if dist > best_dist:
                    best_dist = dist
                    best_dir = direction

            if best_dir:
                current = current.move(best_dir)
                path.append(current)
            else:
                break

        return path

    def _move_toward_fleet_center(self, ship: VisibleShip, view: GameView,
                                   ap: int) -> Optional[MoveAction]:
        """Move toward center of own fleet."""
        allies = view.get_alive_ships()
        if not allies:
            return None

        center_x = sum(s.center.x for s in allies) // len(allies)
        center_y = sum(s.center.y for s in allies) // len(allies)
        center_z = sum(s.center.z for s in allies) // len(allies)
        center = Position(center_x, center_y, center_z)

        max_move = min(ap, ship.movement_remaining or 0)
        if max_move <= 0:
            return None

        path = self._create_path_toward(ship.center, center, max_move, view)
        if path:
            return MoveAction(ship_id=ship.id, path=path)
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
