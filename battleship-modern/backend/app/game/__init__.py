# Game engine module
from .board import Board
from .ship import Ship
from .game import BattleshipGame
from .player import Player, AIPlayer

# 3D Game engine
from .board3d import Board3D
from .ship3d import Ship3D
from .game3d import SpaceBattleshipGame
from .player3d import Player3D, RandomPlayer3D, HunterAI3D, SmartHunter3D

__all__ = [
    # 2D
    "Board", "Ship", "BattleshipGame", "Player", "AIPlayer",
    # 3D
    "Board3D", "Ship3D", "SpaceBattleshipGame",
    "Player3D", "RandomPlayer3D", "HunterAI3D", "SmartHunter3D",
]
