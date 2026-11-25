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


# === Tiebreaker randomness (preserves "same seed = same choice") ===

def test_greedy_breaks_ties_with_rng():
    """Given identical legal_actions, when GreedyTileBot is seeded differently, then it picks varying actions."""
    g = TileTacticsGame(GameConfig(seed=0))
    legal = g.get_legal_actions()
    picks = {GreedyTileBot(seed=s).choose_action(legal) for s in range(30)}
    assert len(picks) > 1, "Greedy must use rng to break ties between equally-good actions"


def test_blocking_breaks_ties_with_rng():
    """Given identical legal_actions, when BlockingTileBot is seeded differently, then it picks varying actions."""
    g = TileTacticsGame(GameConfig(seed=0))
    legal = g.get_legal_actions()
    picks = {BlockingTileBot(seed=s).choose_action(legal) for s in range(30)}
    assert len(picks) > 1


def test_greedy_same_seed_same_choice():
    """Given same seed, when GreedyTileBot picks twice on same legal actions, then both picks are identical."""
    g = TileTacticsGame(GameConfig(seed=0))
    legal = g.get_legal_actions()
    a = GreedyTileBot(seed=42).choose_action(legal)
    b = GreedyTileBot(seed=42).choose_action(legal)
    assert a == b


def test_greedy_top_choice_remains_optimal():
    """Given rng tiebreakers, when GreedyTileBot chooses, then it still picks among the top-tier (biggest, nearest-center) actions."""
    g = TileTacticsGame(GameConfig())
    legal = g.get_legal_actions()
    for s in range(20):
        pick_id = GreedyTileBot(seed=s).choose_action(legal)
        chosen = next(a for a in legal if a.id == pick_id)
        # Greedy must always pick a maximum-claims_cells action (4-cell pieces)
        assert chosen.heuristic.get("claims_cells") == 4


def test_greedy_vs_greedy_outcomes_vary_across_seeds():
    """Given Greedy vs Greedy across many seeds, when games play out, then outcomes vary (no longer identical)."""
    outcomes = set()
    for seed in range(20):
        g = TileTacticsGame(GameConfig(seed=seed))
        p1, p2 = GreedyTileBot(seed=seed), GreedyTileBot(seed=seed + 1000)
        safety = 1000
        while not g.game_over and safety > 0:
            bot = p1 if g.current_player == 0 else p2
            aid = bot.choose_action(g.get_legal_actions())
            g.execute_action(aid)
            safety -= 1
        outcomes.add((g.scores[0], g.scores[1]))
    assert len(outcomes) > 5, f"Expected varied Greedy-vs-Greedy outcomes, got {outcomes}"
