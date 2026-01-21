"""Gymnasium environment for Battleship RL training."""
import gymnasium as gym
from gymnasium import spaces
import numpy as np
from typing import Optional, Tuple, Any

from ..game.board import Board, CellState
from ..game.ship import Ship, Orientation
import random


class BattleshipEnv(gym.Env):
    """
    Gymnasium environment for training a Battleship agent.

    The agent learns to efficiently sink ships on the opponent's board.

    Observation space:
        - 10x10 grid with values:
            - 0: Unknown (not yet shot)
            - 1: Miss
            - 2: Hit
            - 3: Sunk

    Action space:
        - Discrete(100): Position 0-99 representing row*10 + col

    Rewards:
        - Hit: +1
        - Miss: -0.1
        - Sunk ship: +5
        - Win (all ships sunk): +10
        - Invalid move (already shot): -1
    """

    metadata = {"render_modes": ["human", "ansi"]}

    def __init__(self, render_mode: Optional[str] = None):
        super().__init__()

        self.render_mode = render_mode
        self.board_size = 10

        # Observation: 10x10 grid
        self.observation_space = spaces.Box(
            low=0, high=3,
            shape=(self.board_size, self.board_size),
            dtype=np.int8
        )

        # Action: single cell (0-99)
        self.action_space = spaces.Discrete(self.board_size * self.board_size)

        # Game state
        self._opponent_board: Optional[Board] = None
        self._observation: Optional[np.ndarray] = None
        self._shots_fired: set = set()
        self._total_ship_cells: int = 0
        self._hits: int = 0

    def _place_random_ships(self, board: Board) -> None:
        """Place ships randomly on the board."""
        ships = Ship.create_standard_fleet()

        for ship in ships:
            placed = False
            attempts = 0

            while not placed and attempts < 1000:
                row = random.randint(0, self.board_size - 1)
                col = random.randint(0, self.board_size - 1)
                orientation = random.choice([Orientation.HORIZONTAL, Orientation.VERTICAL])

                placed = board.place_ship(ship, row, col, orientation)
                attempts += 1

            if not placed:
                raise RuntimeError(f"Could not place ship: {ship.name}")

        # Count total ship cells
        self._total_ship_cells = sum(ship.size for ship in ships)

    def reset(
        self,
        seed: Optional[int] = None,
        options: Optional[dict] = None
    ) -> Tuple[np.ndarray, dict]:
        """Reset the environment for a new episode."""
        super().reset(seed=seed)

        # Create new board with random ship placement
        self._opponent_board = Board(size=self.board_size)
        self._place_random_ships(self._opponent_board)

        # Initialize observation (all unknown)
        self._observation = np.zeros((self.board_size, self.board_size), dtype=np.int8)
        self._shots_fired = set()
        self._hits = 0

        info = {"ships_remaining": len(self._opponent_board.ships)}

        return self._observation.copy(), info

    def step(self, action: int) -> Tuple[np.ndarray, float, bool, bool, dict]:
        """
        Execute one action.

        Returns:
            observation, reward, terminated, truncated, info
        """
        row = action // self.board_size
        col = action % self.board_size

        # Check if already shot
        if (row, col) in self._shots_fired:
            # Invalid move - heavy penalty
            return self._observation.copy(), -1.0, False, False, {"invalid_move": True}

        self._shots_fired.add((row, col))

        # Process the shot
        is_hit, sunk_ship = self._opponent_board.receive_shot(row, col)

        # Calculate reward
        reward = 0.0
        info = {
            "hit": is_hit,
            "sunk": sunk_ship.name if sunk_ship else None,
            "position": (row, col),
        }

        if is_hit:
            self._hits += 1
            reward = 1.0

            if sunk_ship:
                # Bonus for sinking a ship
                reward += 5.0
                # Update observation with sunk markers
                for r, c in sunk_ship.get_coordinates():
                    self._observation[r, c] = 3  # Sunk
                info["ship_sunk"] = sunk_ship.name
            else:
                self._observation[row, col] = 2  # Hit
        else:
            reward = -0.1  # Small penalty for miss
            self._observation[row, col] = 1  # Miss

        # Check if game is over
        terminated = self._opponent_board.all_ships_sunk
        if terminated:
            reward += 10.0  # Win bonus
            info["won"] = True
            info["total_shots"] = len(self._shots_fired)
            info["accuracy"] = self._hits / len(self._shots_fired)

        info["ships_remaining"] = len(self._opponent_board.remaining_ships)

        return self._observation.copy(), reward, terminated, False, info

    def render(self) -> Optional[str]:
        """Render the current state."""
        if self.render_mode == "ansi" or self.render_mode == "human":
            symbols = {0: "·", 1: "○", 2: "●", 3: "X"}
            lines = ["  " + " ".join(str(i) for i in range(self.board_size))]

            for row in range(self.board_size):
                row_str = f"{row} "
                for col in range(self.board_size):
                    row_str += symbols[self._observation[row, col]] + " "
                lines.append(row_str)

            output = "\n".join(lines)

            if self.render_mode == "human":
                print(output)

            return output

        return None

    def get_valid_actions(self) -> np.ndarray:
        """Get mask of valid actions (positions not yet shot)."""
        mask = np.ones(self.board_size * self.board_size, dtype=np.int8)

        for row, col in self._shots_fired:
            mask[row * self.board_size + col] = 0

        return mask


class BattleshipSelfPlayEnv(BattleshipEnv):
    """
    Extended environment for self-play training.
    Two agents take turns, learning both offense and defense.
    """

    def __init__(self, render_mode: Optional[str] = None):
        super().__init__(render_mode)

        # Extended observation: own board + opponent board
        self.observation_space = spaces.Dict({
            "own_board": spaces.Box(low=0, high=3, shape=(10, 10), dtype=np.int8),
            "opponent_board": spaces.Box(low=0, high=3, shape=(10, 10), dtype=np.int8),
            "valid_actions": spaces.Box(low=0, high=1, shape=(100,), dtype=np.int8),
        })

        self._own_board: Optional[Board] = None
        self._own_observation: Optional[np.ndarray] = None

    def reset(
        self,
        seed: Optional[int] = None,
        options: Optional[dict] = None
    ) -> Tuple[dict, dict]:
        """Reset for self-play."""
        super().reset(seed=seed, options=options)

        # Create own board too
        self._own_board = Board(size=self.board_size)
        self._place_random_ships(self._own_board)
        self._own_observation = np.zeros((self.board_size, self.board_size), dtype=np.int8)

        obs = {
            "own_board": self._own_observation.copy(),
            "opponent_board": self._observation.copy(),
            "valid_actions": self.get_valid_actions(),
        }

        return obs, {}

    def step(self, action: int) -> Tuple[dict, float, bool, bool, dict]:
        """Execute action in self-play mode."""
        obs, reward, terminated, truncated, info = super().step(action)

        dict_obs = {
            "own_board": self._own_observation.copy(),
            "opponent_board": obs,
            "valid_actions": self.get_valid_actions(),
        }

        return dict_obs, reward, terminated, truncated, info
