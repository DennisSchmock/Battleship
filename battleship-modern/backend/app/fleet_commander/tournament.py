"""
Fleet Commander Tournament System

Supports round-robin and single-elimination bracket tournaments
with WebSocket bot participants and spectator mode.
"""
import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Callable, Any
import random


class TournamentFormat(Enum):
    ROUND_ROBIN = "round_robin"
    SINGLE_ELIMINATION = "single_elimination"


class TournamentState(Enum):
    LOBBY = "lobby"           # Waiting for participants
    STARTING = "starting"     # About to start
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class MatchState(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class ScoringModel(Enum):
    WIN_ONLY = "win_only"              # 3 points per win, no time bonus
    WIN_PLUS_TIME = "win_plus_time"    # 3 per win + max(0, 30 - seconds_used) bonus
    TIME_TIEBREAKER = "time_tiebreaker"  # 3 per win, time used as tiebreaker


@dataclass
class Participant:
    """A tournament participant (bot)."""
    id: str
    name: str
    websocket: Any = None  # WebSocket connection
    is_ready: bool = False
    is_internal_bot: bool = False  # True for built-in bots like TacticalBot
    internal_bot_type: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "is_ready": self.is_ready,
            "is_internal_bot": self.is_internal_bot,
        }


@dataclass
class MatchResult:
    """Result of a single match."""
    winner_id: Optional[str]
    loser_id: Optional[str]
    turns: int
    winner_ships_remaining: int
    loser_ships_remaining: int
    replay_id: Optional[str] = None
    winner_time_used_ms: int = 0
    loser_time_used_ms: int = 0

    def to_dict(self) -> dict:
        return {
            "winner_id": self.winner_id,
            "loser_id": self.loser_id,
            "turns": self.turns,
            "winner_ships_remaining": self.winner_ships_remaining,
            "loser_ships_remaining": self.loser_ships_remaining,
            "replay_id": self.replay_id,
            "winner_time_used_ms": self.winner_time_used_ms,
            "loser_time_used_ms": self.loser_time_used_ms,
        }


@dataclass
class Match:
    """A single match between two participants."""
    id: str
    player1_id: str
    player2_id: str
    round_number: int
    state: MatchState = MatchState.PENDING
    result: Optional[MatchResult] = None
    best_of: int = 1
    games_played: List[MatchResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "player1_id": self.player1_id,
            "player2_id": self.player2_id,
            "round_number": self.round_number,
            "state": self.state.value,
            "result": self.result.to_dict() if self.result else None,
            "best_of": self.best_of,
            "games_played": [g.to_dict() for g in self.games_played],
        }


@dataclass
class Standing:
    """Tournament standing for a participant."""
    participant_id: str
    wins: int = 0
    losses: int = 0
    draws: int = 0
    ships_destroyed: int = 0
    ships_lost: int = 0
    total_turns: int = 0
    total_time_used_ms: int = 0
    time_bonus_points: int = 0

    @property
    def points(self) -> int:
        return self.wins * 3 + self.draws * 1 + self.time_bonus_points

    @property
    def games_played(self) -> int:
        return self.wins + self.losses + self.draws

    def to_dict(self) -> dict:
        return {
            "participant_id": self.participant_id,
            "wins": self.wins,
            "losses": self.losses,
            "draws": self.draws,
            "points": self.points,
            "games_played": self.games_played,
            "ships_destroyed": self.ships_destroyed,
            "ships_lost": self.ships_lost,
            "total_time_used_ms": self.total_time_used_ms,
            "time_bonus_points": self.time_bonus_points,
        }


