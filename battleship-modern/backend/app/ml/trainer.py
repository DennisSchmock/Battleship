"""Training script for Battleship RL agent."""
import os
from pathlib import Path
from datetime import datetime
from typing import Optional

import numpy as np
from stable_baselines3 import DQN
from stable_baselines3.common.callbacks import BaseCallback, EvalCallback
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import DummyVecEnv

from .environment import BattleshipEnv


class TrainingMetricsCallback(BaseCallback):
    """Custom callback for logging training metrics."""

    def __init__(self, verbose: int = 0):
        super().__init__(verbose)
        self.episode_rewards = []
        self.episode_lengths = []
        self.episode_accuracies = []
        self.wins = 0
        self.total_games = 0

    def _on_step(self) -> bool:
        # Check if episode ended
        if self.locals.get("dones", [False])[0]:
            info = self.locals.get("infos", [{}])[0]

            self.total_games += 1
            if info.get("won", False):
                self.wins += 1
                self.episode_accuracies.append(info.get("accuracy", 0))

            if self.verbose > 0 and self.total_games % 100 == 0:
                win_rate = self.wins / self.total_games
                avg_accuracy = np.mean(self.episode_accuracies[-100:]) if self.episode_accuracies else 0
                print(f"Games: {self.total_games}, Win rate: {win_rate:.2%}, Avg accuracy: {avg_accuracy:.2%}")

        return True


def create_env() -> BattleshipEnv:
    """Create a monitored Battleship environment."""
    env = BattleshipEnv()
    return Monitor(env)


def train_agent(
    total_timesteps: int = 100_000,
    learning_rate: float = 1e-4,
    buffer_size: int = 50_000,
    batch_size: int = 64,
    exploration_fraction: float = 0.3,
    exploration_final_eps: float = 0.05,
    target_update_interval: int = 1000,
    save_path: Optional[str] = None,
    verbose: int = 1,
) -> DQN:
    """
    Train a DQN agent to play Battleship.

    Args:
        total_timesteps: Total training steps
        learning_rate: Learning rate for the optimizer
        buffer_size: Size of the replay buffer
        batch_size: Batch size for training
        exploration_fraction: Fraction of training for exploration decay
        exploration_final_eps: Final exploration rate
        target_update_interval: Steps between target network updates
        save_path: Path to save the trained model
        verbose: Verbosity level

    Returns:
        Trained DQN model
    """
    # Create environment
    env = DummyVecEnv([create_env])

    # Create DQN agent
    model = DQN(
        "MlpPolicy",
        env,
        learning_rate=learning_rate,
        buffer_size=buffer_size,
        batch_size=batch_size,
        exploration_fraction=exploration_fraction,
        exploration_final_eps=exploration_final_eps,
        target_update_interval=target_update_interval,
        verbose=verbose,
        tensorboard_log="./tensorboard_logs/",
    )

    # Setup callbacks
    metrics_callback = TrainingMetricsCallback(verbose=verbose)

    # Create evaluation environment
    eval_env = DummyVecEnv([create_env])
    eval_callback = EvalCallback(
        eval_env,
        best_model_save_path="./models/best/",
        log_path="./logs/",
        eval_freq=5000,
        n_eval_episodes=20,
        deterministic=True,
    )

    # Train
    print(f"Starting training for {total_timesteps} timesteps...")
    model.learn(
        total_timesteps=total_timesteps,
        callback=[metrics_callback, eval_callback],
        progress_bar=True,
    )

    # Save final model
    if save_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_path = f"./models/battleship_dqn_{timestamp}"

    Path(save_path).parent.mkdir(parents=True, exist_ok=True)
    model.save(save_path)
    print(f"Model saved to {save_path}")

    # Print final stats
    print(f"\nTraining complete!")
    print(f"Total games: {metrics_callback.total_games}")
    print(f"Win rate: {metrics_callback.wins / metrics_callback.total_games:.2%}")

    return model


def evaluate_agent(model_path: str, n_episodes: int = 100) -> dict:
    """
    Evaluate a trained agent.

    Args:
        model_path: Path to the saved model
        n_episodes: Number of episodes to evaluate

    Returns:
        Dictionary with evaluation metrics
    """
    model = DQN.load(model_path)
    env = BattleshipEnv()

    wins = 0
    total_shots = []
    accuracies = []

    for _ in range(n_episodes):
        obs, _ = env.reset()
        done = False

        while not done:
            action, _ = model.predict(obs, deterministic=True)
            obs, reward, terminated, truncated, info = env.step(action)
            done = terminated or truncated

        if info.get("won", False):
            wins += 1
            total_shots.append(info.get("total_shots", 0))
            accuracies.append(info.get("accuracy", 0))

    return {
        "win_rate": wins / n_episodes,
        "avg_shots_to_win": np.mean(total_shots) if total_shots else 0,
        "avg_accuracy": np.mean(accuracies) if accuracies else 0,
        "min_shots": min(total_shots) if total_shots else 0,
        "max_shots": max(total_shots) if total_shots else 0,
    }


if __name__ == "__main__":
    # Train a new agent
    model = train_agent(
        total_timesteps=200_000,
        verbose=1,
    )

    # Evaluate
    print("\nEvaluating trained agent...")
    metrics = evaluate_agent("./models/best/best_model", n_episodes=100)
    print(f"Win rate: {metrics['win_rate']:.2%}")
    print(f"Average shots to win: {metrics['avg_shots_to_win']:.1f}")
    print(f"Average accuracy: {metrics['avg_accuracy']:.2%}")
