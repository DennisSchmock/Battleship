"""
Ward 3: Scoring with Time as Factor Tests

BDD tests for configurable scoring models including time bonuses.
"""
import pytest

from app.fleet_commander.tournament import (
    FleetCommanderTournament, TournamentFormat, TournamentState,
    MatchResult, Standing, ScoringModel,
)


def _make_tournament(scoring_model=None, **kwargs) -> FleetCommanderTournament:
    """Helper: create a tournament with participants."""
    t = FleetCommanderTournament(
        name="Test",
        format=TournamentFormat.ROUND_ROBIN,
        max_participants=4,
        scoring_model=scoring_model or ScoringModel.WIN_PLUS_TIME,
        **kwargs,
    )
    for i in range(4):
        p = t.add_participant(name=f"Bot{i}", is_internal_bot=True, internal_bot_type="random")
        t.set_participant_ready(p.id, True)
    t.start()
    return t


class TestScoringModelEnum:
    """Test that ScoringModel enum exists with expected variants."""

    def test_win_only(self):
        assert ScoringModel.WIN_ONLY.value == "win_only"

    def test_win_plus_time(self):
        assert ScoringModel.WIN_PLUS_TIME.value == "win_plus_time"

    def test_time_tiebreaker(self):
        assert ScoringModel.TIME_TIEBREAKER.value == "time_tiebreaker"


class TestMatchResultTimeFields:
    """Test that MatchResult includes time fields."""

    def test_match_result_has_time_fields(self):
        """Given a MatchResult
        When created with time fields
        Then winner_time_used_ms and loser_time_used_ms are stored."""
        result = MatchResult(
            winner_id="a", loser_id="b",
            turns=50,
            winner_ships_remaining=3, loser_ships_remaining=0,
            winner_time_used_ms=20_000,
            loser_time_used_ms=35_000,
        )
        assert result.winner_time_used_ms == 20_000
        assert result.loser_time_used_ms == 35_000

    def test_match_result_time_defaults_to_zero(self):
        """Given a MatchResult without time fields
        Then they default to 0 (backwards compat)."""
        result = MatchResult(
            winner_id="a", loser_id="b",
            turns=50,
            winner_ships_remaining=3, loser_ships_remaining=0,
        )
        assert result.winner_time_used_ms == 0
        assert result.loser_time_used_ms == 0

    def test_match_result_serialization_includes_time(self):
        """Given a MatchResult with time
        When serialized to dict
        Then time fields are included."""
        result = MatchResult(
            winner_id="a", loser_id="b",
            turns=50,
            winner_ships_remaining=3, loser_ships_remaining=0,
            winner_time_used_ms=20_000,
            loser_time_used_ms=35_000,
        )
        d = result.to_dict()
        assert d["winner_time_used_ms"] == 20_000
        assert d["loser_time_used_ms"] == 35_000


class TestWinPlusTimeScoring:
    """Test the default WIN_PLUS_TIME scoring model."""

    def test_win_gives_3_points(self):
        """Given a win with WIN_PLUS_TIME scoring
        When the winner used 20 seconds
        Then base points = 3."""
        t = _make_tournament(scoring_model=ScoringModel.WIN_PLUS_TIME)
        match = t.matches[0]
        p1_id = match.player1_id
        p2_id = match.player2_id

        result = MatchResult(
            winner_id=p1_id, loser_id=p2_id,
            turns=50, winner_ships_remaining=3, loser_ships_remaining=0,
            winner_time_used_ms=20_000, loser_time_used_ms=35_000,
        )
        t.record_match_result(match.id, result)

        standing = t.standings[p1_id]
        assert standing.wins == 1
        assert standing.points >= 3

    def test_time_bonus_calculation(self):
        """Given a winner who used 20 seconds (20_000 ms)
        When scoring with WIN_PLUS_TIME (bonus = max(0, 30 - seconds_used))
        Then time bonus = 10 points, total = 3 + 10 = 13."""
        t = _make_tournament(scoring_model=ScoringModel.WIN_PLUS_TIME)
        match = t.matches[0]
        p1_id = match.player1_id

        result = MatchResult(
            winner_id=p1_id, loser_id=match.player2_id,
            turns=50, winner_ships_remaining=3, loser_ships_remaining=0,
            winner_time_used_ms=20_000, loser_time_used_ms=35_000,
        )
        t.record_match_result(match.id, result)

        standing = t.standings[p1_id]
        # 3 (win) + 10 (time bonus: 30 - 20 = 10)
        assert standing.points == 13

    def test_no_time_bonus_when_slow(self):
        """Given a winner who used 45 seconds
        When scoring with WIN_PLUS_TIME
        Then time bonus = max(0, 30 - 45) = 0, total = 3."""
        t = _make_tournament(scoring_model=ScoringModel.WIN_PLUS_TIME)
        match = t.matches[0]
        p1_id = match.player1_id

        result = MatchResult(
            winner_id=p1_id, loser_id=match.player2_id,
            turns=50, winner_ships_remaining=3, loser_ships_remaining=0,
            winner_time_used_ms=45_000, loser_time_used_ms=50_000,
        )
        t.record_match_result(match.id, result)

        standing = t.standings[p1_id]
        assert standing.points == 3

    def test_loser_gets_zero_points(self):
        """Given a loser
        When scored
        Then points = 0 (no win points, no time bonus)."""
        t = _make_tournament(scoring_model=ScoringModel.WIN_PLUS_TIME)
        match = t.matches[0]
        p2_id = match.player2_id

        result = MatchResult(
            winner_id=match.player1_id, loser_id=p2_id,
            turns=50, winner_ships_remaining=3, loser_ships_remaining=0,
            winner_time_used_ms=20_000, loser_time_used_ms=10_000,
        )
        t.record_match_result(match.id, result)

        standing = t.standings[p2_id]
        assert standing.points == 0


