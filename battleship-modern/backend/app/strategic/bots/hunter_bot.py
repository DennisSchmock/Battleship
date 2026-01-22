"""HunterBot - A systematic search and destroy bot.

Uses checkerboard pattern for efficient searching, then hunts down hit ships.
"""
import random
from typing import List, Tuple, Set, Optional
from dataclasses import dataclass, field

from ..bot_interface import SpaceBot, random_placement, get_adjacent_positions, get_checkerboard_positions
from ..models import (
    GameState, GameConfig, Action, TurnResult,
    Position, Direction, CellStatus,
    FireAction, MoveAction, ScanAction
)


class HunterBot(SpaceBot):
    """
    A bot that systematically searches using checkerboard pattern,
    then hunts down ships when hits are found.

    Strategy:
    - Uses 3D checkerboard pattern for initial search (covers all ships efficiently)
    - When a hit is found, switches to hunt mode to destroy the ship
    - Prioritizes destroying partially damaged ships
    - Never scans (relies on ship destruction for confirmation)
    - Never moves (stationary defense)

    This is a solid baseline strategy.
    """

    def __init__(self):
        self.search_positions: List[Position] = []
        self.hunt_targets: List[Position] = []
        self.fired_positions: Set[Position] = set()
        self.config: Optional[GameConfig] = None

    def get_name(self) -> str:
        return "HunterBot"

    def on_game_start(self, config: GameConfig) -> None:
        """Initialize search pattern."""
        self.config = config
        self.search_positions = get_checkerboard_positions(config.grid_size)
        random.shuffle(self.search_positions)  # Randomize order
        self.hunt_targets = []
        self.fired_positions = set()

    def place_ships(self, config: GameConfig) -> List[Tuple[Position, Direction]]:
        """Place ships randomly."""
        return random_placement(config)

    def get_actions(self, state: GameState) -> List[Action]:
        """Fire at targets systematically."""
        actions = []

        for _ in range(state.actions_remaining):
            target = self._get_next_target(state)
            if target:
                actions.append(FireAction(target))
                self.fired_positions.add(target)
            else:
                break

        return actions

    def _get_next_target(self, state: GameState) -> Optional[Position]:
        """Get the next position to fire at."""
        # Priority 1: Hunt targets (adjacent to confirmed hits)
        while self.hunt_targets:
            target = self.hunt_targets.pop(0)
            if target not in self.fired_positions:
                return target

        # Priority 2: Check if we have any known hits that need hunting
        known_hits = state.get_hits()
        for hit_pos in known_hits:
            adjacent = get_adjacent_positions(hit_pos, state.grid_size)
            for adj in adjacent:
                if adj not in self.fired_positions and adj not in state.known_cells:
                    self.hunt_targets.append(adj)

        # Try hunt targets again
        while self.hunt_targets:
            target = self.hunt_targets.pop(0)
            if target not in self.fired_positions:
                return target

        # Priority 3: Checkerboard search
        while self.search_positions:
            target = self.search_positions.pop(0)
            if target not in self.fired_positions:
                return target

        # Priority 4: Any remaining position
        unknown = state.get_unknown_cells()
        unfired = [p for p in unknown if p not in self.fired_positions]
        if unfired:
            return random.choice(unfired)

        return None

    def on_turn_result(self, result: TurnResult) -> None:
        """Update hunt targets when we destroy a ship."""
        for fire_result in result.fire_results:
            if fire_result.destroyed_ship:
                # Ship destroyed! We now know where it was.
                # Remove any hunt targets that were for this ship
                pass  # The game state will update known_cells

            elif fire_result.hit:
                # We hit something! Add adjacent cells to hunt.
                # Note: In fog of war, we might not know we hit unless destroyed
                adjacent = get_adjacent_positions(fire_result.target, self.config.grid_size)
                for adj in adjacent:
                    if adj not in self.fired_positions and adj not in self.hunt_targets:
                        self.hunt_targets.append(adj)
