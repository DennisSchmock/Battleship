"""PredictorBot - A smart bot that predicts enemy ship movements AND learns attack patterns.

Two-way prediction:
1. OFFENSE: When you hit a ship, predict where it will move and follow up
2. DEFENSE: Learn enemy's shooting pattern and move ships BEFORE they get hit
"""
import random
from typing import List, Tuple, Set, Optional, Dict
from dataclasses import dataclass, field
from collections import defaultdict

from ..bot_interface import SpaceBot, random_placement, get_adjacent_positions, get_checkerboard_positions
from ..models import (
    GameState, GameConfig, Action, TurnResult,
    Position, Direction, CellStatus, Ship,
    FireAction, MoveAction, ScanAction
)


@dataclass
class TrackedHit:
    """A hit we're tracking for prediction."""
    position: Position
    turn_hit: int
    predicted_moves: List[Position] = field(default_factory=list)
    follow_up_fired: Set[Position] = field(default_factory=set)


@dataclass
class EnemyPatternAnalysis:
    """Analysis of enemy shooting patterns."""
    shots: List[Position] = field(default_factory=list)
    uses_checkerboard: bool = False
    tends_to_hunt: bool = False
    hunt_direction: Optional[Direction] = None  # If they hunt in a consistent direction


class PredictorBot(SpaceBot):
    """
    A bot that predicts BOTH enemy ship movements AND enemy attack patterns.

    OFFENSE Strategy:
    - When hitting a ship, predict where it will move (6 directions)
    - Weight predictions: ships move toward center, away from danger
    - Scan predicted areas, then fire at most likely positions

    DEFENSE Strategy:
    - Analyze enemy's shooting pattern (checkerboard? hunt mode? random?)
    - Predict where enemy will shoot next
    - Move ships BEFORE they get hit (proactive evasion)

    This makes it hard for the enemy to hit us, while we hunt them down efficiently.
    """

    def __init__(self):
        self.config: Optional[GameConfig] = None
        self.search_positions: List[Position] = []
        self.fired_positions: Set[Position] = set()
        self.current_turn: int = 0

        # OFFENSE: Prediction tracking for enemy ships
        self.tracked_hits: List[TrackedHit] = []
        self.high_priority_targets: List[Position] = []
        self.scan_targets: List[Position] = []

        # DEFENSE: Enemy pattern learning
        self.enemy_analysis = EnemyPatternAnalysis()

    def get_name(self) -> str:
        return "PredictorBot"

    def on_game_start(self, config: GameConfig) -> None:
        """Initialize for new game."""
        self.config = config
        self.search_positions = get_checkerboard_positions(config.grid_size)
        random.shuffle(self.search_positions)
        self.fired_positions = set()
        self.tracked_hits = []
        self.high_priority_targets = []
        self.scan_targets = []
        self.current_turn = 0
        self.enemy_analysis = EnemyPatternAnalysis()

    def place_ships(self, config: GameConfig) -> List[Tuple[Position, Direction]]:
        """Place ships spread out."""
        return random_placement(config)

    def get_actions(self, state: GameState) -> List[Action]:
        """Decide actions using both offensive prediction and defensive learning."""
        self.current_turn = state.turn
        actions = []
        actions_used = 0

        # === DEFENSE: Proactive movement based on predicted enemy shots ===
        predicted_danger = self._predict_enemy_next_shots(state)
        proactive_move = self._get_proactive_move(state, predicted_danger)
        if proactive_move:
            actions.append(proactive_move)
            actions_used += 1

        # Also move damaged ships (reactive evasion) if no proactive move
        if actions_used == 0:
            reactive_move = self._get_reactive_move(state)
            if reactive_move:
                actions.append(reactive_move)
                actions_used += 1

        # === OFFENSE: Scan and fire at predicted positions ===

        # Scan for predicted ship locations (if we have scan targets)
        if actions_used < state.actions_remaining and self.scan_targets:
            scan_pos = self.scan_targets.pop(0)
            if self._is_valid_position(scan_pos, state.grid_size):
                actions.append(ScanAction(scan_pos))
                actions_used += 1

        # Fire at high-priority predicted positions
        for _ in range(state.actions_remaining - actions_used):
            target = self._get_smart_target(state)
            if target:
                actions.append(FireAction(target))
                self.fired_positions.add(target)

        return actions

    # ==================== DEFENSE: Pattern Learning ====================

    def _analyze_enemy_pattern(self) -> None:
        """Analyze enemy shooting pattern from history."""
        shots = self.enemy_analysis.shots

        if len(shots) < 5:
            return

        # Check for checkerboard pattern
        checkerboard_count = sum(1 for s in shots if (s.x + s.y + s.z) % 2 == 0)
        self.enemy_analysis.uses_checkerboard = checkerboard_count > len(shots) * 0.65

        # Check for hunt mode (consecutive shots are adjacent)
        hunt_sequences = 0
        direction_counts: Dict[Direction, int] = defaultdict(int)

        for i in range(1, len(shots)):
            diff = (
                shots[i].x - shots[i-1].x,
                shots[i].y - shots[i-1].y,
                shots[i].z - shots[i-1].z
            )
            dist = abs(diff[0]) + abs(diff[1]) + abs(diff[2])

            if dist == 1:
                hunt_sequences += 1
                # Track which direction they tend to hunt
                for d in Direction:
                    if d.value == diff:
                        direction_counts[d] += 1

        self.enemy_analysis.tends_to_hunt = hunt_sequences > len(shots) * 0.25

        # Find most common hunt direction
        if direction_counts:
            self.enemy_analysis.hunt_direction = max(direction_counts, key=direction_counts.get)

    def _predict_enemy_next_shots(self, state: GameState) -> Set[Position]:
        """Predict where enemy will shoot next based on learned patterns."""
        predicted = set()

        if not self.config:
            return predicted

        shots = self.enemy_analysis.shots
        grid_size = state.grid_size

        # If enemy tends to hunt and has hit us recently
        if self.enemy_analysis.tends_to_hunt:
            # Find positions where they hit our ships
            for shot in state.enemy_shots_on_me[-5:]:
                for ship in state.my_ships:
                    # If this shot was near one of our ships
                    for ship_pos in ship.positions:
                        dist = (abs(shot.x - ship_pos.x) +
                               abs(shot.y - ship_pos.y) +
                               abs(shot.z - ship_pos.z))
                        if dist <= 1:
                            # They're hunting this ship! Predict adjacent cells
                            for adj in get_adjacent_positions(shot, grid_size):
                                predicted.add(adj)

                            # Extra weight on their preferred hunt direction
                            if self.enemy_analysis.hunt_direction:
                                next_in_dir = shot.move(self.enemy_analysis.hunt_direction)
                                if self._is_valid_position(next_in_dir, grid_size):
                                    predicted.add(next_in_dir)

        # If enemy uses checkerboard, predict unchecked checkerboard cells near our ships
        if self.enemy_analysis.uses_checkerboard:
            shot_set = set(shots)
            for ship in state.my_ships:
                if ship.is_destroyed:
                    continue
                for pos in ship.positions:
                    # Check nearby checkerboard cells
                    for dx in range(-2, 3):
                        for dy in range(-2, 3):
                            for dz in range(-2, 3):
                                check = Position(pos.x + dx, pos.y + dy, pos.z + dz)
                                if (check.x + check.y + check.z) % 2 == 0:
                                    if self._is_valid_position(check, grid_size):
                                        if check not in shot_set:
                                            predicted.add(check)

        # Always predict adjacent to their last few shots
        for shot in shots[-3:]:
            for adj in get_adjacent_positions(shot, grid_size):
                predicted.add(adj)

        return predicted

    def _get_proactive_move(self, state: GameState, predicted_danger: Set[Position]) -> Optional[MoveAction]:
        """Move a ship BEFORE it gets hit based on predicted enemy shots."""
        if not predicted_danger:
            return None

        # Find ships that are in predicted danger AND can move
        for ship in state.my_ships:
            if not ship.can_move or ship.is_destroyed:
                continue

            # Count how many of ship's cells are in danger
            danger_count = sum(1 for pos in ship.positions if pos in predicted_danger)

            # If significant portion is in danger, move
            if danger_count >= 1:
                best_dir = None
                best_score = -1000

                for direction in Direction:
                    new_positions = [pos.move(direction) for pos in ship.positions]

                    # Check validity
                    valid = all(
                        self._is_valid_position(p, state.grid_size) and
                        not any(p in other.positions for other in state.my_ships
                               if other.id != ship.id and not other.is_destroyed)
                        for p in new_positions
                    )

                    if not valid:
                        continue

                    # Score: fewer positions in danger = better
                    new_danger_count = sum(1 for p in new_positions if p in predicted_danger)
                    score = danger_count - new_danger_count  # Positive = improvement

                    # Bonus for moving toward center
                    center = Position(
                        state.grid_size[0] // 2,
                        state.grid_size[1] // 2,
                        state.grid_size[2] // 2
                    )
                    for p in new_positions:
                        dist = abs(p.x - center.x) + abs(p.y - center.y) + abs(p.z - center.z)
                        score -= dist * 0.01  # Small bonus for center

                    if score > best_score:
                        best_score = score
                        best_dir = direction

                # Only move if it actually helps
                if best_dir and best_score > 0:
                    return MoveAction(ship.id, best_dir)

        return None

    def _get_reactive_move(self, state: GameState) -> Optional[MoveAction]:
        """Move damaged ships (standard evasion)."""
        for ship in state.my_ships:
            if ship.health < ship.size and ship.can_move:
                move_dir = self._find_safe_direction(ship, state)
                if move_dir:
                    return MoveAction(ship.id, move_dir)
        return None

    def _find_safe_direction(self, ship: Ship, state: GameState) -> Optional[Direction]:
        """Find safest direction to move."""
        danger_zone = set()
        for shot in state.enemy_shots_on_me[-10:]:
            danger_zone.add(shot)
            for adj in get_adjacent_positions(shot, state.grid_size):
                danger_zone.add(adj)

        best_direction = None
        best_score = -1000

        for direction in Direction:
            new_positions = [pos.move(direction) for pos in ship.positions]

            valid = all(
                self._is_valid_position(p, state.grid_size) and
                not any(p in other.positions for other in state.my_ships
                       if other.id != ship.id and not other.is_destroyed)
                for p in new_positions
            )

            if not valid:
                continue

            score = sum(10 if pos not in danger_zone else 0 for pos in new_positions)
            if score > best_score:
                best_score = score
                best_direction = direction

        return best_direction

    # ==================== OFFENSE: Ship Movement Prediction ====================

    def _predict_ship_movement(self, hit_pos: Position, state: GameState) -> List[Tuple[Position, float]]:
        """Predict where a ship at hit_pos might move."""
        if not self.config:
            return []

        grid_size = state.grid_size
        center = Position(grid_size[0] // 2, grid_size[1] // 2, grid_size[2] // 2)

        predictions: List[Tuple[Position, float]] = []

        for direction in Direction:
            new_pos = hit_pos.move(direction)

            if not self._is_valid_position(new_pos, grid_size):
                continue

            score = 1.0

            # Ships move toward center (more escape options)
            old_dist = abs(hit_pos.x - center.x) + abs(hit_pos.y - center.y) + abs(hit_pos.z - center.z)
            new_dist = abs(new_pos.x - center.x) + abs(new_pos.y - center.y) + abs(new_pos.z - center.z)
            if new_dist < old_dist:
                score += 0.5

            # Lower score if we already shot there
            if new_pos in self.fired_positions:
                score -= 0.8

            # Higher score if moving away from our recent shots
            for tracked in self.tracked_hits[-3:]:
                dist = (abs(new_pos.x - tracked.position.x) +
                       abs(new_pos.y - tracked.position.y) +
                       abs(new_pos.z - tracked.position.z))
                if dist > 2:
                    score += 0.3

            predictions.append((new_pos, score))

        predictions.sort(key=lambda x: x[1], reverse=True)
        return predictions

    def _get_smart_target(self, state: GameState) -> Optional[Position]:
        """Get next target using prediction-based priority."""

        # Priority 1: High-priority predicted positions
        while self.high_priority_targets:
            target = self.high_priority_targets.pop(0)
            if target not in self.fired_positions:
                return target

        # Priority 2: Adjacent to recent hits (hunt mode)
        for tracked in reversed(self.tracked_hits[-5:]):
            for adj in get_adjacent_positions(tracked.position, state.grid_size):
                if adj not in self.fired_positions and adj not in tracked.follow_up_fired:
                    tracked.follow_up_fired.add(adj)
                    return adj

        # Priority 3: Known hit cells we haven't fully explored
        for pos, status in state.known_cells.items():
            if status == CellStatus.HIT and pos not in self.fired_positions:
                for adj in get_adjacent_positions(pos, state.grid_size):
                    if adj not in self.fired_positions:
                        return adj

        # Priority 4: Checkerboard search
        while self.search_positions:
            target = self.search_positions.pop(0)
            if target not in self.fired_positions:
                return target

        # Priority 5: Random unknown
        unknown = [p for p in state.get_unknown_cells() if p not in self.fired_positions]
        if unknown:
            return random.choice(unknown)

        return None

    def _is_valid_position(self, pos: Position, grid_size: Tuple[int, int, int]) -> bool:
        """Check if position is within grid."""
        x_max, y_max, z_max = grid_size
        return 0 <= pos.x < x_max and 0 <= pos.y < y_max and 0 <= pos.z < z_max

    def on_turn_result(self, result: TurnResult) -> None:
        """Process results and update predictions."""
        # Track enemy shots for pattern learning
        for pos in result.incoming_hits:
            self.enemy_analysis.shots.append(pos)

        # Analyze enemy pattern periodically
        if len(self.enemy_analysis.shots) % 5 == 0:
            self._analyze_enemy_pattern()

        # Process our hits - predict where ships will move
        for fire_result in result.fire_results:
            if fire_result.hit:
                tracked = TrackedHit(
                    position=fire_result.target,
                    turn_hit=self.current_turn
                )

                if not fire_result.destroyed_ship and self.config:
                    # Ship not destroyed - it might move
                    dummy_state = GameState(
                        turn=self.current_turn,
                        grid_size=self.config.grid_size,
                        my_ships=[],
                        known_cells={},
                        my_shots=[],
                        enemy_shots_on_me=[],
                        actions_remaining=0,
                        enemy_ships_destroyed=[]
                    )
                    predictions = self._predict_ship_movement(fire_result.target, dummy_state)

                    for pos, _ in predictions[:4]:
                        if pos not in self.fired_positions:
                            self.high_priority_targets.append(pos)
                            tracked.predicted_moves.append(pos)

                    if predictions:
                        self.scan_targets.append(predictions[0][0])

                self.tracked_hits.append(tracked)
