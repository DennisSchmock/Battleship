"""Tournament management for Battleship AI competitions."""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Type
from enum import Enum
import asyncio
import random

from ..game.game import BattleshipGame, GameState
from ..game.player import Player, AIPlayer, HunterAIPlayer
from ..ml.rl_player import RLPlayer


class TournamentFormat(Enum):
    ROUND_ROBIN = "round_robin"
    SINGLE_ELIMINATION = "single_elimination"
    BEST_OF_N = "best_of_n"


@dataclass
class MatchResult:
    """Result of a single match."""

    player1_name: str
    player2_name: str
    winner_name: str
    player1_shots: int
    player2_shots: int
    total_turns: int
    events: List[dict]

    def to_dict(self) -> dict:
        return {
            "player1": self.player1_name,
            "player2": self.player2_name,
            "winner": self.winner_name,
            "player1_shots": self.player1_shots,
            "player2_shots": self.player2_shots,
            "total_turns": self.total_turns,
            "events": self.events,
        }


@dataclass
class PlayerStats:
    """Statistics for a player in the tournament."""

    name: str
    wins: int = 0
    losses: int = 0
    total_shots_fired: int = 0
    total_hits: int = 0
    games_played: int = 0

    @property
    def win_rate(self) -> float:
        return self.wins / self.games_played if self.games_played > 0 else 0

    @property
    def accuracy(self) -> float:
        return self.total_hits / self.total_shots_fired if self.total_shots_fired > 0 else 0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "wins": self.wins,
            "losses": self.losses,
            "games_played": self.games_played,
            "win_rate": self.win_rate,
            "accuracy": self.accuracy,
            "total_shots": self.total_shots_fired,
            "total_hits": self.total_hits,
        }


# Registry of available AI players
AI_PLAYER_REGISTRY: Dict[str, Type[Player]] = {
    "random": AIPlayer,
    "hunter": HunterAIPlayer,
    "rl": RLPlayer,
}


def create_player(player_type: str, name: str, **kwargs) -> Player:
    """Factory function to create players."""
    if player_type not in AI_PLAYER_REGISTRY:
        raise ValueError(f"Unknown player type: {player_type}")

    player_class = AI_PLAYER_REGISTRY[player_type]
    return player_class(name=name, **kwargs)


@dataclass
class Tournament:
    """Manages a tournament between multiple AI players."""

    name: str
    format: TournamentFormat = TournamentFormat.ROUND_ROBIN
    games_per_match: int = 3  # Best of N
    players: List[Player] = field(default_factory=list)
    stats: Dict[str, PlayerStats] = field(default_factory=dict)
    match_results: List[MatchResult] = field(default_factory=list)
    current_match: Optional[BattleshipGame] = None
    is_running: bool = False

    def add_player(self, player: Player) -> None:
        """Add a player to the tournament."""
        self.players.append(player)
        self.stats[player.name] = PlayerStats(name=player.name)

    def _play_single_game(self, player1: Player, player2: Player) -> MatchResult:
        """Play a single game and return the result."""
        game = BattleshipGame(player1=player1, player2=player2)
        self.current_match = game

        winner = game.play_full_game()

        result = MatchResult(
            player1_name=player1.name,
            player2_name=player2.name,
            winner_name=winner.name,
            player1_shots=len(player1.shots_fired),
            player2_shots=len(player2.shots_fired),
            total_turns=game.turn_count,
            events=[e.to_dict() for e in game.events],
        )

        return result

    def _play_match(self, player1: Player, player2: Player) -> str:
        """Play a best-of-N match and return the winner's name."""
        wins = {player1.name: 0, player2.name: 0}
        games_needed = (self.games_per_match // 2) + 1

        for game_num in range(self.games_per_match):
            # Alternate who goes first
            if game_num % 2 == 0:
                result = self._play_single_game(player1, player2)
            else:
                result = self._play_single_game(player2, player1)

            self.match_results.append(result)
            wins[result.winner_name] += 1

            # Update stats
            for p_name, shots, hits in [
                (result.player1_name, result.player1_shots, len([e for e in result.events if e["player"] == result.player1_name and e["action"] in ["hit", "sunk"]])),
                (result.player2_name, result.player2_shots, len([e for e in result.events if e["player"] == result.player2_name and e["action"] in ["hit", "sunk"]])),
            ]:
                self.stats[p_name].total_shots_fired += shots
                self.stats[p_name].total_hits += hits
                self.stats[p_name].games_played += 1

            # Check for early winner
            if wins[player1.name] >= games_needed:
                return player1.name
            if wins[player2.name] >= games_needed:
                return player2.name

        # Return winner based on total wins
        return player1.name if wins[player1.name] > wins[player2.name] else player2.name

    def run_round_robin(self) -> Dict[str, PlayerStats]:
        """Run a round-robin tournament."""
        self.is_running = True

        for i, player1 in enumerate(self.players):
            for player2 in self.players[i + 1:]:
                winner_name = self._play_match(player1, player2)

                # Update win/loss
                loser_name = player2.name if winner_name == player1.name else player1.name
                self.stats[winner_name].wins += 1
                self.stats[loser_name].losses += 1

        self.is_running = False
        return self.stats

    def get_leaderboard(self) -> List[PlayerStats]:
        """Get sorted leaderboard."""
        return sorted(
            self.stats.values(),
            key=lambda s: (s.wins, s.accuracy),
            reverse=True
        )

    def to_dict(self) -> dict:
        """Convert tournament to dictionary."""
        return {
            "name": self.name,
            "format": self.format.value,
            "games_per_match": self.games_per_match,
            "is_running": self.is_running,
            "players": [p.name for p in self.players],
            "leaderboard": [s.to_dict() for s in self.get_leaderboard()],
            "total_matches": len(self.match_results),
        }


class AsyncTournament(Tournament):
    """Tournament that can be run asynchronously with progress updates."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._event_queue: asyncio.Queue = asyncio.Queue()

    async def emit_event(self, event_type: str, data: dict) -> None:
        """Emit an event to connected clients."""
        await self._event_queue.put({"type": event_type, "data": data})

    async def get_event(self) -> dict:
        """Get the next event from the queue."""
        return await self._event_queue.get()

    async def run_round_robin_async(self) -> Dict[str, PlayerStats]:
        """Run tournament with async event emission."""
        self.is_running = True
        await self.emit_event("tournament_start", {"name": self.name, "players": [p.name for p in self.players]})

        match_num = 0
        total_matches = len(self.players) * (len(self.players) - 1) // 2

        for i, player1 in enumerate(self.players):
            for player2 in self.players[i + 1:]:
                match_num += 1
                await self.emit_event("match_start", {
                    "match": match_num,
                    "total_matches": total_matches,
                    "player1": player1.name,
                    "player2": player2.name,
                })

                winner_name = self._play_match(player1, player2)

                loser_name = player2.name if winner_name == player1.name else player1.name
                self.stats[winner_name].wins += 1
                self.stats[loser_name].losses += 1

                await self.emit_event("match_end", {
                    "match": match_num,
                    "winner": winner_name,
                    "leaderboard": [s.to_dict() for s in self.get_leaderboard()],
                })

                # Small delay to allow UI to update
                await asyncio.sleep(0.1)

        self.is_running = False
        await self.emit_event("tournament_end", {
            "leaderboard": [s.to_dict() for s in self.get_leaderboard()],
            "total_games": len(self.match_results),
        })

        return self.stats
