"""
Tests for Fleet Commander Tournament System
"""
import pytest
from app.fleet_commander.tournament import (
    FleetCommanderTournament,
    TournamentManager,
    TournamentFormat,
    TournamentState,
    MatchState,
    MatchResult,
    Participant,
)


class TestTournamentCreation:
    """Test tournament creation and configuration."""

    def test_create_tournament(self):
        """Test basic tournament creation."""
        tournament = FleetCommanderTournament(
            name="Test Tournament",
            format=TournamentFormat.ROUND_ROBIN,
            best_of=3,
            max_participants=4,
        )

        assert tournament.name == "Test Tournament"
        assert tournament.format == TournamentFormat.ROUND_ROBIN
        assert tournament.best_of == 3
        assert tournament.max_participants == 4
        assert tournament.state == TournamentState.LOBBY
        assert len(tournament.participants) == 0

    def test_tournament_has_unique_id(self):
        """Test that tournaments have unique IDs."""
        t1 = FleetCommanderTournament(name="T1")
        t2 = FleetCommanderTournament(name="T2")

        assert t1.id != t2.id


class TestParticipantManagement:
    """Test participant registration and management."""

    def test_add_participant(self):
        """Test adding a participant."""
        tournament = FleetCommanderTournament(name="Test", max_participants=4)

        participant = tournament.add_participant(name="Bot1")

        assert participant is not None
        assert participant.name == "Bot1"
        assert participant.id in tournament.participants
        assert participant.id in tournament.standings

    def test_add_internal_bot(self):
        """Test adding an internal bot (e.g., TacticalBot)."""
        tournament = FleetCommanderTournament(name="Test")

        participant = tournament.add_participant(
            name="TacticalBot",
            is_internal_bot=True,
            internal_bot_type="tactical",
        )

        assert participant.is_internal_bot
        assert participant.internal_bot_type == "tactical"
        assert participant.is_ready  # Internal bots are auto-ready

    def test_max_participants_limit(self):
        """Test that participant limit is enforced."""
        tournament = FleetCommanderTournament(name="Test", max_participants=2)

        p1 = tournament.add_participant(name="Bot1")
        p2 = tournament.add_participant(name="Bot2")
        p3 = tournament.add_participant(name="Bot3")

        assert p1 is not None
        assert p2 is not None
        assert p3 is None  # Should fail - at capacity
        assert len(tournament.participants) == 2

    def test_cannot_add_after_start(self):
        """Test that participants cannot join after tournament starts."""
        tournament = FleetCommanderTournament(name="Test", max_participants=4)
        p1 = tournament.add_participant(name="Bot1", is_internal_bot=True)
        p2 = tournament.add_participant(name="Bot2", is_internal_bot=True)

        tournament.start()
        p3 = tournament.add_participant(name="Bot3")

        assert p3 is None
        assert len(tournament.participants) == 2

    def test_remove_participant(self):
        """Test removing a participant."""
        tournament = FleetCommanderTournament(name="Test")
        participant = tournament.add_participant(name="Bot1")

        removed = tournament.remove_participant(participant.id)

        assert removed
        assert participant.id not in tournament.participants

    def test_set_participant_ready(self):
        """Test setting participant ready status."""
        tournament = FleetCommanderTournament(name="Test")
        participant = tournament.add_participant(name="Bot1")

        assert not participant.is_ready

        tournament.set_participant_ready(participant.id, True)

        assert participant.is_ready


class TestTournamentStart:
    """Test tournament start conditions."""

    def test_cannot_start_with_one_participant(self):
        """Test that tournament needs at least 2 participants."""
        tournament = FleetCommanderTournament(name="Test")
        tournament.add_participant(name="Bot1", is_internal_bot=True)

        assert not tournament.can_start()
        assert not tournament.start()

    def test_cannot_start_if_not_all_ready(self):
        """Test that all participants must be ready."""
        tournament = FleetCommanderTournament(name="Test")
        tournament.add_participant(name="Bot1", is_internal_bot=True)
        p2 = tournament.add_participant(name="Bot2")  # Not ready

        assert not tournament.all_participants_ready()
        assert not tournament.can_start()

    def test_can_start_when_ready(self):
        """Test successful tournament start."""
        tournament = FleetCommanderTournament(name="Test")
        tournament.add_participant(name="Bot1", is_internal_bot=True)
        tournament.add_participant(name="Bot2", is_internal_bot=True)

        assert tournament.can_start()
        assert tournament.start()
        assert tournament.state == TournamentState.IN_PROGRESS
        assert tournament.started_at is not None


