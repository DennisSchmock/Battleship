"""Adaptive AI player that learns across multiple rounds."""
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict
import random

from .board import Board
from .ship import Ship, Orientation
from .player import Player


@dataclass
class AdaptiveHunterAI(Player):
    """
    AI that learns opponent patterns across multiple rounds.

    Inspired by the original Java R58 bot:
    - Tracks enemy shot patterns with heat maps
    - Places ships in "cold" areas (less frequently shot)
    - Tracks where enemy ships are found to shoot smarter
    - Adapts strategy based on win/loss ratio
    """

    # Persistent data across rounds
    enemy_shot_heatmap: List[List[float]] = field(default_factory=list)
    enemy_ship_heatmap: List[List[float]] = field(default_factory=list)
    rounds_played: int = 0
    wins: int = 0
    losses: int = 0

    # Per-game state
    _hunt_mode: bool = False
    _hunt_targets: List[Tuple[int, int]] = field(default_factory=list)
    _confirmed_hits: List[Tuple[int, int]] = field(default_factory=list)

    # Learning parameters - tuned for visible impact
    HEAT_INCREASE: float = 1.0
    HEAT_DECAY: float = 0.98  # Less decay = longer memory
    SHIP_HEAT_WEIGHT: float = 2.0  # How much to weight ship positions when shooting

    def __post_init__(self):
        """Initialize heat maps."""
        size = 10
        if not self.enemy_shot_heatmap:
            self.enemy_shot_heatmap = [[0.0] * size for _ in range(size)]
        if not self.enemy_ship_heatmap:
            self.enemy_ship_heatmap = [[0.0] * size for _ in range(size)]

    def reset(self) -> None:
        """Reset for a new game, but keep learned data."""
        self.board = Board()
        self.shots_fired = []
        self.hits = []
        self._hunt_mode = False
        self._hunt_targets = []
        self._confirmed_hits = []

    def start_new_round(self) -> None:
        """Called at the start of each round to decay old data."""
        # Decay heat maps so recent data is more important
        for r in range(len(self.enemy_shot_heatmap)):
            for c in range(len(self.enemy_shot_heatmap[0])):
                self.enemy_shot_heatmap[r][c] *= self.HEAT_DECAY
                self.enemy_ship_heatmap[r][c] *= self.HEAT_DECAY

    def record_round_result(self, won: bool, enemy_shots: List[Tuple[int, int]],
                           enemy_ship_positions: List[Tuple[int, int]]) -> None:
        """Record round outcome and learn from it."""
        self.rounds_played += 1
        if won:
            self.wins += 1
        else:
            self.losses += 1

        # Update enemy shot heatmap (where do they shoot before hitting?)
        for row, col in enemy_shots:
            if 0 <= row < len(self.enemy_shot_heatmap) and 0 <= col < len(self.enemy_shot_heatmap[0]):
                self.enemy_shot_heatmap[row][col] += self.HEAT_INCREASE

        # Update enemy ship heatmap (where do they place ships?)
        for row, col in enemy_ship_positions:
            if 0 <= row < len(self.enemy_ship_heatmap) and 0 <= col < len(self.enemy_ship_heatmap[0]):
                self.enemy_ship_heatmap[row][col] += self.HEAT_INCREASE

    def place_ships(self, ships: List[Ship]) -> None:
        """Place ships avoiding hot zones where enemy frequently shoots."""
        for ship in ships:
            best_placement = None
            best_score = float('inf')

            # Try many random placements and pick the "coldest" one
            for _ in range(200):
                row = random.randint(0, self.board.size - 1)
                col = random.randint(0, self.board.size - 1)
                orientation = random.choice([Orientation.HORIZONTAL, Orientation.VERTICAL])

                if self.board.can_place_ship(ship, row, col, orientation):
                    # Calculate heat score for this placement
                    score = self._calculate_placement_heat(ship, row, col, orientation)
                    if score < best_score:
                        best_score = score
                        best_placement = (row, col, orientation)

            if best_placement:
                row, col, orientation = best_placement
                self.board.place_ship(ship, row, col, orientation)
            else:
                # Fallback to random placement
                self._random_place_ship(ship)

    def _calculate_placement_heat(self, ship: Ship, row: int, col: int,
                                  orientation: Orientation) -> float:
        """Calculate total heat for a potential ship placement."""
        total_heat = 0.0
        checkerboard_cells = 0
        dr, dc = (0, 1) if orientation == Orientation.HORIZONTAL else (1, 0)

        for i in range(ship.size):
            r, c = row + dr * i, col + dc * i
            if 0 <= r < len(self.enemy_shot_heatmap) and 0 <= c < len(self.enemy_shot_heatmap[0]):
                # Add heat from enemy shot patterns
                total_heat += self.enemy_shot_heatmap[r][c]
                # Penalize checkerboard cells (enemy shoots there first)
                if (r + c) % 2 == 0:
                    checkerboard_cells += 1

        # After learning, heavily penalize checkerboard placements
        if self.rounds_played >= 3:
            total_heat += checkerboard_cells * 5.0

        return total_heat

    def _random_place_ship(self, ship: Ship) -> None:
        """Fallback random ship placement."""
        for _ in range(1000):
            row = random.randint(0, self.board.size - 1)
            col = random.randint(0, self.board.size - 1)
            orientation = random.choice([Orientation.HORIZONTAL, Orientation.VERTICAL])
            if self.board.place_ship(ship, row, col, orientation):
                return
        raise RuntimeError(f"Could not place ship: {ship.name}")

    def get_shot(self, opponent_board_state: dict) -> Tuple[int, int]:
        """Smart shot selection using learned enemy ship positions."""
        shots_received = set(tuple(s) for s in opponent_board_state.get("shots_received", []))
        size = opponent_board_state.get("size", 10)

        # Filter hunt targets
        self._hunt_targets = [
            t for t in self._hunt_targets
            if t not in shots_received and 0 <= t[0] < size and 0 <= t[1] < size
        ]

        # Hunt mode: pursue confirmed hits (highest priority)
        if self._hunt_targets:
            return self._hunt_targets.pop(0)

        # Build list of candidates with scores
        candidates = []
        for r in range(size):
            for c in range(size):
                if (r, c) not in shots_received:
                    # Base score from checkerboard pattern
                    base_score = 2.0 if (r + c) % 2 == 0 else 1.0
                    # Add learned ship position heat
                    heat_score = self.enemy_ship_heatmap[r][c]
                    candidates.append((r, c, base_score, heat_score))

        if not candidates:
            raise RuntimeError("No available shots")

        # GREEDY EXPLOITATION: After learning, prioritize high-heat cells
        if self.rounds_played >= 5:
            # Sort by heat score (descending), then by checkerboard
            candidates.sort(key=lambda x: (x[3], x[2]), reverse=True)

            # Pick from top 20% hottest cells (minimum 5 cells)
            top_n = max(5, len(candidates) // 5)
            top_candidates = candidates[:top_n]

            # Among top candidates, prefer checkerboard cells
            checkerboard_top = [c for c in top_candidates if c[2] > 1.5]
            if checkerboard_top:
                choice = random.choice(checkerboard_top)
            else:
                choice = random.choice(top_candidates)
            return (choice[0], choice[1])
        else:
            # Early game: use weighted random to explore
            weights = [c[2] * (1.0 + c[3] * self.SHIP_HEAT_WEIGHT) for c in candidates]
            total = sum(weights)
            if total > 0:
                weights = [w / total for w in weights]
                idx = random.choices(range(len(candidates)), weights=weights, k=1)[0]
                return (candidates[idx][0], candidates[idx][1])
            choice = random.choice(candidates)
            return (choice[0], choice[1])

    def record_shot_result(self, row: int, col: int, is_hit: bool,
                          sunk_ship: Optional[Ship] = None) -> None:
        """Record shot result and update hunting state."""
        self.shots_fired.append((row, col))
        if is_hit:
            self.hits.append((row, col))
            self._confirmed_hits.append((row, col))

            if sunk_ship:
                # Remove sunk ship positions from hunt targets
                sunk_coords = set(sunk_ship.get_coordinates())
                self._hunt_targets = [t for t in self._hunt_targets if t not in sunk_coords]
                self._confirmed_hits = [h for h in self._confirmed_hits if h not in sunk_coords]
            else:
                # Add adjacent cells to hunt targets
                self._add_adjacent_targets(row, col)

    def _add_adjacent_targets(self, row: int, col: int) -> None:
        """Add adjacent cells to hunt targets, prioritizing direction if multiple hits."""
        shots_set = set(self.shots_fired)

        # Check for line of hits to prioritize direction
        directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        prioritized = []

        for dr, dc in directions:
            # Check if there's a hit in this direction
            check_r, check_c = row + dr, col + dc
            if (check_r, check_c) in self._confirmed_hits:
                # Prioritize continuing in this direction
                continue_r, continue_c = row - dr, col - dc
                if (continue_r, continue_c) not in shots_set:
                    prioritized.append((continue_r, continue_c))
                # Also try the other end
                other_r, other_c = check_r + dr, check_c + dc
                if (other_r, other_c) not in shots_set:
                    prioritized.append((other_r, other_c))

        # Add prioritized targets first
        for target in prioritized:
            if target not in self._hunt_targets and 0 <= target[0] < 10 and 0 <= target[1] < 10:
                self._hunt_targets.insert(0, target)

        # Then add all adjacent cells
        for dr, dc in directions:
            new_row, new_col = row + dr, col + dc
            if 0 <= new_row < 10 and 0 <= new_col < 10:
                if (new_row, new_col) not in shots_set and (new_row, new_col) not in self._hunt_targets:
                    self._hunt_targets.append((new_row, new_col))

    @property
    def win_rate(self) -> float:
        """Calculate current win rate."""
        if self.rounds_played == 0:
            return 0.0
        return self.wins / self.rounds_played

    def get_stats(self) -> dict:
        """Get learning statistics."""
        return {
            "rounds_played": self.rounds_played,
            "wins": self.wins,
            "losses": self.losses,
            "win_rate": round(self.win_rate * 100, 1),
        }