class FleetCommanderTournament:
    """
    Manages a Fleet Commander tournament.

    Supports:
    - Round-robin format (everyone plays everyone)
    - Single elimination bracket
    - Best-of-N matches
    - WebSocket bot participants
    - Spectator broadcast
    """

    def __init__(
        self,
        name: str,
        format: TournamentFormat = TournamentFormat.ROUND_ROBIN,
        best_of: int = 1,
        max_participants: int = 8,
        use_small_grid: bool = True,
        scoring_model: ScoringModel = ScoringModel.WIN_PLUS_TIME,
    ):
        self.id = str(uuid.uuid4())[:8]
        self.name = name
        self.format = format
        self.best_of = best_of
        self.max_participants = max_participants
        self.use_small_grid = use_small_grid
        self.scoring_model = scoring_model

        self.state = TournamentState.LOBBY
        self.participants: Dict[str, Participant] = {}
        self.matches: List[Match] = []
        self.standings: Dict[str, Standing] = {}
        self.current_match: Optional[Match] = None
        self.current_round: int = 0
        self.live_game_state: Optional[dict] = None  # Current game state for live viewing

        self.spectators: List[Any] = []  # WebSocket connections
        self.created_at = datetime.now()
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None

        # Event callbacks
        self._event_handlers: List[Callable] = []

    def add_event_handler(self, handler: Callable):
        """Add a handler for tournament events."""
        self._event_handlers.append(handler)

    async def _emit_event(self, event_type: str, data: dict):
        """Emit event to all handlers."""
        event = {"type": event_type, "tournament_id": self.id, **data}
        for handler in self._event_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                print(f"Event handler error: {e}")

    # =========================================================================
    # Participant Management
    # =========================================================================

    def add_participant(
        self,
        name: str,
        websocket: Any = None,
        is_internal_bot: bool = False,
        internal_bot_type: Optional[str] = None,
    ) -> Optional[Participant]:
        """Add a participant to the tournament."""
        if self.state != TournamentState.LOBBY:
            return None

        if len(self.participants) >= self.max_participants:
            return None

        participant = Participant(
            id=str(uuid.uuid4())[:8],
            name=name,
            websocket=websocket,
            is_ready=is_internal_bot,  # Internal bots are always ready
            is_internal_bot=is_internal_bot,
            internal_bot_type=internal_bot_type,
        )

        self.participants[participant.id] = participant
        self.standings[participant.id] = Standing(participant_id=participant.id)

        return participant

    def remove_participant(self, participant_id: str) -> bool:
        """Remove a participant from the tournament."""
        if self.state != TournamentState.LOBBY:
            return False

        if participant_id in self.participants:
            del self.participants[participant_id]
            del self.standings[participant_id]
            return True
        return False

    def set_participant_ready(self, participant_id: str, ready: bool = True) -> bool:
        """Mark a participant as ready."""
        if participant_id in self.participants:
            self.participants[participant_id].is_ready = ready
            return True
        return False

    def all_participants_ready(self) -> bool:
        """Check if all participants are ready."""
        if len(self.participants) < 2:
            return False
        return all(p.is_ready for p in self.participants.values())

    # =========================================================================
    # Tournament Control
    # =========================================================================

    def can_start(self) -> bool:
        """Check if tournament can start."""
        return (
            self.state == TournamentState.LOBBY
            and len(self.participants) >= 2
            and self.all_participants_ready()
        )

    def start(self, rng: 'random.Random | None' = None) -> bool:
        """Start the tournament."""
        if not self.can_start():
            return False

        self._rng = rng or random

        self.state = TournamentState.STARTING
        self.started_at = datetime.now()

        # Generate matches based on format
        if self.format == TournamentFormat.ROUND_ROBIN:
            self._generate_round_robin_matches()
        else:
            self._generate_bracket_matches()

        self.state = TournamentState.IN_PROGRESS
        self.current_round = 1
        return True

    def _generate_round_robin_matches(self):
        """Generate round-robin schedule."""
        participants = list(self.participants.keys())
        n = len(participants)

        # If odd number, add a "bye"
        if n % 2 == 1:
            participants.append(None)
            n += 1

        rounds = n - 1
        matches_per_round = n // 2

        # Circle method for round-robin scheduling
        for round_num in range(rounds):
            for i in range(matches_per_round):
                p1_idx = i
                p2_idx = n - 1 - i

                p1 = participants[p1_idx]
                p2 = participants[p2_idx]

                # Skip bye matches
                if p1 is None or p2 is None:
                    continue

                match = Match(
                    id=str(uuid.uuid4())[:8],
                    player1_id=p1,
                    player2_id=p2,
                    round_number=round_num + 1,
                    best_of=self.best_of,
                )
                self.matches.append(match)

            # Rotate participants (keep first fixed)
            participants = [participants[0]] + [participants[-1]] + participants[1:-1]

    def _generate_bracket_matches(self):
        """Generate single-elimination bracket."""
        participants = list(self.participants.keys())
        self._rng.shuffle(participants)

        # Pad to power of 2
        bracket_size = 1
        while bracket_size < len(participants):
            bracket_size *= 2

        # Add byes
        while len(participants) < bracket_size:
            participants.append(None)

        # Generate first round
        round_num = 1
        for i in range(0, len(participants), 2):
            p1 = participants[i]
            p2 = participants[i + 1]

            match = Match(
                id=str(uuid.uuid4())[:8],
                player1_id=p1 or "BYE",
                player2_id=p2 or "BYE",
                round_number=round_num,
                best_of=self.best_of,
            )
            self.matches.append(match)

    def get_next_match(self) -> Optional[Match]:
        """Get the next pending match."""
        for match in self.matches:
            if match.state == MatchState.PENDING:
                # Skip bye matches
                if match.player1_id == "BYE" or match.player2_id == "BYE":
                    match.state = MatchState.COMPLETED
                    # Winner is the non-bye
                    winner = match.player1_id if match.player2_id == "BYE" else match.player2_id
                    match.result = MatchResult(
                        winner_id=winner,
                        loser_id=None,
                        turns=0,
                        winner_ships_remaining=7,
                        loser_ships_remaining=0,
                    )
                    continue
                return match
        return None

    def record_match_result(self, match_id: str, result: MatchResult):
        """Record the result of a match."""
        for match in self.matches:
            if match.id == match_id:
                match.games_played.append(result)

                # Check if match is decided (best of N)
                p1_wins = sum(1 for g in match.games_played if g.winner_id == match.player1_id)
                p2_wins = sum(1 for g in match.games_played if g.winner_id == match.player2_id)
                wins_needed = (match.best_of // 2) + 1

                if p1_wins >= wins_needed or p2_wins >= wins_needed:
                    match.state = MatchState.COMPLETED
                    match.result = result

                    # Update standings
                    self._update_standings(match)

                    # For bracket format, advance winner
                    if self.format == TournamentFormat.SINGLE_ELIMINATION:
                        self._advance_bracket_winner(match)

                break

    def _update_standings(self, match: Match):
        """Update standings after a match."""
        if not match.result:
            return

        winner_id = match.result.winner_id
        loser_id = match.result.loser_id

        if winner_id and winner_id in self.standings:
            s = self.standings[winner_id]
            s.wins += 1
            s.ships_destroyed += (7 - match.result.loser_ships_remaining)
            s.ships_lost += (7 - match.result.winner_ships_remaining)
            s.total_turns += match.result.turns
            s.total_time_used_ms += match.result.winner_time_used_ms

            # Calculate time bonus based on scoring model
            if self.scoring_model == ScoringModel.WIN_PLUS_TIME:
                seconds_used = match.result.winner_time_used_ms / 1000
                bonus = max(0, int(30 - seconds_used))
                s.time_bonus_points += bonus

        if loser_id and loser_id in self.standings:
            s = self.standings[loser_id]
            s.losses += 1
            s.ships_destroyed += (7 - match.result.winner_ships_remaining)
            s.ships_lost += (7 - match.result.loser_ships_remaining)
            s.total_turns += match.result.turns
            s.total_time_used_ms += match.result.loser_time_used_ms

    def _advance_bracket_winner(self, match: Match):
        """Advance winner to next round in bracket."""
        # Find matches in next round and place winner
        # This is simplified - a full implementation would track bracket structure
        pass

    def is_completed(self) -> bool:
        """Check if tournament is completed."""
        return all(m.state == MatchState.COMPLETED for m in self.matches)

    def complete(self):
        """Mark tournament as completed."""
        self.state = TournamentState.COMPLETED
        self.completed_at = datetime.now()

    def get_leaderboard(self) -> List[Standing]:
        """Get sorted leaderboard."""
        standings = list(self.standings.values())
        if self.scoring_model == ScoringModel.TIME_TIEBREAKER:
            # Same points → lower time wins
            standings.sort(key=lambda s: (-s.points, s.total_time_used_ms, -s.ships_destroyed))
        else:
            standings.sort(key=lambda s: (-s.points, -s.ships_destroyed, s.ships_lost))
        return standings

    def get_winner(self) -> Optional[Participant]:
        """Get tournament winner."""
        if not self.is_completed():
            return None
        leaderboard = self.get_leaderboard()
        if leaderboard:
            winner_id = leaderboard[0].participant_id
            return self.participants.get(winner_id)
        return None

    # =========================================================================
    # Serialization
    # =========================================================================

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "format": self.format.value,
            "best_of": self.best_of,
            "max_participants": self.max_participants,
            "state": self.state.value,
            "participants": [p.to_dict() for p in self.participants.values()],
            "matches": [m.to_dict() for m in self.matches],
            "standings": [s.to_dict() for s in self.get_leaderboard()],
            "current_match": self.current_match.to_dict() if self.current_match else None,
            "current_round": self.current_round,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "scoring_model": self.scoring_model.value,
        }


