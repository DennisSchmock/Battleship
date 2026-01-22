"""3D Gymnasium environment for SpaceBattleship RL training."""
import gymnasium as gym
from gymnasium import spaces
import numpy as np
from typing import Tuple, Optional, Dict, Any

from ..game.board3d import Board3D, CellState3D
from ..game.ship3d import Ship3D


class SpaceBattleshipEnv(gym.Env):
    """
    3D SpaceBattleship environment for Reinforcement Learning.

    Observation space: 12x12x8 grid with values:
        0 = unknown (not yet shot)
        1 = miss
        2 = hit
        3 = sunk

    Action space: Discrete(12*12*8 = 1152) - each cell is an action

    Rewards:
        - Hit: +1
        - Miss: -0.1
        - Sink ship: +5
        - Win (all ships sunk): +20
        - Invalid shot (already shot): -1 and action masked
    """

    metadata = {"render_modes": ["human", "ansi"]}

    def __init__(self,
                 size_x: int = 12,
                 size_y: int = 12,
                 size_z: int = 8,
                 render_mode: Optional[str] = None):
        super().__init__()

        self.size_x = size_x
        self.size_y = size_y
        self.size_z = size_z
        self.total_cells = size_x * size_y * size_z
        self.render_mode = render_mode

        # Observation: 3D grid with cell states (0-3)
        self.observation_space = spaces.Box(
            low=0,
            high=3,
            shape=(size_x, size_y, size_z),
            dtype=np.int8
        )

        # Action: which cell to shoot (flattened index)
        self.action_space = spaces.Discrete(self.total_cells)

        self.board: Optional[Board3D] = None
        self.total_ship_cells: int = 0
        self.shots_taken: int = 0

    def _get_obs(self) -> np.ndarray:
        """Convert board state to observation."""
        obs = np.zeros((self.size_x, self.size_y, self.size_z), dtype=np.int8)

        for x in range(self.size_x):
            for y in range(self.size_y):
                for z in range(self.size_z):
                    state = self.board.get_cell_state(x, y, z)
                    if state == CellState3D.MISS:
                        obs[x, y, z] = 1
                    elif state == CellState3D.HIT:
                        obs[x, y, z] = 2
                    elif state == CellState3D.SUNK:
                        obs[x, y, z] = 3
                    # EMPTY and SHIP both appear as 0 (unknown)

        return obs

    def _get_info(self) -> Dict[str, Any]:
        """Get additional info about the game state."""
        ships_sunk = sum(1 for ship in self.board.ships if ship.is_sunk)
        total_ships = len(self.board.ships)
        hits = sum(1 for ship in self.board.ships for _ in ship.hits)

        return {
            "ships_sunk": ships_sunk,
            "total_ships": total_ships,
            "ships_remaining": total_ships - ships_sunk,
            "total_shots": self.shots_taken,
            "hits": hits,
            "accuracy": hits / self.shots_taken if self.shots_taken > 0 else 0,
            "won": self.board.all_ships_sunk,
        }

    def _action_to_coords(self, action: int) -> Tuple[int, int, int]:
        """Convert flattened action index to 3D coordinates."""
        z = action % self.size_z
        remainder = action // self.size_z
        y = remainder % self.size_y
        x = remainder // self.size_y
        return (x, y, z)

    def _coords_to_action(self, x: int, y: int, z: int) -> int:
        """Convert 3D coordinates to flattened action index."""
        return x * self.size_y * self.size_z + y * self.size_z + z

    def reset(self, seed: Optional[int] = None, options: Optional[dict] = None) -> Tuple[np.ndarray, dict]:
        """Reset the environment for a new game."""
        super().reset(seed=seed)

        self.board = Board3D(self.size_x, self.size_y, self.size_z)
        self.shots_taken = 0

        # Place space fleet randomly
        fleet = Ship3D.create_space_fleet()
        self.total_ship_cells = sum(ship.size for ship in fleet)

        for ship in fleet:
            if not self.board.place_ship_randomly(ship):
                # Retry with new board if placement fails
                return self.reset(seed=seed, options=options)

        return self._get_obs(), self._get_info()

    def step(self, action: int) -> Tuple[np.ndarray, float, bool, bool, dict]:
        """
        Take a shot at the specified cell.

        Returns: (observation, reward, terminated, truncated, info)
        """
        x, y, z = self._action_to_coords(action)

        # Check if already shot
        if (x, y, z) in self.board.shots_received:
            # Invalid action - penalize and return current state
            return self._get_obs(), -1.0, False, False, self._get_info()

        self.shots_taken += 1

        # Take the shot
        is_hit, sunk_ship = self.board.receive_shot(x, y, z)

        # Calculate reward
        if sunk_ship:
            reward = 5.0  # Ship destroyed
        elif is_hit:
            reward = 1.0  # Hit
        else:
            reward = -0.1  # Miss

        # Check if game is won
        terminated = self.board.all_ships_sunk
        if terminated:
            reward += 20.0  # Win bonus

        # Truncate if too many shots (shouldn't happen normally)
        truncated = self.shots_taken >= self.total_cells

        return self._get_obs(), reward, terminated, truncated, self._get_info()

    def get_valid_actions(self) -> np.ndarray:
        """Get mask of valid actions (cells not yet shot)."""
        mask = np.ones(self.total_cells, dtype=np.int8)
        for x, y, z in self.board.shots_received:
            action = self._coords_to_action(x, y, z)
            mask[action] = 0
        return mask

    def render(self) -> Optional[str]:
        """Render the current state."""
        if self.render_mode == "ansi":
            return self._render_ansi()
        elif self.render_mode == "human":
            print(self._render_ansi())
        return None

    def _render_ansi(self) -> str:
        """Render as ASCII art (showing one layer at a time)."""
        lines = []
        lines.append(f"=== SpaceBattleship ===")
        lines.append(f"Grid: {self.size_x}x{self.size_y}x{self.size_z}")
        lines.append(f"Shots: {self.shots_taken}, Ships remaining: {len(self.board.remaining_ships)}")
        lines.append("")

        # Show middle layer (z = size_z // 2)
        z = self.size_z // 2
        lines.append(f"Layer Z={z}:")
        lines.append("  " + " ".join(f"{y:2}" for y in range(self.size_y)))

        for x in range(self.size_x):
            row = f"{x:2} "
            for y in range(self.size_y):
                state = self.board.get_cell_state(x, y, z)
                if state == CellState3D.HIT:
                    row += " X"
                elif state == CellState3D.MISS:
                    row += " ."
                elif state == CellState3D.SUNK:
                    row += " #"
                elif state == CellState3D.SHIP:
                    row += " S"
                else:
                    row += " ~"
            lines.append(row)

        return "\n".join(lines)


# Register the environment
gym.register(
    id="SpaceBattleship-v0",
    entry_point="app.ml.environment3d:SpaceBattleshipEnv",
)
