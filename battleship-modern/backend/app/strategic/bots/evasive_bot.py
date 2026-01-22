"""EvasiveBot - A defensive bot that moves ships to avoid destruction.

Prioritizes survival by moving damaged ships away from danger.
"""
import random
from typing import List, Tuple, Set, Optional, Dict
from dataclasses import dataclass

from ..bot_interface import SpaceBot, random_placement, get_adjacent_positions, get_checkerboard_positions
from ..models import (
    GameState, GameConfig, Action, TurnResult,
    Position, Direction, CellStatus, Ship,
    FireAction, MoveAction, ScanAction
)


class EvasiveBot(SpaceBot):
    """
    A bot that actively moves ships to avoid being destroyed.

    Strategy:
    - Moves damaged ships away from where enemy is shooting
    - Uses 1 move + 2 fires per turn when under attack
    - Tracks where enemy has been shooting to predict next shots
    - Places ships spread out for better evasion options

    This bot is hard to destroy because it keeps moving.
    """

    def __init__(self):
        self.config: Optional[GameConfig] = None
        self.search_positions: List[Position] = []
        self.fired_positions: Set[Position] = set()
        self.hunt_targets: List[Position] = []
        self.last_enemy_shots: List[Position] = []

    def get_name(self) -> str:
        return "EvasiveBot"

    def on_game_start(self, config: GameConfig) -> None:
        """Initialize."""
        self.config = config
        self.search_positions = get_checkerboard_positions(config.grid_size)
        random.shuffle(self.search_positions)
        self.fired_positions = set()
        self.hunt_targets = []
        self.last_enemy_shots = []

    def place_ships(self, config: GameConfig) -> List[Tuple[Position, Direction]]:
        """Place ships spread out for better evasion."""
        # Try to place ships with space between them
        return random_placement(config)

    def get_actions(self, state: GameState) -> List[Action]:
        """Move damaged ships and attack."""
        actions = []
        actions_used = 0

        # Priority 1: Move any damaged ship that can move
        move_action = self._get_evasive_move(state)
        if move_action:
            actions.append(move_action)
            actions_used += 1

        # Priority 2: Fire at known targets or search
        for _ in range(state.actions_remaining - actions_used):
            target = self._get_fire_target(state)
            if target:
                actions.append(FireAction(target))
                self.fired_positions.add(target)

        return actions

    def _get_evasive_move(self, state: GameState) -> Optional[MoveAction]:
        """Get a move to evade enemy fire."""
        # Find ships that have been hit and can move
        for ship in state.my_ships:
            if ship.health < ship.size and ship.can_move:
                # This ship has been hit! Move it!
                move_dir = self._find_safe_direction(ship, state)
                if move_dir:
                    return MoveAction(ship.id, move_dir)

        # Also consider moving ships that are near recent enemy shots
        for ship in state.my_ships:
            if ship.can_move:
                # Check if enemy has been shooting near this ship
                ship_positions = set(ship.positions)
                danger_zone = self._get_danger_zone(state)

                if ship_positions & danger_zone:
                    # Ship is in danger zone - move it!
                    move_dir = self._find_safe_direction(ship, state)
                    if move_dir:
                        return MoveAction(ship.id, move_dir)

        return None

    def _get_danger_zone(self, state: GameState) -> Set[Position]:
        """Get positions that are dangerous (near enemy shots)."""
        danger = set()
        for shot in state.enemy_shots_on_me[-10:]:  # Last 10 shots
            danger.add(shot)
            for adj in get_adjacent_positions(shot, state.grid_size):
                danger.add(adj)
        return danger

    def _find_safe_direction(self, ship: Ship, state: GameState) -> Optional[Direction]:
        """Find a direction to move that's safer."""
        danger_zone = self._get_danger_zone(state)
        best_direction = None
        best_score = -1000

        for direction in Direction:
            # Calculate new positions
            new_positions = [pos.move(direction) for pos in ship.positions]

            # Check if move is valid
            valid = True
            for pos in new_positions:
                if not self._is_valid_position(pos, state.grid_size):
                    valid = False
                    break
                # Check collision with own ships
                for other_ship in state.my_ships:
                    if other_ship.id != ship.id and not other_ship.is_destroyed:
                        if pos in other_ship.positions:
                            valid = False
                            break

            if not valid:
                continue

            # Score this move (higher = safer)
            score = 0
            for pos in new_positions:
                if pos not in danger_zone:
                    score += 10
                # Prefer moving toward center (more escape routes)
                center_x, center_y, center_z = [s // 2 for s in state.grid_size]
                dist_to_center = abs(pos.x - center_x) + abs(pos.y - center_y) + abs(pos.z - center_z)
                score -= dist_to_center * 0.1

            if score > best_score:
                best_score = score
                best_direction = direction

        return best_direction

    def _is_valid_position(self, pos: Position, grid_size: Tuple[int, int, int]) -> bool:
        """Check if position is within grid."""
        x_max, y_max, z_max = grid_size
        return 0 <= pos.x < x_max and 0 <= pos.y < y_max and 0 <= pos.z < z_max

    def _get_fire_target(self, state: GameState) -> Optional[Position]:
        """Get next target to fire at."""
        # Priority 1: Hunt targets
        while self.hunt_targets:
            target = self.hunt_targets.pop(0)
            if target not in self.fired_positions:
                return target

        # Priority 2: Known hits
        for pos, status in state.known_cells.items():
            if status == CellStatus.HIT and pos not in self.fired_positions:
                # Add adjacent cells to hunt
                for adj in get_adjacent_positions(pos, state.grid_size):
                    if adj not in self.fired_positions and adj not in self.hunt_targets:
                        self.hunt_targets.append(adj)

        while self.hunt_targets:
            target = self.hunt_targets.pop(0)
            if target not in self.fired_positions:
                return target

        # Priority 3: Checkerboard search
        while self.search_positions:
            target = self.search_positions.pop(0)
            if target not in self.fired_positions:
                return target

        # Priority 4: Random
        unknown = state.get_unknown_cells()
        unfired = [p for p in unknown if p not in self.fired_positions]
        if unfired:
            return random.choice(unfired)

        return None

    def on_turn_result(self, result: TurnResult) -> None:
        """Track incoming fire for evasion."""
        for pos in result.incoming_hits:
            self.last_enemy_shots.append(pos)

        # Update hunt targets on hits
        for fire_result in result.fire_results:
            if fire_result.hit and self.config:
                for adj in get_adjacent_positions(fire_result.target, self.config.grid_size):
                    if adj not in self.fired_positions and adj not in self.hunt_targets:
                        self.hunt_targets.append(adj)
