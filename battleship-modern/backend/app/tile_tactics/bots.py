import random


class RandomTileBot:
    def __init__(self, seed: int = 0):
        self.rng = random.Random(seed)

    def choose_action(self, legal_actions):
        return self.rng.choice(legal_actions).id if legal_actions else None


def _pick_top_tier(legal_actions, key, rng):
    """Sort by key, then return rng-chosen action from those tied at the optimum."""
    sorted_actions = sorted(legal_actions, key=key)
    top_score = key(sorted_actions[0])
    top_tier = [a for a in sorted_actions if key(a) == top_score]
    return rng.choice(top_tier)


class GreedyTileBot:
    def __init__(self, seed: int = 0):
        self.rng = random.Random(seed)

    def choose_action(self, legal_actions):
        if not legal_actions:
            return None
        center_dist = lambda a: abs(a.x - 5) + abs(a.y - 5)
        key = lambda a: (-a.heuristic.get("claims_cells", 0), center_dist(a))
        return _pick_top_tier(legal_actions, key, self.rng).id


class BlockingTileBot:
    def __init__(self, seed: int = 0):
        self.rng = random.Random(seed)

    def choose_action(self, legal_actions):
        if not legal_actions:
            return None
        center_dist = lambda a: abs(a.x - 5) + abs(a.y - 5)
        key = lambda a: (
            -a.heuristic.get("adjacent_enemy_cells", 0),
            -a.heuristic.get("claims_cells", 0),
            center_dist(a),
        )
        return _pick_top_tier(legal_actions, key, self.rng).id
