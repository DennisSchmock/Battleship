from __future__ import annotations
from dataclasses import asdict
from copy import deepcopy
import random
from .models import Position, LegalAction, GameConfig, GameState, TurnResult

PIECES = {
    "single": [(0, 0)],
    "domino": [(0, 0), (1, 0)],
    "tri_line": [(0, 0), (1, 0), (2, 0)],
    "tri_l": [(0, 0), (1, 0), (0, 1)],
    "square": [(0, 0), (1, 0), (0, 1), (1, 1)],
    "l4": [(0, 0), (0, 1), (0, 2), (1, 2)],
}


class TileTacticsGame:
    def __init__(self, config: GameConfig):
        self.config = config
        self.rng = random.Random(config.seed)
        self.board = [[None for _ in range(config.board_size)] for _ in range(config.board_size)]
        self.current_player = 0
        self.turn = 0
        self.scores = {0: 0, 1: 0}
        self.remaining_pieces = {0: set(PIECES.keys()), 1: set(PIECES.keys())}
        self.consecutive_passes = 0
        self.game_over = False
        self.winner = None

    def rotate_piece(self, cells, rotation):
        rot = rotation % 360
        out = list(cells)
        for _ in range(rot // 90):
            out = [(y, -x) for x, y in out]
        min_x = min(x for x, _ in out)
        min_y = min(y for _, y in out)
        return [(x - min_x, y - min_y) for x, y in out]

    def _has_own_cell(self, player_id):
        return any(c == player_id for row in self.board for c in row)

    def _orth_adjacent_own(self, player_id, placed):
        for x, y in placed:
            for dx, dy in [(1,0),(-1,0),(0,1),(0,-1)]:
                nx, ny = x+dx, y+dy
                if 0 <= nx < self.config.board_size and 0 <= ny < self.config.board_size:
                    if self.board[ny][nx] == player_id:
                        return True
        return False

    def legal_actions_for(self, player_id):
        actions = []
        first_move = not self._has_own_cell(player_id)
        center = self.config.board_size // 2
        for piece_id in sorted(self.remaining_pieces[player_id]):
            for rotation in [0, 90, 180, 270]:
                shape = self.rotate_piece(PIECES[piece_id], rotation)
                for y in range(self.config.board_size):
                    for x in range(self.config.board_size):
                        placed = [(x + dx, y + dy) for dx, dy in shape]
                        if any(px < 0 or py < 0 or px >= self.config.board_size or py >= self.config.board_size for px, py in placed):
                            continue
                        if any(self.board[py][px] is not None for px, py in placed):
                            continue
                        if not first_move and not self._orth_adjacent_own(player_id, placed):
                            continue
                        adj_enemy = 0
                        adj_own = 0
                        for px, py in placed:
                            for dx, dy in [(1,0),(-1,0),(0,1),(0,-1)]:
                                nx, ny = px+dx, py+dy
                                if 0 <= nx < self.config.board_size and 0 <= ny < self.config.board_size:
                                    if self.board[ny][nx] == player_id:
                                        adj_own += 1
                                    elif self.board[ny][nx] == 1-player_id:
                                        adj_enemy += 1
                        touches_center = any(px == center and py == center for px, py in placed)
                        action_id = f"p{player_id}_{piece_id}_{x}_{y}_r{rotation}"
                        label = f"Place {piece_id} at {chr(65+x)}{y+1} rotated {rotation} degrees"
                        actions.append(LegalAction(
                            id=action_id, player_id=player_id, piece_id=piece_id, x=x, y=y, rotation=rotation,
                            cells=[Position(px, py) for px, py in placed], label=label,
                            heuristic={"claims_cells": len(placed), "touches_center": touches_center, "adjacent_own_cells": adj_own, "adjacent_enemy_cells": adj_enemy, "blocks_enemy_space": adj_enemy > 0}
                        ))
        uniq = {a.id: a for a in actions}
        return [uniq[k] for k in sorted(uniq)]

    def get_legal_actions(self):
        return self.legal_actions_for(self.current_player)

    def get_state(self):
        return GameState(turn=self.turn, current_player=self.current_player, board=deepcopy(self.board), scores=dict(self.scores), remaining_pieces={0: sorted(self.remaining_pieces[0]), 1: sorted(self.remaining_pieces[1])})

    def visible_state(self):
        return asdict(self.get_state())

    def execute_action(self, action_id: str | None):
        if self.game_over:
            return TurnResult(self.turn, self.current_player, None, True, dict(self.scores), True, self.winner)
        legal = self.get_legal_actions()
        chosen = next((a for a in legal if a.id == action_id), None)
        passed = False
        pid = self.current_player
        if chosen is None:
            if legal:
                chosen = legal[0]
            else:
                passed = True
        if chosen:
            for p in chosen.cells:
                self.board[p.y][p.x] = pid
            self.remaining_pieces[pid].discard(chosen.piece_id)
            self.scores[pid] += len(chosen.cells)
            self.consecutive_passes = 0
        else:
            self.consecutive_passes += 1
        self.turn += 1
        if self.consecutive_passes >= 2 or self.turn >= self.config.max_turns:
            self.game_over = True
            if self.scores[0] == self.scores[1]:
                self.winner = None
            else:
                self.winner = 0 if self.scores[0] > self.scores[1] else 1
        self.current_player = 1 - self.current_player
        if not self.game_over and not self.get_legal_actions():
            # auto-pass next player's no-move turn
            return self.execute_action(None)
        return TurnResult(self.turn, pid, chosen.id if chosen else None, passed, dict(self.scores), self.game_over, self.winner)
