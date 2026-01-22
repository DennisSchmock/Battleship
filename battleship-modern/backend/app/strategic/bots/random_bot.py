"""RandomBot - A baseline bot that makes random decisions.

Good for testing, but not competitive.
"""
import random
from typing import List, Tuple

from ..bot_interface import SpaceBot, random_placement
from ..models import (
    GameState, GameConfig, Action, TurnResult,
    Position, Direction,
    FireAction, MoveAction, ScanAction
)


class RandomBot(SpaceBot):
    """
    A bot that makes completely random decisions.

    Strategy:
    - Places ships randomly
    - Fires at random unknown positions
    - Sometimes moves ships randomly
    - Sometimes scans random areas

    This is the baseline - any decent bot should beat RandomBot consistently.
    """

    def get_name(self) -> str:
        return "RandomBot"

    def place_ships(self, config: GameConfig) -> List[Tuple[Position, Direction]]:
        """Place ships randomly."""
        return random_placement(config)

    def get_actions(self, state: GameState) -> List[Action]:
        """Take random actions."""
        actions = []
        x_max, y_max, z_max = state.grid_size

        for _ in range(state.actions_remaining):
            action_type = random.choice(['fire', 'fire', 'fire', 'move', 'scan'])

            if action_type == 'fire':
                # Fire at random position
                pos = Position(
                    random.randint(0, x_max - 1),
                    random.randint(0, y_max - 1),
                    random.randint(0, z_max - 1)
                )
                actions.append(FireAction(pos))

            elif action_type == 'move':
                # Move a random ship
                movable_ships = [s for s in state.my_ships if s.can_move]
                if movable_ships:
                    ship = random.choice(movable_ships)
                    direction = random.choice(list(Direction))
                    actions.append(MoveAction(ship.id, direction))
                else:
                    # Can't move, fire instead
                    pos = Position(
                        random.randint(0, x_max - 1),
                        random.randint(0, y_max - 1),
                        random.randint(0, z_max - 1)
                    )
                    actions.append(FireAction(pos))

            elif action_type == 'scan':
                # Scan random area
                pos = Position(
                    random.randint(0, x_max - 1),
                    random.randint(0, y_max - 1),
                    random.randint(0, z_max - 1)
                )
                actions.append(ScanAction(pos))

        return actions
