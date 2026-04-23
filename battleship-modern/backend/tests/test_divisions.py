"""
Ward 4: Bot Divisions Tests

BDD tests for division-based tournament organization.
Divisions are primarily etiquette — no technical enforcement of LLM usage.
"""
import pytest

from app.fleet_commander.tournament import (
    FleetCommanderTournament, TournamentFormat, TournamentState,
    MatchResult, Division, Participant,
)


class TestDivisionEnum:
    """Test that Division enum exists with expected variants."""

    def test_deterministic(self):
        assert Division.DETERMINISTIC.value == "deterministic"

    def test_open(self):
        assert Division.OPEN.value == "open"

    def test_local_llm(self):
        assert Division.LOCAL_LLM.value == "local_llm"

    def test_tiny_model(self):
        assert Division.TINY_MODEL.value == "tiny_model"


class TestParticipantDivision:
    """Test that participants can declare a division."""

    def test_participant_has_division(self):
        """Given a participant with a division
        When created
        Then division is stored."""
        t = FleetCommanderTournament(name="Test")
        p = t.add_participant(name="Bot1", is_internal_bot=True,
                              internal_bot_type="random",
                              division=Division.DETERMINISTIC)
        assert p.division == Division.DETERMINISTIC

    def test_participant_division_defaults_to_open(self):
        """Given a participant without explicit division
        When created
        Then division defaults to OPEN."""
        t = FleetCommanderTournament(name="Test")
        p = t.add_participant(name="Bot1", is_internal_bot=True,
                              internal_bot_type="random")
        assert p.division == Division.OPEN

    def test_participant_serialization_includes_division(self):
        """Given a participant with division
        When serialized
        Then dict includes division."""
        t = FleetCommanderTournament(name="Test")
        p = t.add_participant(name="Bot1", is_internal_bot=True,
                              internal_bot_type="random",
                              division=Division.TINY_MODEL)
        d = p.to_dict()
        assert d["division"] == "tiny_model"


class TestTournamentDivision:
    """Test tournament-level division configuration."""

    def test_tournament_has_optional_division(self):
        """Given a tournament with a division
        When created
        Then division is stored."""
        t = FleetCommanderTournament(name="Test", division=Division.DETERMINISTIC)
        assert t.division == Division.DETERMINISTIC

    def test_tournament_division_defaults_to_none(self):
        """Given a tournament without division
        When created
        Then division is None (mixed)."""
        t = FleetCommanderTournament(name="Test")
        assert t.division is None

    def test_tournament_serialization_includes_division(self):
        """Given a tournament with division
        When serialized
        Then dict includes division."""
        t = FleetCommanderTournament(name="Test", division=Division.LOCAL_LLM)
        d = t.to_dict()
        assert d["division"] == "local_llm"

    def test_tournament_no_division_serializes_as_none(self):
        """Given a tournament without division
        When serialized
        Then division is null."""
        t = FleetCommanderTournament(name="Test")
        d = t.to_dict()
        assert d["division"] is None


class TestDivisionMatchmaking:
    """Test that matchmaking prioritizes same-division bots."""

    def _make_mixed_tournament(self) -> FleetCommanderTournament:
        """Create a tournament with bots in different divisions."""
        t = FleetCommanderTournament(
            name="Mixed",
            format=TournamentFormat.ROUND_ROBIN,
            max_participants=4,
        )
        t.add_participant(name="DetBot1", is_internal_bot=True,
                          internal_bot_type="random", division=Division.DETERMINISTIC)
        t.add_participant(name="DetBot2", is_internal_bot=True,
                          internal_bot_type="random", division=Division.DETERMINISTIC)
        t.add_participant(name="OpenBot1", is_internal_bot=True,
                          internal_bot_type="random", division=Division.OPEN)
        t.add_participant(name="OpenBot2", is_internal_bot=True,
                          internal_bot_type="random", division=Division.OPEN)
        for p in t.participants.values():
            t.set_participant_ready(p.id, True)
        return t

    def test_round_robin_includes_all_matchups(self):
        """Given a mixed-division round-robin tournament
        When started
        Then all participants play each other (divisions don't exclude)."""
        t = self._make_mixed_tournament()
        t.start()

        # 4 players round-robin = 6 matches
        assert len(t.matches) == 6

    def test_leaderboard_can_filter_by_division(self):
        """Given a tournament with mixed divisions
        When getting leaderboard with division filter
        Then only participants of that division are shown."""
        t = self._make_mixed_tournament()
        t.start()

        # Record some results
        for match in t.matches[:3]:
            result = MatchResult(
                winner_id=match.player1_id, loser_id=match.player2_id,
                turns=50, winner_ships_remaining=3, loser_ships_remaining=0,
            )
            t.record_match_result(match.id, result)

        det_board = t.get_leaderboard(division=Division.DETERMINISTIC)
        for standing in det_board:
            p = t.participants[standing.participant_id]
            assert p.division == Division.DETERMINISTIC

    def test_leaderboard_without_filter_shows_all(self):
        """Given a tournament with mixed divisions
        When getting leaderboard without filter
        Then all participants are shown."""
        t = self._make_mixed_tournament()
        t.start()

        board = t.get_leaderboard()
        assert len(board) == 4
