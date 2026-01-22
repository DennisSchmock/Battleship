"""RandomBot - Baseline random bot for Fleet Commander.

Takes random actions - useful as a baseline to compare other bots against.
"""
import random
from typing import List, Tuple, Optional

from ..bot_interface import (
    FleetBot, GameView, VisibleShip, random_fleet_placement,
    get_adjacent_positions
)
from ..models import (
    Position, Direction, ShipType, AbilityType, CellStatus,
    GameConfig, Action, MoveAction, FireAction, ScanAction, AbilityAction,
    TurnResult, SHIP_CONFIGS
)


class RandomBot(FleetBot):
    """
    A baseline bot that takes random actions.

    Useful for testing and comparing bot strategies.
    """

    def __init__(self):
        self.config: Optional[GameConfig] = None

    def get_name(self) -> str:
        return "RandomBot"

    def on_game_start(self, config: GameConfig) -> None:
        self.config = config

    def place_fleet(self, config: GameConfig, zone_x_min: int, zone_x_max: int
                    ) -> List[Tuple[ShipType, Position, Direction]]:
        return random_fleet_placement(config, zone_x_min, zone_x_max)

    def get_actions(self, view: GameView) -> List[Action]:
        actions = []
        action_points_used = 0

        # Get list of alive ships
        alive_ships = [s for s in view.my_ships if s.hp and s.hp > 0]
        random.shuffle(alive_ships)

        for ship in alive_ships:
            if action_points_used >= view.action_points:
                break

            cost = SHIP_CONFIGS[ship.ship_type].action_cost
            if action_points_used + cost > view.action_points:
                continue

            # Pick random action type
            action_type = random.choice(['fire', 'move', 'scan', 'move'])  # Bias toward move

            ship_center = ship.positions[len(ship.positions) // 2]
            action = None

            if action_type == 'fire':
                action = self._random_fire(ship, view)
            elif action_type == 'scan':
                action = self._random_scan(ship, view)
            elif action_type == 'move':
                action = self._random_move(ship, view)

            if action:
                actions.append(action)
                action_points_used += cost

        return actions

    def _random_fire(self, ship: VisibleShip, view: GameView) -> Optional[FireAction]:
        """Fire at a random valid position."""
        if not ship.abilities or AbilityType.FIRE not in ship.abilities:
            return None
        if not ship.abilities[AbilityType.FIRE]:
            return None

        ship_center = ship.positions[len(ship.positions) // 2]

        # Get fire range
        fire_range = 4
        for ab in SHIP_CONFIGS[ship.ship_type].abilities:
            if ab.ability_type == AbilityType.FIRE:
                fire_range = ab.range
                break

        # Try to hit visible enemies first
        if view.visible_enemy_ships:
            enemy = random.choice(view.visible_enemy_ships)
            if enemy.positions:
                target = random.choice(enemy.positions)
                if ship_center.distance_to(target) <= fire_range:
                    return FireAction(ship_id=ship.id, target=target)

        # Otherwise fire randomly within range
        for _ in range(20):
            target = Position(
                ship_center.x + random.randint(-fire_range, fire_range),
                ship_center.y + random.randint(-fire_range, fire_range),
                ship_center.z + random.randint(-fire_range, fire_range)
            )

            if not view.is_valid_position(target):
                continue
            if ship_center.distance_to(target) > fire_range:
                continue
            if view.get_cell_status(target) in [CellStatus.HIT, CellStatus.DESTROYED]:
                continue

            return FireAction(ship_id=ship.id, target=target)

        return None

    def _random_scan(self, ship: VisibleShip, view: GameView) -> Optional[ScanAction]:
        """Scan a random position."""
        if not ship.abilities or AbilityType.SCAN not in ship.abilities:
            return None
        if not ship.abilities[AbilityType.SCAN]:
            return None

        ship_center = ship.positions[len(ship.positions) // 2]

        # Get scan range
        scan_range = 5
        for ab in SHIP_CONFIGS[ship.ship_type].abilities:
            if ab.ability_type == AbilityType.SCAN:
                scan_range = ab.range
                break

        # Scan random position in range
        for _ in range(20):
            target = Position(
                ship_center.x + random.randint(-scan_range, scan_range),
                ship_center.y + random.randint(-scan_range, scan_range),
                ship_center.z + random.randint(-scan_range, scan_range)
            )

            if not view.is_valid_position(target):
                continue
            if ship_center.distance_to(target) > scan_range:
                continue

            return ScanAction(ship_id=ship.id, center=target)

        return None

    def _random_move(self, ship: VisibleShip, view: GameView) -> Optional[MoveAction]:
        """Move in a random valid direction."""
        ship_center = ship.positions[len(ship.positions) // 2]

        # Get valid directions
        valid_dirs = []
        for direction in Direction:
            new_pos = ship_center.move(direction)
            if view.is_valid_position(new_pos) and not view.is_in_storm(new_pos):
                valid_dirs.append(direction)

        if valid_dirs:
            direction = random.choice(valid_dirs)
            return MoveAction(ship_id=ship.id, path=[ship_center.move(direction)])

        return None

    def on_turn_result(self, result: TurnResult) -> None:
        """Random bot doesn't learn."""
        pass