class TestRoundRobinSchedule:
    """Test round-robin match generation."""

    def test_round_robin_two_players(self):
        """Test round-robin with 2 players."""
        tournament = FleetCommanderTournament(
            name="Test",
            format=TournamentFormat.ROUND_ROBIN,
        )
        tournament.add_participant(name="Bot1", is_internal_bot=True)
        tournament.add_participant(name="Bot2", is_internal_bot=True)
        tournament.start()

        assert len(tournament.matches) == 1

    def test_round_robin_four_players(self):
        """Test round-robin with 4 players (should have 6 matches)."""
        tournament = FleetCommanderTournament(
            name="Test",
            format=TournamentFormat.ROUND_ROBIN,
        )
        for i in range(4):
            tournament.add_participant(name=f"Bot{i}", is_internal_bot=True)
        tournament.start()

        # n*(n-1)/2 = 4*3/2 = 6 matches
        assert len(tournament.matches) == 6

    def test_round_robin_three_players(self):
        """Test round-robin with 3 players (odd number)."""
        tournament = FleetCommanderTournament(
            name="Test",
            format=TournamentFormat.ROUND_ROBIN,
        )
        for i in range(3):
            tournament.add_participant(name=f"Bot{i}", is_internal_bot=True)
        tournament.start()

        # n*(n-1)/2 = 3*2/2 = 3 matches
        assert len(tournament.matches) == 3

    def test_each_player_plays_each_other_once(self):
        """Test that each pair plays exactly once."""
        tournament = FleetCommanderTournament(
            name="Test",
            format=TournamentFormat.ROUND_ROBIN,
        )
        for i in range(4):
            tournament.add_participant(name=f"Bot{i}", is_internal_bot=True)
        tournament.start()

        participant_ids = list(tournament.participants.keys())
        match_pairs = set()

        for match in tournament.matches:
            pair = frozenset([match.player1_id, match.player2_id])
            assert pair not in match_pairs, "Duplicate match found"
            match_pairs.add(pair)

        # Each player should appear in 3 matches
        for pid in participant_ids:
            matches_with_player = sum(
                1 for m in tournament.matches
                if m.player1_id == pid or m.player2_id == pid
            )
            assert matches_with_player == 3


class TestMatchExecution:
    """Test match result recording."""

    def test_record_match_result(self):
        """Test recording a match result."""
        tournament = FleetCommanderTournament(name="Test")
        p1 = tournament.add_participant(name="Bot1", is_internal_bot=True)
        p2 = tournament.add_participant(name="Bot2", is_internal_bot=True)
        tournament.start()

        match = tournament.get_next_match()
        result = MatchResult(
            winner_id=p1.id,
            loser_id=p2.id,
            turns=25,
            winner_ships_remaining=5,
            loser_ships_remaining=0,
        )

        tournament.record_match_result(match.id, result)

        assert match.state == MatchState.COMPLETED
        assert match.result.winner_id == p1.id

    def test_standings_update_after_match(self):
        """Test that standings update correctly."""
        tournament = FleetCommanderTournament(name="Test")
        p1 = tournament.add_participant(name="Bot1", is_internal_bot=True)
        p2 = tournament.add_participant(name="Bot2", is_internal_bot=True)
        tournament.start()

        match = tournament.get_next_match()
        result = MatchResult(
            winner_id=p1.id,
            loser_id=p2.id,
            turns=25,
            winner_ships_remaining=5,
            loser_ships_remaining=0,
        )
        tournament.record_match_result(match.id, result)

        assert tournament.standings[p1.id].wins == 1
        assert tournament.standings[p1.id].losses == 0
        assert tournament.standings[p2.id].wins == 0
        assert tournament.standings[p2.id].losses == 1

    def test_best_of_three_requires_two_wins(self):
        """Test best-of-3 match completion."""
        tournament = FleetCommanderTournament(name="Test", best_of=3)
        p1 = tournament.add_participant(name="Bot1", is_internal_bot=True)
        p2 = tournament.add_participant(name="Bot2", is_internal_bot=True)
        tournament.start()

        match = tournament.get_next_match()

        # First game - p1 wins
        result1 = MatchResult(
            winner_id=p1.id, loser_id=p2.id,
            turns=20, winner_ships_remaining=6, loser_ships_remaining=0
        )
        tournament.record_match_result(match.id, result1)
        assert match.state == MatchState.PENDING  # Not decided yet

        # Second game - p2 wins
        result2 = MatchResult(
            winner_id=p2.id, loser_id=p1.id,
            turns=22, winner_ships_remaining=4, loser_ships_remaining=0
        )
        tournament.record_match_result(match.id, result2)
        assert match.state == MatchState.PENDING  # Still not decided

        # Third game - p1 wins
        result3 = MatchResult(
            winner_id=p1.id, loser_id=p2.id,
            turns=18, winner_ships_remaining=3, loser_ships_remaining=0
        )
        tournament.record_match_result(match.id, result3)
        assert match.state == MatchState.COMPLETED  # Now decided
        assert len(match.games_played) == 3


