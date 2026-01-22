"""Tournament runner for Strategic SpaceBattleship."""
import random
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Type, Tuple
from datetime import datetime

from .models import GameConfig, Position, Direction
from .engine import StrategicGame, GamePhase
from .bot_interface import SpaceBot


@dataclass
class MatchResult:
    """Result of a single match between two bots."""
    bot1_name: str
    bot2_name: str
    winner: str
    turns: int
    bot1_ships_remaining: int
    bot2_ships_remaining: int
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "bot1": self.bot1_name,
            "bot2": self.bot2_name,
            "winner": self.winner,
            "turns": self.turns,
            "bot1_ships_remaining": self.bot1_ships_remaining,
            "bot2_ships_remaining": self.bot2_ships_remaining,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class BotStats:
    """Statistics for a bot in the tournament."""
    name: str
    wins: int = 0
    losses: int = 0
    total_turns: int = 0
    ships_destroyed: int = 0
    ships_lost: int = 0

    @property
    def games_played(self) -> int:
        return self.wins + self.losses

    @property
    def win_rate(self) -> float:
        if self.games_played == 0:
            return 0.0
        return self.wins / self.games_played

    @property
    def avg_turns(self) -> float:
        if self.games_played == 0:
            return 0.0
        return self.total_turns / self.games_played

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "wins": self.wins,
            "losses": self.losses,
            "games_played": self.games_played,
            "win_rate": round(self.win_rate * 100, 1),
            "avg_turns": round(self.avg_turns, 1),
            "ships_destroyed": self.ships_destroyed,
            "ships_lost": self.ships_lost
        }


def run_match(bot1: SpaceBot, bot2: SpaceBot, config: GameConfig = None) -> MatchResult:
    """Run a single match between two bots."""
    if config is None:
        config = GameConfig()

    game = StrategicGame(config=config)

    # Initialize bots
    bot1.on_game_start(config)
    bot2.on_game_start(config)

    # Get ship placements
    try:
        placements1 = bot1.place_ships(config)
        placements2 = bot2.place_ships(config)
    except Exception as e:
        raise RuntimeError(f"Ship placement failed: {e}")

    # Convert placements to the format expected by engine
    def convert_placements(placements, ships_config):
        result = []
        for i, (pos, direction) in enumerate(placements):
            ship_name, ship_size = ships_config[i]
            result.append((f"{ship_name.lower()}_{i}", pos, direction))
        return result

    game.setup_player_ships(game.player1, convert_placements(placements1, config.ships))
    game.setup_player_ships(game.player2, convert_placements(placements2, config.ships))

    game.player1.name = bot1.get_name()
    game.player2.name = bot2.get_name()

    game.start_game()

    # Play the game
    max_turns = 500  # Safety limit
    bots = [bot1, bot2]

    while game.phase == GamePhase.PLAYING and game.turn < max_turns:
        current_bot = bots[game.current_player_idx]
        current_player = game.current_player

        # Get game state for current player
        state = game.get_game_state(current_player)

        # Get actions from bot
        try:
            actions = current_bot.get_actions(state)
        except Exception as e:
            print(f"Bot {current_bot.get_name()} error: {e}")
            actions = []

        # Execute actions
        result = game.execute_turn(actions)

        # Notify bot of results
        try:
            current_bot.on_turn_result(result)
        except Exception as e:
            print(f"Bot {current_bot.get_name()} on_turn_result error: {e}")

        # End turn
        game.end_turn()

    # Determine winner
    if game.winner:
        winner = game.winner
    elif game.player1.all_ships_destroyed():
        winner = game.player2.name
    elif game.player2.all_ships_destroyed():
        winner = game.player1.name
    else:
        # Draw or timeout - whoever has more ships wins
        p1_ships = sum(1 for s in game.player1.ships if not s.is_destroyed)
        p2_ships = sum(1 for s in game.player2.ships if not s.is_destroyed)
        if p1_ships > p2_ships:
            winner = game.player1.name
        elif p2_ships > p1_ships:
            winner = game.player2.name
        else:
            winner = "Draw"

    # Notify bots of game end
    final_state1 = game.get_game_state(game.player1)
    final_state2 = game.get_game_state(game.player2)
    bot1.on_game_end(winner == bot1.get_name(), final_state1)
    bot2.on_game_end(winner == bot2.get_name(), final_state2)

    return MatchResult(
        bot1_name=bot1.get_name(),
        bot2_name=bot2.get_name(),
        winner=winner,
        turns=game.turn,
        bot1_ships_remaining=sum(1 for s in game.player1.ships if not s.is_destroyed),
        bot2_ships_remaining=sum(1 for s in game.player2.ships if not s.is_destroyed)
    )


