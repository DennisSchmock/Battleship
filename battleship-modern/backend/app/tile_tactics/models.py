from dataclasses import dataclass, field
from typing import Optional, Any


@dataclass(frozen=True)
class Position:
    x: int
    y: int


@dataclass(frozen=True)
class Piece:
    id: str
    cells: list[Position]


@dataclass(frozen=True)
class TileAction:
    action_id: str


@dataclass
class LegalAction:
    id: str
    player_id: int
    piece_id: str
    x: int
    y: int
    rotation: int
    cells: list[Position]
    label: str
    heuristic: dict[str, Any] = field(default_factory=dict)


@dataclass
class PlayerState:
    player_id: int
    remaining_pieces: set[str]


@dataclass
class GameConfig:
    board_size: int = 10
    max_turns: int = 60
    seed: int = 0


@dataclass
class GameState:
    turn: int
    current_player: int
    board: list[list[Optional[int]]]
    scores: dict[int, int]
    remaining_pieces: dict[int, list[str]]


@dataclass
class TurnResult:
    turn: int
    player_id: int
    action_id: Optional[str]
    passed: bool
    scores: dict[int, int]
    game_over: bool
    winner: Optional[int]