class TestLeaderboard:
    """Test leaderboard generation."""

    def test_leaderboard_sorted_by_points(self):
        """Test leaderboard sorting."""
        tournament = FleetCommanderTournament(name="Test")
        p1 = tournament.add_participant(name="Bot1", is_internal_bot=True)
        p2 = tournament.add_participant(name="Bot2", is_internal_bot=True)
        p3 = tournament.add_participant(name="Bot3", is_internal_bot=True)
        tournament.start()

        # Manually set standings for testing
        tournament.standings[p1.id].wins = 2
        tournament.standings[p2.id].wins = 1
        tournament.standings[p3.id].wins = 0

        leaderboard = tournament.get_leaderboard()

        assert leaderboard[0].participant_id == p1.id
        assert leaderboard[1].participant_id == p2.id
        assert leaderboard[2].participant_id == p3.id

    def test_get_winner(self):
        """Test getting tournament winner."""
        tournament = FleetCommanderTournament(name="Test")
        p1 = tournament.add_participant(name="Winner", is_internal_bot=True)
        p2 = tournament.add_participant(name="Loser", is_internal_bot=True)
        tournament.start()

        # Complete the match
        match = tournament.get_next_match()
        result = MatchResult(
            winner_id=p1.id, loser_id=p2.id,
            turns=20, winner_ships_remaining=5, loser_ships_remaining=0
        )
        tournament.record_match_result(match.id, result)
        tournament.complete()

        winner = tournament.get_winner()

        assert winner is not None
        assert winner.name == "Winner"


class TestTournamentManager:
    """Test tournament manager."""

    def test_create_and_get_tournament(self):
        """Test creating and retrieving tournaments."""
        manager = TournamentManager()

        tournament = manager.create_tournament(name="Test Cup")

        assert manager.get_tournament(tournament.id) == tournament

    def test_list_tournaments(self):
        """Test listing tournaments."""
        manager = TournamentManager()

        t1 = manager.create_tournament(name="Cup 1")
        t2 = manager.create_tournament(name="Cup 2")

        tournaments = manager.list_tournaments()

        assert len(tournaments) == 2
        assert t1 in tournaments
        assert t2 in tournaments

    def test_list_excludes_completed_by_default(self):
        """Test that completed tournaments are excluded by default."""
        manager = TournamentManager()

        t1 = manager.create_tournament(name="Active")
        t2 = manager.create_tournament(name="Done")
        t2.state = TournamentState.COMPLETED

        active = manager.list_tournaments(include_completed=False)
        all_tournaments = manager.list_tournaments(include_completed=True)

        assert len(active) == 1
        assert len(all_tournaments) == 2

    def test_delete_tournament(self):
        """Test deleting a tournament."""
        manager = TournamentManager()

        tournament = manager.create_tournament(name="To Delete")
        tid = tournament.id

        assert manager.delete_tournament(tid)
        assert manager.get_tournament(tid) is None


class TestSerialization:
    """Test tournament serialization."""

    def test_tournament_to_dict(self):
        """Test tournament serialization."""
        tournament = FleetCommanderTournament(name="Test Cup", best_of=3)
        p1 = tournament.add_participant(name="Bot1", is_internal_bot=True)
        p2 = tournament.add_participant(name="Bot2", is_internal_bot=True)

        data = tournament.to_dict()

        assert data["name"] == "Test Cup"
        assert data["best_of"] == 3
        assert data["state"] == "lobby"
        assert len(data["participants"]) == 2

    def test_participant_to_dict(self):
        """Test participant serialization."""
        participant = Participant(
            id="abc123",
            name="TestBot",
            is_ready=True,
            is_internal_bot=True,
        )

        data = participant.to_dict()

        assert data["id"] == "abc123"
        assert data["name"] == "TestBot"
        assert data["is_ready"]
        assert data["is_internal_bot"]

    def test_match_result_to_dict(self):
        """Test match result serialization."""
        result = MatchResult(
            winner_id="p1",
            loser_id="p2",
            turns=25,
            winner_ships_remaining=5,
            loser_ships_remaining=0,
            replay_id="replay123",
        )

        data = result.to_dict()

        assert data["winner_id"] == "p1"
        assert data["turns"] == 25
        assert data["replay_id"] == "replay123"
