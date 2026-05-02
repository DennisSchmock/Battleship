from app.tile_tactics.engine import TileTacticsGame
from app.tile_tactics.models import GameConfig
from app.tile_tactics.bots import RandomTileBot, GreedyTileBot, BlockingTileBot


def test_random_returns_legal():
    g = TileTacticsGame(GameConfig())
    legal = g.get_legal_actions()
    pick = RandomTileBot(seed=1).choose_action(legal)
    assert pick in {a.id for a in legal}


def test_greedy_prefers_biggest_piece():
    g = TileTacticsGame(GameConfig())
    pick = GreedyTileBot().choose_action(g.get_legal_actions())
    assert 'square' in pick or 'l4' in pick


def test_blocking_returns_legal():
    g = TileTacticsGame(GameConfig())
    pick = BlockingTileBot().choose_action(g.get_legal_actions())
    assert pick in {a.id for a in g.get_legal_actions()}