class Tournament:
    """Runs a round-robin tournament between multiple bots."""

    def __init__(self, config: GameConfig = None):
        self.config = config or GameConfig()
        self.bots: List[Type[SpaceBot]] = []
        self.results: List[MatchResult] = []
        self.stats: Dict[str, BotStats] = {}

    def add_bot(self, bot_class: Type[SpaceBot]):
        """Add a bot class to the tournament."""
        self.bots.append(bot_class)

    def run(self, rounds_per_matchup: int = 10) -> Dict[str, BotStats]:
        """Run the tournament."""
        # Initialize stats
        for bot_class in self.bots:
            bot = bot_class()
            name = bot.get_name()
            self.stats[name] = BotStats(name=name)

        # Round robin - each bot plays each other bot
        matchups = []
        for i, bot1_class in enumerate(self.bots):
            for bot2_class in self.bots[i + 1:]:
                matchups.append((bot1_class, bot2_class))

        # Run matches
        for bot1_class, bot2_class in matchups:
            for round_num in range(rounds_per_matchup):
                # Alternate who goes first
                if round_num % 2 == 0:
                    result = run_match(bot1_class(), bot2_class(), self.config)
                else:
                    result = run_match(bot2_class(), bot1_class(), self.config)

                self.results.append(result)
                self._update_stats(result)

        return self.stats

    def _update_stats(self, result: MatchResult):
        """Update bot statistics from a match result."""
        stats1 = self.stats[result.bot1_name]
        stats2 = self.stats[result.bot2_name]

        stats1.total_turns += result.turns
        stats2.total_turns += result.turns

        if result.winner == result.bot1_name:
            stats1.wins += 1
            stats2.losses += 1
        elif result.winner == result.bot2_name:
            stats1.losses += 1
            stats2.wins += 1
        else:
            # Draw counts as loss for both
            stats1.losses += 1
            stats2.losses += 1

        # Ships stats
        stats1.ships_lost += 5 - result.bot1_ships_remaining
        stats2.ships_lost += 5 - result.bot2_ships_remaining
        stats1.ships_destroyed += 5 - result.bot2_ships_remaining
        stats2.ships_destroyed += 5 - result.bot1_ships_remaining

    def get_leaderboard(self) -> List[BotStats]:
        """Get bots sorted by win rate."""
        return sorted(self.stats.values(), key=lambda s: (-s.win_rate, -s.wins))

    def print_results(self):
        """Print tournament results."""
        print("\n" + "=" * 60)
        print("TOURNAMENT RESULTS")
        print("=" * 60)

        leaderboard = self.get_leaderboard()
        print(f"\n{'Rank':<6}{'Bot':<20}{'W':<6}{'L':<6}{'Win%':<8}{'Avg Turns':<10}")
        print("-" * 56)

        for i, stats in enumerate(leaderboard, 1):
            print(f"{i:<6}{stats.name:<20}{stats.wins:<6}{stats.losses:<6}"
                  f"{stats.win_rate*100:>5.1f}%  {stats.avg_turns:>8.1f}")

        print("\n" + "=" * 60)


def quick_test():
    """Quick test of the tournament system."""
    from .bots import RandomBot, HunterBot, ScoutBot, EvasiveBot

    print("Running quick tournament test...")

    tournament = Tournament()
    tournament.add_bot(RandomBot)
    tournament.add_bot(HunterBot)
    tournament.add_bot(ScoutBot)
    tournament.add_bot(EvasiveBot)

    tournament.run(rounds_per_matchup=5)
    tournament.print_results()


if __name__ == "__main__":
    quick_test()
