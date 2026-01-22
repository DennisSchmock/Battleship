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

    # Learning parameters
    HEAT_INCREASE: float = 1.0
    HEAT_DECAY: float = 0.95  # Decay old data slightly each round

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
            for _ in range(100):
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
        dr, dc = (0, 1) if orientation == Orientation.HORIZONTAL else (1, 0)

        for i in range(ship.size):
            r, c = row + dr * i, col + dc * i
            if 0 <= r < len(self.enemy_shot_heatmap) and 0 <= c < len(self.enemy_shot_heatmap[0]):
                total_heat += self.enemy_shot_heatmap[r][c]

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

        # Hunt mode: pursue confirmed hits
        if self._hunt_targets:
            return self._hunt_targets.pop(0)

        # Otherwise, use weighted selection based on enemy ship heatmap
        candidates = []
        weights = []

        # Checkerboard pattern with heat-weighted selection
        for r in range(size):
            for c in range(size):
                if (r, c) not in shots_received:
                    # Prefer checkerboard positions
                    base_weight = 2.0 if (r + c) % 2 == 0 else 1.0
                    # Add weight from learned enemy ship positions
                    heat_weight = 1.0 + self.enemy_ship_heatmap[r][c] * 0.5
                    candidates.append((r, c))
                    weights.append(base_weight * heat_weight)

        if candidates:
            # Weighted random selection
            total = sum(weights)
            if total > 0:
                weights = [w / total for w in weights]
                return random.choices(candidates, weights=weights, k=1)[0]
            return random.choice(candidates)

        raise RuntimeError("No available shots")

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
