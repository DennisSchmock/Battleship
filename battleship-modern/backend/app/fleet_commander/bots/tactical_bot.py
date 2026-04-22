"""TacticalBot - A strategic bot for Fleet Commander.

Uses different strategies based on ship type.
Uses AP system to combine move + attack when beneficial.
"""
import random as stdlib_random
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

    - Destroyers: Hunt with burst fire, move+fire combos
    - Cruisers: Area bombardment when enemies cluster
    - Artillery: Long-range precision strikes (stay back)
    - Support: Repair damaged allies, move+heal combos
    - Minelayers: Deploy mines then retreat
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

    def place_fleet(self, config: GameConfig, zone_x_min: int, zone_x_max: int,
                    rng: 'stdlib_random.Random | None' = None,
                    ) -> List[Tuple[ShipType, Position, Direction]]:
        return random_fleet_placement(config, zone_x_min, zone_x_max, rng=rng)

    def get_actions(self, view: GameView, rng: 'stdlib_random.Random | None' = None,
                    ) -> List[Action]:
        actions = []

        # Track enemy positions
        enemy_positions: List[Position] = []
        for enemy in view.visible_enemy_ships:
            enemy_positions.extend(enemy.positions)
            self.enemy_last_seen[enemy.id] = (enemy.positions[0], view.turn)

        # Process each ship that can act
        for ship in view.get_ships_that_can_act():
            ship_actions = self._get_ship_actions(ship, view, enemy_positions)
            actions.extend(ship_actions)

        return actions

    def _get_ship_actions(self, ship: VisibleShip, view: GameView,
                          enemy_positions: List[Position]) -> List[Action]:
        """Get all actions for a ship based on its type and AP."""
        actions = []
        remaining_ap = ship.action_points

        # First: Escape storm if in danger
        if any(view.is_in_storm(p) for p in ship.positions):
            move = self._get_storm_escape_move(ship, view, remaining_ap)
            if move:
                actions.append(move)
            return actions

        # Type-specific tactics
        if ship.ship_type == ShipType.SUPPORT:
            return self._support_actions(ship, view, remaining_ap)
        elif ship.ship_type == ShipType.MINELAYER:
            return self._minelayer_actions(ship, view, enemy_positions, remaining_ap)
        elif ship.ship_type == ShipType.ARTILLERY:
            return self._artillery_actions(ship, view, enemy_positions, remaining_ap)
        elif ship.ship_type == ShipType.CARRIER:
            return self._carrier_actions(ship, view, enemy_positions, remaining_ap)
        else:
            # Combat ships (Destroyer, Cruiser)
            return self._combat_actions(ship, view, enemy_positions, remaining_ap)

    def _support_actions(self, ship: VisibleShip, view: GameView, ap: int) -> List[Action]:
        """Support ships: move toward damaged allies and repair."""
        actions = []

        if not ship.ability_info or AbilityType.REPAIR not in ship.ability_info:
            return actions

        repair_info = ship.ability_info[AbilityType.REPAIR]
        repair_range = repair_info.range
        repair_cost = repair_info.ap_cost

        damaged = view.get_damaged_ships()
        if not damaged:
            return actions

        # Find closest damaged ally
        target_ally = min(damaged, key=lambda a: ship.center.distance_to(a.center))
        dist = ship.center.distance_to(target_ally.center)

        # If in range, repair
        if dist <= repair_range and repair_info.can_use and ap >= repair_cost:
            actions.append(AbilityAction(
                ship_id=ship.id,
                ability=AbilityType.REPAIR,
                target_ship_id=target_ally.id
            ))
            ap -= repair_cost

        # If not in range, try to move closer then repair
        elif dist > repair_range:
            steps_needed = dist - repair_range
            max_move = min(ap - repair_cost, ship.movement_remaining or 0)

            if max_move > 0:
                path = self._create_path_toward(ship.center, target_ally.center, max_move, view)
                if path:
                    actions.append(MoveAction(ship_id=ship.id, path=path))
                    ap -= len(path)
                    new_pos = path[-1]

                    # Check if now in range
                    if new_pos.distance_to(target_ally.center) <= repair_range and ap >= repair_cost:
                        if repair_info.can_use:
                            actions.append(AbilityAction(
                                ship_id=ship.id,
                                ability=AbilityType.REPAIR,
                                target_ship_id=target_ally.id
                            ))

        return actions

    def _minelayer_actions(self, ship: VisibleShip, view: GameView,
                           enemies: List[Position], ap: int) -> List[Action]:
        """Deploy mines then move away."""
        actions = []

        if ship.ability_info and AbilityType.DEPLOY_MINE in ship.ability_info:
            mine_info = ship.ability_info[AbilityType.DEPLOY_MINE]
            if mine_info.can_use and ap >= mine_info.ap_cost:
                mine_pos = self._find_mine_position(ship, view, enemies)
                if mine_pos:
                    actions.append(AbilityAction(
                        ship_id=ship.id,
                        ability=AbilityType.DEPLOY_MINE,
                        target=mine_pos
                    ))
                    ap -= mine_info.ap_cost

        # Move toward enemies to deploy more mines later
        if ap > 0 and enemies and ship.movement_remaining:
            closest = min(enemies, key=lambda e: ship.center.distance_to(e))
            path = self._create_path_toward(ship.center, closest, min(ap, ship.movement_remaining), view)
            if path:
                actions.append(MoveAction(ship_id=ship.id, path=path))

        return actions

    def _artillery_actions(self, ship: VisibleShip, view: GameView,
                           enemies: List[Position], ap: int) -> List[Action]:
        """Long-range strikes - prefer staying back."""
        actions = []

        if not enemies or not ship.ability_info:
            return actions

        # Try precision strike first (high damage, long range)
        if AbilityType.PRECISION_STRIKE in ship.ability_info:
            strike_info = ship.ability_info[AbilityType.PRECISION_STRIKE]
            if strike_info.can_use and ap >= strike_info.ap_cost:
                for enemy_pos in enemies:
                    if ship.center.distance_to(enemy_pos) <= strike_info.range:
                        actions.append(FireAction(
                            ship_id=ship.id, target=enemy_pos,
                            ability=AbilityType.PRECISION_STRIKE
                        ))
                        ap -= strike_info.ap_cost
                        break

        # Try piercing shot if we have AP left
        if ap > 0 and AbilityType.PIERCING_SHOT in ship.ability_info:
            pierce_info = ship.ability_info[AbilityType.PIERCING_SHOT]
            if pierce_info.can_use and ap >= pierce_info.ap_cost:
                for enemy_pos in enemies:
                    if ship.center.distance_to(enemy_pos) <= pierce_info.range:
                        actions.append(FireAction(
                            ship_id=ship.id, target=enemy_pos,
                            ability=AbilityType.PIERCING_SHOT
                        ))
                        ap -= pierce_info.ap_cost
                        break

        # Artillery should stay back - move away if too close
        closest = min(enemies, key=lambda e: ship.center.distance_to(e))
        if ship.center.distance_to(closest) < 6 and ap > 0 and ship.movement_remaining:
            move = self._move_away_from(ship, closest, view, ap)
            if move:
                actions.append(move)

        return actions

    def _carrier_actions(self, ship: VisibleShip, view: GameView,
                         enemies: List[Position], ap: int) -> List[Action]:
        """Launch drones, stay back."""
        actions = []

        if ship.ability_info and AbilityType.LAUNCH_DRONE in ship.ability_info:
            drone_info = ship.ability_info[AbilityType.LAUNCH_DRONE]
            if drone_info.can_use and ap >= drone_info.ap_cost:
                actions.append(AbilityAction(ship_id=ship.id, ability=AbilityType.LAUNCH_DRONE))
                ap -= drone_info.ap_cost

        # Stay back - move toward fleet center with remaining AP
        if ap > 0 and ship.movement_remaining:
            move = self._move_toward_fleet_center(ship, view, ap)
            if move:
                actions.append(move)

        return actions

    def _combat_actions(self, ship: VisibleShip, view: GameView,
                        enemies: List[Position], ap: int) -> List[Action]:
        """Combat ships: move into range and attack."""
        actions = []
        current_pos = ship.center

        if not enemies:
            return actions

        # Find best attack option
        best_attack, attack_cost, attack_range = self._get_best_attack(ship, ap)

        if best_attack:
            # Check if any enemy in range
            target = self._find_target_in_range(current_pos, enemies, attack_range)

            if target:
                # Fire immediately
                actions.append(FireAction(ship_id=ship.id, target=target, ability=best_attack))
                ap -= attack_cost
            else:
                # Try to move into range then fire
                closest = min(enemies, key=lambda e: current_pos.distance_to(e))
                dist = current_pos.distance_to(closest)
                steps_needed = max(0, dist - attack_range)

                max_move = min(ap - attack_cost, ship.movement_remaining or 0)

                if steps_needed <= max_move and max_move > 0:
                    path = self._create_path_toward(current_pos, closest, steps_needed, view)
                    if path:
                        actions.append(MoveAction(ship_id=ship.id, path=path))
                        ap -= len(path)
                        current_pos = path[-1]

                        # Now fire
                        target = self._find_target_in_range(current_pos, enemies, attack_range)
                        if target and ap >= attack_cost:
                            actions.append(FireAction(ship_id=ship.id, target=target, ability=best_attack))
                            ap -= attack_cost

                # If couldn't reach firing range, just move closer
                elif ap > 0 and ship.movement_remaining:
                    path = self._create_path_toward(current_pos, closest, min(ap, ship.movement_remaining), view)
                    if path:
                        actions.append(MoveAction(ship_id=ship.id, path=path))

        return actions

    def _get_best_attack(self, ship: VisibleShip, max_ap: int) -> Tuple[Optional[AbilityType], int, int]:
        """Get best attack ability that fits within AP budget."""
        if not ship.ability_info:
            return None, 0, 0

        # Priority: burst fire, area bombardment, regular fire
        options = [
            (AbilityType.BURST_FIRE, 3),  # High priority for damage
            (AbilityType.AREA_BOMBARDMENT, 2),
            (AbilityType.FIRE, 1),
        ]

        for ab_type, _ in options:
            if ab_type in ship.ability_info:
                info = ship.ability_info[ab_type]
                if info.can_use and info.ap_cost <= max_ap:
                    return ab_type, info.ap_cost, info.range

        return None, 0, 0

    def _find_target_in_range(self, from_pos: Position, enemies: List[Position],
                               range_limit: int) -> Optional[Position]:
        """Find an enemy within range."""
        for enemy in enemies:
            if from_pos.distance_to(enemy) <= range_limit:
                return enemy
        return None

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

    def _get_storm_escape_move(self, ship: VisibleShip, view: GameView,
                                ap: int) -> Optional[MoveAction]:
        """Move out of storm."""
        if not view.storm_min or not view.storm_max:
            return None

        max_move = min(ap, ship.movement_remaining or 0)
        if max_move <= 0:
            return None

        safe_center = Position(
            (view.storm_min.x + view.storm_max.x) // 2,
            (view.storm_min.y + view.storm_max.y) // 2,
            (view.storm_min.z + view.storm_max.z) // 2
        )

        path = self._create_path_toward(ship.center, safe_center, max_move, view)
        if path:
            return MoveAction(ship_id=ship.id, path=path)
        return None

    def _move_away_from(self, ship: VisibleShip, target: Position,
                        view: GameView, ap: int) -> Optional[MoveAction]:
        """Move away from a target."""
        max_move = min(ap, ship.movement_remaining or 0)
        if max_move <= 0:
            return None

        path = []
        current = ship.center

        for _ in range(max_move):
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

        if path:
            return MoveAction(ship_id=ship.id, path=path)
        return None

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