class TournamentManager:
    """
    Manages multiple tournaments.
    """

    def __init__(self):
        self.tournaments: Dict[str, FleetCommanderTournament] = {}

    def create_tournament(
        self,
        name: str,
        format: TournamentFormat = TournamentFormat.ROUND_ROBIN,
        best_of: int = 1,
        max_participants: int = 8,
        use_small_grid: bool = True,
    ) -> FleetCommanderTournament:
        """Create a new tournament."""
        tournament = FleetCommanderTournament(
            name=name,
            format=format,
            best_of=best_of,
            max_participants=max_participants,
            use_small_grid=use_small_grid,
        )
        self.tournaments[tournament.id] = tournament
        return tournament

    def get_tournament(self, tournament_id: str) -> Optional[FleetCommanderTournament]:
        """Get a tournament by ID."""
        return self.tournaments.get(tournament_id)

    def list_tournaments(self, include_completed: bool = False) -> List[FleetCommanderTournament]:
        """List all tournaments."""
        tournaments = list(self.tournaments.values())
        if not include_completed:
            tournaments = [t for t in tournaments if t.state != TournamentState.COMPLETED]
        return tournaments

    def delete_tournament(self, tournament_id: str) -> bool:
        """Delete a tournament."""
        if tournament_id in self.tournaments:
            del self.tournaments[tournament_id]
            return True
        return False