class TestWinOnlyScoring:
    """Test WIN_ONLY scoring model."""

    def test_win_only_ignores_time(self):
        """Given WIN_ONLY scoring
        When a fast winner (5 seconds) scores
        Then points = 3 (no time bonus)."""
        t = _make_tournament(scoring_model=ScoringModel.WIN_ONLY)
        match = t.matches[0]
        p1_id = match.player1_id

        result = MatchResult(
            winner_id=p1_id, loser_id=match.player2_id,
            turns=50, winner_ships_remaining=5, loser_ships_remaining=0,
            winner_time_used_ms=5_000, loser_time_used_ms=30_000,
        )
        t.record_match_result(match.id, result)

        standing = t.standings[p1_id]
        assert standing.points == 3


class TestTimeTiebreakerScoring:
    """Test TIME_TIEBREAKER scoring model."""

    def test_tiebreaker_same_wins_faster_wins(self):
        """Given two players with same wins but different total time
        When leaderboard is sorted with TIME_TIEBREAKER
        Then the faster player ranks higher."""
        t = _make_tournament(scoring_model=ScoringModel.TIME_TIEBREAKER)

        # Get two matches involving different pairs
        m1 = t.matches[0]
        m2 = t.matches[1]

        # Both win their first match, but p1 of m1 is faster
        r1 = MatchResult(
            winner_id=m1.player1_id, loser_id=m1.player2_id,
            turns=50, winner_ships_remaining=3, loser_ships_remaining=0,
            winner_time_used_ms=10_000, loser_time_used_ms=30_000,
        )
        t.record_match_result(m1.id, r1)

        r2 = MatchResult(
            winner_id=m2.player1_id, loser_id=m2.player2_id,
            turns=50, winner_ships_remaining=3, loser_ships_remaining=0,
            winner_time_used_ms=25_000, loser_time_used_ms=30_000,
        )
        t.record_match_result(m2.id, r2)

        leaderboard = t.get_leaderboard()
        # Both have 3 points (1 win each), but m1.player1 used less time
        top_two = [s for s in leaderboard if s.wins == 1]
        if len(top_two) >= 2:
            assert top_two[0].total_time_used_ms <= top_two[1].total_time_used_ms


class TestStandingTimeTracking:
    """Test that Standing tracks time used."""

    def test_standing_has_time_fields(self):
        """Given a Standing
        When created
        Then it has total_time_used_ms and time_bonus_points."""
        standing = Standing(participant_id="test")
        assert standing.total_time_used_ms == 0
        assert standing.time_bonus_points == 0

    def test_standing_serialization_includes_time(self):
        """Given a Standing with time data
        When serialized
        Then dict includes time fields."""
        standing = Standing(participant_id="test", wins=1, total_time_used_ms=15_000, time_bonus_points=15)
        d = standing.to_dict()
        assert d["total_time_used_ms"] == 15_000
        assert d["time_bonus_points"] == 15
        assert d["points"] == 3 + 15  # win points + time bonus


class TestTournamentScoringConfig:
    """Test tournament scoring configuration."""

    def test_tournament_default_scoring(self):
        """Given a tournament without explicit scoring model
        When created
        Then default is WIN_PLUS_TIME."""
        t = FleetCommanderTournament(name="Test")
        assert t.scoring_model == ScoringModel.WIN_PLUS_TIME

    def test_tournament_custom_scoring(self):
        """Given a tournament with WIN_ONLY scoring
        When created
        Then scoring model is stored."""
        t = FleetCommanderTournament(name="Test", scoring_model=ScoringModel.WIN_ONLY)
        assert t.scoring_model == ScoringModel.WIN_ONLY

    def test_tournament_serialization_includes_scoring(self):
        """Given a tournament with scoring model
        When serialized
        Then dict includes scoring_model."""
        t = FleetCommanderTournament(name="Test", scoring_model=ScoringModel.WIN_PLUS_TIME)
        d = t.to_dict()
        assert d["scoring_model"] == "win_plus_time"
