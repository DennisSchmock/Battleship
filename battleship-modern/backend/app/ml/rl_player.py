"""RL-based player that uses a trained model."""
import numpy as np
from pathlib import Path
from typing import Tuple, List, Optional
import random

from ..game.player import Player
from ..game.board import Board
from ..game.ship import Ship, Orientation


class RLPlayer(Player):
    """
    A Battleship player powered by a trained RL model.
    Uses the observation format from BattleshipEnv.
    """

    def __init__(self, name: str, model_path: Optional[str] = None):
        super().__init__(name)
        self.model = None
        self.model_path = model_path
        self._observation = None

        if model_path and Path(model_path).exists():
            self._load_model(model_path)

    def _load_model(self, model_path: str) -> None:
        """Load a trained model from disk."""
        try:
            from stable_baselines3 import DQN
            self.model = DQN.load(model_path)
            print(f"Loaded model from {model_path}")
        except Exception as e:
            print(f"Could not load model: {e}")
            self.model = None

    def reset(self) -> None:
        """Reset player for a new game."""
        super().reset()
        self._observation = np.zeros((10, 10), dtype=np.int8)

    def place_ships(self, ships: List[Ship]) -> None:
        """Place ships randomly (could be improved with learned placement)."""
        for ship in ships:
            placed = False
            attempts = 0

            while not placed and attempts < 1000:
                row = random.randint(0, self.board.size - 1)
                col = random.randint(0, self.board.size - 1)
                orientation = random.choice([Orientation.HORIZONTAL, Orientation.VERTICAL])

                placed = self.board.place_ship(ship, row, col, orientation)
                attempts += 1

            if not placed:
                raise RuntimeError(f"Could not place ship: {ship.name}")

    def get_shot(self, opponent_board_state: dict) -> Tuple[int, int]:
        """Use the RL model to determine the next shot."""
        if self._observation is None:
            self._observation = np.zeros((10, 10), dtype=np.int8)

        if self.model is None:
            # Fallback to random if no model loaded
            return self._get_random_shot(opponent_board_state)

        # Get action from model
        action, _ = self.model.predict(self._observation, deterministic=True)

        row = int(action) // 10
        col = int(action) % 10

        # Check if action is valid
        shots_received = set(tuple(s) for s in opponent_board_state.get("shots_received", []))
        if (row, col) in shots_received:
            # Invalid action - fallback to random valid shot
            return self._get_random_shot(opponent_board_state)

        return (row, col)

    def _get_random_shot(self, opponent_board_state: dict) -> Tuple[int, int]:
        """Fallback random shot selection."""
        shots_received = set(tuple(s) for s in opponent_board_state.get("shots_received", []))
        size = opponent_board_state.get("size", 10)

        available = [
            (r, c) for r in range(size) for c in range(size)
            if (r, c) not in shots_received
        ]

        if not available:
            raise RuntimeError("No available shots")

        return random.choice(available)

    def record_shot_result(self, row: int, col: int, is_hit: bool, sunk_ship: Optional[Ship] = None) -> None:
        """Update internal observation based on shot result."""
        super().record_shot_result(row, col, is_hit, sunk_ship)

        if self._observation is None:
            self._observation = np.zeros((10, 10), dtype=np.int8)

        if sunk_ship:
            # Mark all cells of sunk ship
            for r, c in sunk_ship.get_coordinates():
                self._observation[r, c] = 3  # Sunk
        elif is_hit:
            self._observation[row, col] = 2  # Hit
        else:
            self._observation[row, col] = 1  # Miss
