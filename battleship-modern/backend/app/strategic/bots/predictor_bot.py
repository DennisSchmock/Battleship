"""PredictorBot - A smart bot that predicts enemy ship movements AND learns attack patterns.

Three-pronged strategy:
1. INTEL: Use scans strategically to find ships before firing
2. OFFENSE: When you hit a ship, predict where it will move and follow up
3. DEFENSE: Learn enemy's shooting pattern and move ships BEFORE they get hit
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
    hunt_direction: Optional[Direction] = None


class PredictorBot(SpaceBot):
    """
    A bot that uses scans for intelligence, predicts movements, and learns patterns.

    INTEL Strategy (NEW):
    - Early game: Scan to find ships before blindly firing
    - Scan reveals 3x3x3 = 27 cells at once - much more efficient than firing
    - Use scan data to locate ships, THEN fire at confirmed positions
    - Re-scan areas where ships might have moved

    OFFENSE Strategy:
    - Fire at cells where scans revealed ships
    - When hitting a ship, predict where it will move (6 directions)
    - Scan predicted areas to re-acquire target

    DEFENSE Strategy:
    - Analyze enemy's shooting pattern (checkerboard? hunt mode?)
    - Predict where enemy will shoot next
    - Move ships BEFORE they get hit (proactive evasion)
    """

    def __init__(self):
        self.config: Optional[GameConfig] = None
        self.search_positions: List[Position] = []
        self.fired_positions: Set[Position] = set()
        self.scanned_centers: Set[Position] = set()  # Track where we've scanned
        self.current_turn: int = 0

        # INTEL: Tracking scan data
        self.revealed_ships: Set[Position] = set()  # Positions where we found ships
        self.scan_priority_targets: List[Position] = []  # Where to scan next

        # OFFENSE: Prediction tracking
        self.tracked_hits: List[TrackedHit] = []
        self.high_priority_targets: List[Position] = []

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
        self.scanned_centers = set()
        self.revealed_ships = set()
        self.tracked_hits = []
        self.high_priority_targets = []
        self.current_turn = 0
        self.enemy_analysis = EnemyPatternAnalysis()

        # Create strategic scan positions LAST (after resetting everything)
        self._init_scan_positions(config.grid_size)

    def _init_scan_positions(self, grid_size: Tuple[int, int, int]) -> None:
        """Create optimal scan positions to cover the grid efficiently."""
        x_max, y_max, z_max = grid_size

        # Scans cover 3x3x3, so space them 3 apart for efficient coverage
        self.scan_priority_targets = []
        for x in range(1, x_max, 3):
            for y in range(1, y_max, 3):
                for z in range(1, z_max, 3):
                    self.scan_priority_targets.append(Position(x, y, z))

        # Randomize to avoid predictable patterns
        random.shuffle(self.scan_priority_targets)

    def place_ships(self, config: GameConfig) -> List[Tuple[Position, Direction]]:
        """Place ships spread out."""
        return random_placement(config)

    def get_actions(self, state: GameState) -> List[Action]:
        """Decide actions with intelligent scan usage."""
        self.current_turn = state.turn
        actions = []

        # Update revealed ships from scan results
        self._update_intel(state)

        # === Decide action allocation based on game state ===
        # Early game: More scans to gather intel
        # Mid game: Mix of scans and fires
        # Late game: More fires to finish off ships

        unknown_ratio = len(state.get_unknown_cells()) / (
            state.grid_size[0] * state.grid_size[1] * state.grid_size[2]
        )

        # Determine action split
        if unknown_ratio > 0.7:
            # Early game: 1-2 scans, rest fires
            desired_scans = 2 if not self.revealed_ships else 1
        elif unknown_ratio > 0.4:
            # Mid game: 1 scan if we have targets, else more fires
            desired_scans = 1 if not self.high_priority_targets else 0
        else:
            # Late game: Focus on finishing
            desired_scans = 0

        actions_used = 0

        # === DEFENSE: Proactive/reactive movement ===
        predicted_danger = self._predict_enemy_next_shots(state)
        move_action = self._get_best_move(state, predicted_danger)
        if move_action:
            actions.append(move_action)
            actions_used += 1

        # === INTEL: Strategic scanning ===
        scans_done = 0
        while scans_done < desired_scans and actions_used < state.actions_remaining:
            scan_pos = self._get_scan_target(state)
            if scan_pos:
                actions.append(ScanAction(scan_pos))
                self.scanned_centers.add(scan_pos)
                actions_used += 1
                scans_done += 1
            else:
                break

        # === OFFENSE: Fire at targets ===
        while actions_used < state.actions_remaining:
            target = self._get_fire_target(state)
            if target:
                actions.append(FireAction(target))
                self.fired_positions.add(target)
                actions_used += 1
            else:
                break

        return actions

    def _update_intel(self, state: GameState) -> None:
        """Update our intelligence from scan results."""
        # Find cells that scans revealed as having ships
        for pos, status in state.known_cells.items():
            if status == CellStatus.HIT:
                # This is a confirmed ship position
                if pos not in self.fired_positions:
                    self.revealed_ships.add(pos)
            elif status == CellStatus.MISS or status == CellStatus.EMPTY:
                # Remove from revealed ships if we now know it's empty
                self.revealed_ships.discard(pos)

    def _get_scan_target(self, state: GameState) -> Optional[Position]:
        """Get the best position to scan."""
        # Priority 1: Scan near recent hits to find moved ships
        for tracked in reversed(self.tracked_hits[-3:]):
            if not tracked.predicted_moves:
                continue
            for pred_pos in tracked.predicted_moves:
                if pred_pos not in self.scanned_centers:
                    return pred_pos

        # Priority 2: Scan unexplored areas
        while self.scan_priority_targets:
            pos = self.scan_priority_targets.pop(0)
            # Check if this scan would reveal new cells
            would_reveal_new = False
            for dx in range(-1, 2):
                for dy in range(-1, 2):
                    for dz in range(-1, 2):
                        check = Position(pos.x + dx, pos.y + dy, pos.z + dz)
                        if self._is_valid_position(check, state.grid_size):
                            if state.get_cell_status(check) == CellStatus.UNKNOWN:
                                would_reveal_new = True
                                break

            if would_reveal_new and pos not in self.scanned_centers:
                return pos

        # Priority 3: Re-scan areas where ships were but might have moved
        for hit_pos in list(self.revealed_ships)[:3]:
            # Scan adjacent to where we know ships were
            for direction in Direction:
                scan_pos = hit_pos.move(direction)
                if (self._is_valid_position(scan_pos, state.grid_size) and
                    scan_pos not in self.scanned_centers):
                    return scan_pos

        return None

    def _get_fire_target(self, state: GameState) -> Optional[Position]:
        """Get the best position to fire at."""
        # Priority 1: Fire at positions revealed by scans as having ships
        for pos in list(self.revealed_ships):
            if pos not in self.fired_positions:
                self.revealed_ships.discard(pos)
                return pos

        # Priority 2: High-priority predicted positions (where ships moved)
        while self.high_priority_targets:
            target = self.high_priority_targets.pop(0)
            if target not in self.fired_positions:
                return target

        # Priority 3: Adjacent to recent hits (hunt mode)
        for tracked in reversed(self.tracked_hits[-5:]):
            for adj in get_adjacent_positions(tracked.position, state.grid_size):
                if adj not in self.fired_positions and adj not in tracked.follow_up_fired:
                    tracked.follow_up_fired.add(adj)
                    return adj

        # Priority 4: Known hits we haven't explored
        for pos, status in state.known_cells.items():
            if status == CellStatus.HIT:
                for adj in get_adjacent_positions(pos, state.grid_size):
                    if adj not in self.fired_positions:
                        return adj

        # Priority 5: Checkerboard search (fallback)
        while self.search_positions:
            target = self.search_positions.pop(0)
            if target not in self.fired_positions:
                return target

        # Priority 6: Random unknown
        unknown = [p for p in state.get_unknown_cells() if p not in self.fired_positions]
        if unknown:
            return random.choice(unknown)

        return None

    def _get_best_move(self, state: GameState, predicted_danger: Set[Position]) -> Optional[MoveAction]:
        """Get the best move action (proactive or reactive)."""
        # First try proactive move (avoid predicted danger)
        if predicted_danger:
            for ship in state.my_ships:
                if not ship.can_move or ship.is_destroyed:
                    continue

                danger_count = sum(1 for pos in ship.positions if pos in predicted_danger)
                if danger_count >= 1:
                    move_dir = self._find_escape_direction(ship, state, predicted_danger)
                    if move_dir:
                        return MoveAction(ship.id, move_dir)

        # Then try reactive move (damaged ships)
        for ship in state.my_ships:
            if ship.health < ship.size and ship.can_move:
                move_dir = self._find_safe_direction(ship, state)
                if move_dir:
                    return MoveAction(ship.id, move_dir)

        return None

    def _find_escape_direction(self, ship: Ship, state: GameState,
                               danger: Set[Position]) -> Optional[Direction]:
        """Find direction to escape predicted danger."""
        best_dir = None
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

            old_danger = sum(1 for p in ship.positions if p in danger)
            new_danger = sum(1 for p in new_positions if p in danger)
            score = old_danger - new_danger

            if score > best_score:
                best_score = score
                best_dir = direction

        return best_dir if best_score > 0 else None

    def _find_safe_direction(self, ship: Ship, state: GameState) -> Optional[Direction]:
        """Find safest direction for damaged ship."""
        danger_zone = set()
        for shot in state.enemy_shots_on_me[-10:]:
            danger_zone.add(shot)
            for adj in get_adjacent_positions(shot, state.grid_size):
                danger_zone.add(adj)

        best_dir = None
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
                best_dir = direction

        return best_dir

    # ==================== Enemy Pattern Learning ====================

    def _analyze_enemy_pattern(self) -> None:
        """Analyze enemy shooting patterns."""
        shots = self.enemy_analysis.shots
        if len(shots) < 5:
            return

        cb_count = sum(1 for s in shots if (s.x + s.y + s.z) % 2 == 0)
        self.enemy_analysis.uses_checkerboard = cb_count > len(shots) * 0.65

        hunt_sequences = 0
        dir_counts: Dict[Direction, int] = defaultdict(int)

        for i in range(1, len(shots)):
            diff = (shots[i].x - shots[i-1].x, shots[i].y - shots[i-1].y, shots[i].z - shots[i-1].z)
            if abs(diff[0]) + abs(diff[1]) + abs(diff[2]) == 1:
                hunt_sequences += 1
                for d in Direction:
                    if d.value == diff:
                        dir_counts[d] += 1

        self.enemy_analysis.tends_to_hunt = hunt_sequences > len(shots) * 0.25
        if dir_counts:
            self.enemy_analysis.hunt_direction = max(dir_counts, key=dir_counts.get)

    def _predict_enemy_next_shots(self, state: GameState) -> Set[Position]:
        """Predict where enemy will shoot next."""
        predicted = set()
        if not self.config:
            return predicted

        shots = self.enemy_analysis.shots
        grid_size = state.grid_size

        # If they hunt, predict adjacent to recent hits on us
        if self.enemy_analysis.tends_to_hunt:
            for shot in state.enemy_shots_on_me[-5:]:
                for ship in state.my_ships:
                    for ship_pos in ship.positions:
                        if (abs(shot.x - ship_pos.x) + abs(shot.y - ship_pos.y) +
                            abs(shot.z - ship_pos.z)) <= 1:
                            for adj in get_adjacent_positions(shot, grid_size):
                                predicted.add(adj)
                            if self.enemy_analysis.hunt_direction:
                                next_pos = shot.move(self.enemy_analysis.hunt_direction)
                                if self._is_valid_position(next_pos, grid_size):
                                    predicted.add(next_pos)

        # Predict adjacent to their last shots
        for shot in shots[-3:]:
            for adj in get_adjacent_positions(shot, grid_size):
                predicted.add(adj)

        return predicted

    def _is_valid_position(self, pos: Position, grid_size: Tuple[int, int, int]) -> bool:
        x_max, y_max, z_max = grid_size
        return 0 <= pos.x < x_max and 0 <= pos.y < y_max and 0 <= pos.z < z_max

    def on_turn_result(self, result: TurnResult) -> None:
        """Process results and update tracking."""
        # Track enemy shots
        for pos in result.incoming_hits:
            self.enemy_analysis.shots.append(pos)

        if len(self.enemy_analysis.shots) % 5 == 0:
            self._analyze_enemy_pattern()

        # Process scan results - add revealed ship positions
        for scan_result in result.scan_results:
            for pos, status in scan_result.revealed.items():
                if status == CellStatus.HIT:
                    self.revealed_ships.add(pos)

        # Process fire results
        for fire_result in result.fire_results:
            if fire_result.hit:
                tracked = TrackedHit(
                    position=fire_result.target,
                    turn_hit=self.current_turn
                )

                if not fire_result.destroyed_ship and self.config:
                    # Ship not destroyed - predict where it might move
                    for direction in Direction:
                        pred_pos = fire_result.target.move(direction)
                        if self._is_valid_position(pred_pos, self.config.grid_size):
                            if pred_pos not in self.fired_positions:
                                self.high_priority_targets.append(pred_pos)
                                tracked.predicted_moves.append(pred_pos)

                    # Queue scan at hit position to find moved ship
                    if fire_result.target not in self.scanned_centers:
                        self.scan_priority_targets.insert(0, fire_result.target)

                self.tracked_hits.append(tracked)
