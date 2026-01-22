"""Bot interface for Strategic SpaceBattleship.

Developers implement the SpaceBot class to create their own bots.

Example:
    class MyBot(SpaceBot):
        def get_name(self) -> str:
            return "MyAwesomeBot"

        def place_ships(self, config: GameConfig) -> List[Tuple[Position, Direction]]:
            # Return starting position and direction for each ship
            return [
                (Position(0, 0, 0), Direction.EAST),
                (Position(0, 2, 0), Direction.EAST),
                # ...
            ]

        def get_actions(self, state: GameState) -> List[Action]:
            # Return up to 3 actions
            return [
                FireAction(Position(5, 5, 4)),
                ScanAction(Position(6, 6, 4)),
                MoveAction("destroyer_4", Direction.NORTH)
            ]

        def on_turn_result(self, result: TurnResult) -> None:
            # Learn from results (optional)
            pass
"""
from abc import ABC, abstractmethod
from typing import List, Tuple, Optional

from .models import (
    GameState, GameConfig, Action, TurnResult,
    Position, Direction, Ship,
    FireAction, MoveAction, ScanAction,
    CellStatus
)


class SpaceBot(ABC):
    """
    Base class for Strategic SpaceBattleship bots.

    Implement this class to create your own bot for the tournament.
    """

    @abstractmethod
    def get_name(self) -> str:
        """Return the name of your bot."""
        pass

    @abstractmethod
    def place_ships(self, config: GameConfig) -> List[Tuple[Position, Direction]]:
        """
        Place your ships on the board.

        Args:
            config: Game configuration including grid size and ship list

        Returns:
            List of (start_position, direction) tuples, one for each ship.
            Ships are placed in order: Carrier(5), Battleship(4), Cruiser(3), Submarine(3), Destroyer(2)
        """
        pass

    @abstractmethod
    def get_actions(self, state: GameState) -> List[Action]:
        """
        Decide what actions to take this turn.

        Args:
            state: Current game state from your perspective

        Returns:
            List of up to 3 actions (FireAction, MoveAction, ScanAction)
        """
        pass

    def on_turn_result(self, result: TurnResult) -> None:
        """
        Called after your turn with the results.

        Override this to learn from results (optional).

        Args:
            result: Results of all your actions this turn
        """
        pass

    def on_game_start(self, config: GameConfig) -> None:
        """
        Called when a new game starts.

        Override this to initialize state (optional).
        """
        pass

    def on_game_end(self, won: bool, state: GameState) -> None:
        """
        Called when the game ends.

        Override this to learn from the game (optional).

        Args:
            won: True if you won
            state: Final game state
        """
        pass


# === HELPER FUNCTIONS FOR BOT DEVELOPERS ===

def random_placement(config: GameConfig) -> List[Tuple[Position, Direction]]:
    """Helper: Generate random ship placements."""
    import random

    placements = []
    occupied = set()
    x_max, y_max, z_max = config.grid_size
    directions = list(Direction)

    for ship_name, ship_size in config.ships:
        placed = False
        for _ in range(1000):
            start = Position(
                random.randint(0, x_max - 1),
                random.randint(0, y_max - 1),
                random.randint(0, z_max - 1)
            )
            direction = random.choice(directions)

            # Calculate all positions
            positions = [start]
            current = start
            for _ in range(ship_size - 1):
                current = current.move(direction)
                positions.append(current)

            # Check validity
            valid = True
            for pos in positions:
                if not (0 <= pos.x < x_max and 0 <= pos.y < y_max and 0 <= pos.z < z_max):
                    valid = False
                    break
                if pos in occupied:
                    valid = False
                    break

            if valid:
                placements.append((start, direction))
                for pos in positions:
                    occupied.add(pos)
                placed = True
                break

        if not placed:
            raise RuntimeError(f"Could not place {ship_name}")

    return placements


def get_adjacent_positions(pos: Position, grid_size: Tuple[int, int, int]) -> List[Position]:
    """Helper: Get all valid adjacent positions (6 directions in 3D)."""
    x_max, y_max, z_max = grid_size
    adjacent = []
    for direction in Direction:
        new_pos = pos.move(direction)
        if 0 <= new_pos.x < x_max and 0 <= new_pos.y < y_max and 0 <= new_pos.z < z_max:
            adjacent.append(new_pos)
    return adjacent


def get_checkerboard_positions(grid_size: Tuple[int, int, int]) -> List[Position]:
    """Helper: Get positions in a 3D checkerboard pattern (efficient search)."""
    x_max, y_max, z_max = grid_size
    positions = []
    for x in range(x_max):
        for y in range(y_max):
            for z in range(z_max):
                if (x + y + z) % 2 == 0:
                    positions.append(Position(x, y, z))
    return positions
