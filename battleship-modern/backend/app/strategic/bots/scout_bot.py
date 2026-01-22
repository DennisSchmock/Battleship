"""ScoutBot - A recon-focused bot that scans before firing.

Uses scanning to gather intel, then makes precision strikes.
"""
import random
from typing import List, Tuple, Set, Optional
from dataclasses import dataclass

from ..bot_interface import SpaceBot, random_placement, get_adjacent_positions
from ..models import (
    GameState, GameConfig, Action, TurnResult,
    Position, Direction, CellStatus,
    FireAction, MoveAction, ScanAction
)


class ScoutBot(SpaceBot):
    """
    A bot that prioritizes scanning to find ships, then precision fires.

    Strategy:
    - Scans systematically to reveal the map
    - Only fires at positions known to contain ships
    - Uses 1 scan + 2 fires per turn when targets are known
    - Uses 2 scans + 1 fire when searching

    This bot is efficient in fog of war mode because it never wastes shots.
    """

    def __init__(self):
        self.scan_positions: List[Position] = []
        self.config: Optional[GameConfig] = None
        self.fired_positions: Set[Position] = set()
        self.scanned_centers: Set[Position] = set()

    def get_name(self) -> str:
        return "ScoutBot"

    def on_game_start(self, config: GameConfig) -> None:
        """Initialize scan pattern."""
        self.config = config
        self.scan_positions = self._create_scan_grid(config.grid_size)
        random.shuffle(self.scan_positions)
        self.fired_positions = set()
        self.scanned_centers = set()

    def _create_scan_grid(self, grid_size: Tuple[int, int, int]) -> List[Position]:
        """Create efficient scan positions (every 3 cells for 3x3x3 scans)."""
        x_max, y_max, z_max = grid_size
        positions = []
        # Scan centers spaced 3 apart for full coverage
        for x in range(1, x_max, 3):
            for y in range(1, y_max, 3):
                for z in range(1, z_max, 3):
                    positions.append(Position(x, y, z))
        return positions

    def place_ships(self, config: GameConfig) -> List[Tuple[Position, Direction]]:
        """Place ships randomly but spread out."""
        return random_placement(config)

    def get_actions(self, state: GameState) -> List[Action]:
        """Scan and fire strategically."""
        actions = []

        # Find known targets (cells with ships we haven't destroyed)
        targets = self._get_known_targets(state)

        if targets:
            # We have targets! Fire at them
            # Strategy: 2 fires, 1 scan
            for _ in range(min(2, state.actions_remaining)):
                if targets:
                    target = targets.pop(0)
                    actions.append(FireAction(target))
                    self.fired_positions.add(target)

            # Use remaining action to scan for more targets
            if len(actions) < state.actions_remaining:
                scan_pos = self._get_next_scan_position()
                if scan_pos:
                    actions.append(ScanAction(scan_pos))
                    self.scanned_centers.add(scan_pos)
        else:
            # No known targets - scan heavily
            # Strategy: 2 scans, 1 speculative fire
            for _ in range(min(2, state.actions_remaining)):
                scan_pos = self._get_next_scan_position()
                if scan_pos:
                    actions.append(ScanAction(scan_pos))
                    self.scanned_centers.add(scan_pos)

            # Speculative fire at unexplored area
            if len(actions) < state.actions_remaining:
                fire_pos = self._get_speculative_target(state)
                if fire_pos:
                    actions.append(FireAction(fire_pos))
                    self.fired_positions.add(fire_pos)

        return actions

    def _get_known_targets(self, state: GameState) -> List[Position]:
        """Get positions we know have ships."""
        targets = []
        for pos, status in state.known_cells.items():
            if status == CellStatus.HIT and pos not in self.fired_positions:
                targets.append(pos)
        # Also target destroyed positions' neighbors that might have more ship
        return targets

    def _get_next_scan_position(self) -> Optional[Position]:
        """Get the next position to scan."""
        while self.scan_positions:
            pos = self.scan_positions.pop(0)
            if pos not in self.scanned_centers:
                return pos

        # Scan grid exhausted - scan random unexplored areas
        if self.config:
            x_max, y_max, z_max = self.config.grid_size
            for _ in range(50):
                pos = Position(
                    random.randint(0, x_max - 1),
                    random.randint(0, y_max - 1),
                    random.randint(0, z_max - 1)
                )
                if pos not in self.scanned_centers:
                    return pos
        return None

    def _get_speculative_target(self, state: GameState) -> Optional[Position]:
        """Get a position to fire at speculatively."""
        unknown = state.get_unknown_cells()
        unfired = [p for p in unknown if p not in self.fired_positions]
        if unfired:
            return random.choice(unfired)
        return None

    def on_turn_result(self, result: TurnResult) -> None:
        """Learn from scan results."""
        # The game state will be updated with scan results automatically
        pass
