from app.tile_tactics.engine import TileTacticsGame
from app.tile_tactics.models import GameConfig


def test_board_init():
    g = TileTacticsGame(GameConfig(seed=1))
    assert len(g.board) == 10 and len(g.board[0]) == 10


def test_piece_rotation():
    g = TileTacticsGame(GameConfig())
    r = g.rotate_piece([(0,0),(1,0),(2,0)], 90)
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
