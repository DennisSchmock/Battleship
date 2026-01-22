"""Strategic SpaceBattleship - A tactical 3D space combat game."""
from .models import (
    Position, Direction, Ship, GameConfig, GameState,
    Action, FireAction, MoveAction, ScanAction,
    FireResult, MoveResult, ScanResult, TurnResult,
    CellStatus, ActionType
)
from .engine import StrategicGame, GamePhase, PlayerState
from .bot_interface import SpaceBot, random_placement, get_adjacent_positions, get_checkerboard_positions

__all__ = [
    # Models
    'Position', 'Direction', 'Ship', 'GameConfig', 'GameState',
    'Action', 'FireAction', 'MoveAction', 'ScanAction',
    'FireResult', 'MoveResult', 'ScanResult', 'TurnResult',
    'CellStatus', 'ActionType',
    # Engine
    'StrategicGame', 'GamePhase', 'PlayerState',
    # Bot interface
    'SpaceBot', 'random_placement', 'get_adjacent_positions', 'get_checkerboard_positions',
]
