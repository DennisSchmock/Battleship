import random


class RandomTileBot:
    def __init__(self, seed: int = 0):
        self.rng = random.Random(seed)

    def choose_action(self, legal_actions):
        return self.rng.choice(legal_actions).id if legal_actions else None


class GreedyTileBot:
    def choose_action(self, legal_actions):
        if not legal_actions:
            return None
        center_dist = lambda a: abs(a.x - 5) + abs(a.y - 5)
        best = sorted(legal_actions, key=lambda a: (-a.heuristic.get("claims_cells", 0), center_dist(a), a.id))[0]
        return best.id


class BlockingTileBot:
    def choose_action(self, legal_actions):
        if not legal_actions:
            return None
        center_dist = lambda a: abs(a.x - 5) + abs(a.y - 5)
        best = sorted(legal_actions, key=lambda a: (-a.heuristic.get("adjacent_enemy_cells", 0), -a.heuristic.get("claims_cells", 0), center_dist(a), a.id))[0]
        return best.id
