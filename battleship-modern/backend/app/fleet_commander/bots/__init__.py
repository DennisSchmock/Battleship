"""Bots for Fleet Commander."""
from .tactical_bot import TacticalBot
from .aggressive_bot import AggressiveBot
from .defensive_bot import DefensiveBot
from .random_bot import RandomBot

__all__ = ['TacticalBot', 'AggressiveBot', 'DefensiveBot', 'RandomBot']
