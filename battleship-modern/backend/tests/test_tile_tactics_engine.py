from app.tile_tactics.engine import TileTacticsGame, PIECES
from app.tile_tactics.models import GameConfig
from app.tile_tactics.bots import GreedyTileBot, RandomTileBot, BlockingTileBot


# === Existing invariants ===

def test_board_uses_default_size():
    g = TileTacticsGame(GameConfig())
    assert len(g.board) == g.config.board_size
    assert all(len(row) == g.config.board_size for row in g.board)


def test_piece_rotation():
    g = TileTacticsGame(GameConfig())
    r = g.rotate_piece([(0, 0), (1, 0), (2, 0)], 90)
    assert len(r) == 3


def test_first_move_anywhere_and_no_overlap():
    g = TileTacticsGame(GameConfig())
    assert g.get_legal_actions()
    aid = g.get_legal_actions()[0].id
    g.execute_action(aid)
    assert all(a.id != aid for a in g.get_legal_actions())


def test_seed_deterministic():
    g1 = TileTacticsGame(GameConfig(seed=5))
    g2 = TileTacticsGame(GameConfig(seed=5))
    assert [a.id for a in g1.get_legal_actions()] == [a.id for a in g2.get_legal_actions()]


# === Opstramning 1: tighter board ===

def test_default_board_is_seven_by_seven():
    """Given a default config, when game starts, then board is 7×7 for tighter contention."""
    g = TileTacticsGame(GameConfig())
    assert g.config.board_size == 7
    assert len(g.board) == 7 and len(g.board[0]) == 7


def test_board_size_is_configurable():
    """Given a custom board_size, when game starts, then engine respects the configured size."""
    g = TileTacticsGame(GameConfig(board_size=10))
    assert len(g.board) == 10


# === Opstramning 2: multiple pieces per type ===

def test_each_player_starts_with_three_of_each_piece():
    """Given default config, when game starts, then each player has 3 copies of each piece type."""
    g = TileTacticsGame(GameConfig())
    for pid in (0, 1):
        for piece_id in PIECES:
            assert g.piece_count(pid, piece_id) == 3, (
                f"Player {pid} should have 3 of {piece_id}, has {g.piece_count(pid, piece_id)}"
            )


def test_piece_inventory_decrements_on_placement():
    """Given a player places piece X, when checking inventory, then count of X is reduced by one."""
    g = TileTacticsGame(GameConfig(seed=0))
    legal = g.get_legal_actions()
    chosen = next(a for a in legal if a.piece_id == "single")
    before = g.piece_count(0, "single")
    g.execute_action(chosen.id)
    assert g.piece_count(0, "single") == before - 1


def test_piece_can_be_placed_multiple_times():
    """Given 3 of each piece, when player places same piece type repeatedly, then it remains legal until exhausted."""
    g = TileTacticsGame(GameConfig(board_size=10, seed=0))
    placements = 0
    for _ in range(20):
        legal = [a for a in g.get_legal_actions() if a.piece_id == "single" and a.player_id == g.current_player]
        if not legal:
            break
        if g.current_player == 0:
            g.execute_action(legal[0].id)
            placements += 1
        else:
            other = g.get_legal_actions()
            g.execute_action(other[0].id if other else None)
    assert placements == 3, f"Expected 3 'single' placements for player 0, got {placements}"


def test_piece_no_longer_legal_when_inventory_exhausted():
    """Given a player has used all 3 of a piece, when fetching legal actions, then that piece is absent."""
    g = TileTacticsGame(GameConfig(board_size=10, seed=0))
    for _ in range(3):
        legal = [a for a in g.get_legal_actions() if a.piece_id == "single"]
        assert legal, "Should still have 'single' available"
        g.execute_action(legal[0].id)
        # Opponent turn — pick anything
        opp_legal = g.get_legal_actions()
        if opp_legal:
            g.execute_action(opp_legal[0].id)
    p0_singles = [a for a in g.get_legal_actions() if a.piece_id == "single" and a.player_id == 0]
    assert not p0_singles


# === Opstramning 3: adjacency-bonus + first-pass-ends ===

def test_first_placement_scores_only_cells():
    """Given a fresh board, when first move is placed, then score equals cell count (no bonus possible)."""
    g = TileTacticsGame(GameConfig(seed=0))
    legal = g.get_legal_actions()
    chosen = next(a for a in legal if a.piece_id == "single")
    g.execute_action(chosen.id)
    assert g.scores[0] == 1


