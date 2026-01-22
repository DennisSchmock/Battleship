"""Fleet Commander - Advanced 3D Space Battle Game.

A strategic game with specialized ships, abilities, fog of war, and
a shrinking battlefield to force engagement.
"""
from .models import (
    Position, Direction, ShipType, AbilityType, CellStatus,
    Ship, ShipConfig, SHIP_CONFIGS,
    GameConfig, FleetConfig, PlayerState,
    Action, MoveAction, FireAction, ScanAction, AbilityAction, LockOnAction,
    ActionResult, TurnResult, Storm
)
from .engine import FleetCommanderGame, GamePhase
from .bot_interface import FleetBot, GameView, VisibleShip, random_fleet_placement

__all__ = [
    # Models
    'Position', 'Direction', 'ShipType', 'AbilityType', 'CellStatus',
    'Ship', 'ShipConfig', 'SHIP_CONFIGS',
    'GameConfig', 'FleetConfig', 'PlayerState',
    'Action', 'MoveAction', 'FireAction', 'ScanAction', 'AbilityAction', 'LockOnAction',
    'ActionResult', 'TurnResult', 'Storm',
    # Engine
    'FleetCommanderGame', 'GamePhase',
    # Bot interface
    'FleetBot', 'GameView', 'VisibleShip', 'random_fleet_placement',
]