def test_adjacent_placement_awards_bonus():
    """Given player has a placed cell, when player places adjacent piece, then score is cells + adjacency bonus."""
    g = TileTacticsGame(GameConfig(board_size=7, seed=0))
    # P0 places single at (3,3)
    p0_first = next(a for a in g.get_legal_actions() if a.piece_id == "single" and a.x == 3 and a.y == 3)
    g.execute_action(p0_first.id)
    # P1 places single far away
    p1_far = next(a for a in g.get_legal_actions() if a.piece_id == "single" and a.x == 0 and a.y == 0)
    g.execute_action(p1_far.id)
    # P0 places single adjacent to (3,3) — at (4,3)
    p0_adj = next(a for a in g.get_legal_actions() if a.piece_id == "single" and a.x == 4 and a.y == 3)
    g.execute_action(p0_adj.id)
    # 1 (first) + 1 cell + 1 adjacency bonus = 3
    assert g.scores[0] == 3


def test_multi_cell_adjacency_counts_each_neighbor():
    """Given an L-shape adjacent to two own cells, when placed, then bonus = number of orthogonal own neighbors."""
    g = TileTacticsGame(GameConfig(board_size=10, seed=0))
    # P0 places domino at (3,3)-(4,3)
    p0_first = next(a for a in g.get_legal_actions() if a.piece_id == "domino" and a.x == 3 and a.y == 3 and a.rotation == 0)
    g.execute_action(p0_first.id)  # score = 2
    # P1 plays anywhere far
    p1 = next(a for a in g.get_legal_actions() if a.x == 0 and a.y == 0 and a.player_id == 1)
    g.execute_action(p1.id)
    # P0 places another domino at (3,4)-(4,4) — both cells touch own cells above, so 2 adjacencies
    p0_next = next(
        a for a in g.get_legal_actions()
        if a.piece_id == "domino" and a.x == 3 and a.y == 4 and a.rotation == 0
    )
    g.execute_action(p0_next.id)
    # 2 (first domino) + 2 cells + 2 adjacencies = 6
    assert g.scores[0] == 6


def test_game_ends_when_first_player_cannot_place():
    """Given a 3×3 board (saturates fast), when one player runs out of legal moves, then game_over is True."""
    g = TileTacticsGame(GameConfig(board_size=3, seed=0))
    safety = 200
    while not g.game_over and safety > 0:
        legal = g.get_legal_actions()
        if legal:
            g.execute_action(legal[0].id)
        else:
            g.execute_action(None)
        safety -= 1
    assert g.game_over
    # First-pass rule: termination triggered by ≥1 consecutive pass (not 2)
    assert g.consecutive_passes >= 1


# === Tactical depth: outcomes should vary ===

def test_greedy_vs_random_does_not_always_draw():
    """Given new tactical rules, when greedy plays random across many seeds, then results vary."""
    score_pairs = set()
    for seed in range(10):
        g = TileTacticsGame(GameConfig(seed=seed))
        p1, p2 = GreedyTileBot(seed=seed), RandomTileBot(seed=seed + 100)
        safety = 1000
        while not g.game_over and safety > 0:
            bot = p1 if g.current_player == 0 else p2
            aid = bot.choose_action(g.get_legal_actions())
            g.execute_action(aid)
            safety -= 1
        score_pairs.add((g.scores[0], g.scores[1]))
    assert len(score_pairs) > 1, f"Expected varied outcomes, got always {score_pairs}"


def test_blocking_bot_wins_against_random_more_often_than_loses():
    """Given the new rules reward blocking, when Blocking plays Random many seeds, then Blocking wins more than half."""
    blocking_wins = 0
    decisive_games = 0
    for seed in range(20):
        g = TileTacticsGame(GameConfig(seed=seed))
        p1, p2 = BlockingTileBot(seed=seed), RandomTileBot(seed=seed + 100)
        safety = 1000
        while not g.game_over and safety > 0:
            bot = p1 if g.current_player == 0 else p2
            aid = bot.choose_action(g.get_legal_actions())
            g.execute_action(aid)
            safety -= 1
        if g.winner is not None:
            decisive_games += 1
            if g.winner == 0:
                blocking_wins += 1
    assert decisive_games >= 10, "Expected most games to have a winner under new rules"
    assert blocking_wins > decisive_games / 2, (
        f"Blocking should beat Random majority of decisive games, won {blocking_wins}/{decisive_games}"
    )
