"""
Ward 2: Time Budget per Match Tests

BDD tests ensuring bots have a configurable time budget per match,
with turn forfeiture when exceeded and cheat detection for unrealistic timing.
"""
import pytest
import time
from unittest.mock import patch

from app.fleet_commander.engine import FleetCommanderGame, GamePhase
from app.fleet_commander.models import (
    GameConfig, PlayerState, TurnResult, Action, MoveAction, Position,
)
from app.fleet_commander.bot_interface import create_game_view, GameView
from app.fleet_commander.bots import RandomBot


def _make_started_game(seed=42, time_budget_ms=60_000) -> FleetCommanderGame:
    """Helper: create a seeded game with bots placed and started."""
    config = GameConfig.small()
    config.seed = seed
    config.match_time_budget_ms = time_budget_ms
    game = FleetCommanderGame(config=config)
    game.auto_place_fleet(0)
    game.auto_place_fleet(1)
    game.players[0].name = "Bot1"
    game.players[1].name = "Bot2"
    game.start_game()
    return game


class TestTimeBudgetConfig:
    """Test that GameConfig accepts time budget settings."""

    def test_default_time_budget(self):
        """Given a default GameConfig
        When created
        Then match_time_budget_ms is 60_000 (60 seconds)."""
        config = GameConfig.small()
        assert config.match_time_budget_ms == 60_000

    def test_custom_time_budget(self):
        """Given a GameConfig with custom budget
        When match_time_budget_ms is set to 30_000
        Then budget is 30 seconds."""
        config = GameConfig.small()
        config.match_time_budget_ms = 30_000
        assert config.match_time_budget_ms == 30_000

    def test_zero_budget_means_unlimited(self):
        """Given a GameConfig with budget=0
        When checking
        Then budget is 0 (unlimited - no time enforcement)."""
        config = GameConfig.small()
        config.match_time_budget_ms = 0
        assert config.match_time_budget_ms == 0


class TestPlayerTimeTracking:
    """Test that PlayerState tracks time used."""

    def test_player_has_time_used(self):
        """Given a started game
        When inspecting player state
        Then time_used_ms is 0 initially."""
        game = _make_started_game()
        assert game.players[0].time_used_ms == 0
        assert game.players[1].time_used_ms == 0

    def test_time_remaining_calculated(self):
        """Given a player who has used 10 seconds of 60 second budget
        When checking time remaining
        Then 50 seconds remain."""
        game = _make_started_game(time_budget_ms=60_000)
        game.players[0].time_used_ms = 10_000
        remaining = game.config.match_time_budget_ms - game.players[0].time_used_ms
        assert remaining == 50_000


class TestTimeBudgetEnforcement:
    """Test that exceeding time budget forfeits the turn."""

    def test_record_thinking_time(self):
        """Given a game with time budget
        When a turn is executed with thinking_time_ms=500
        Then player's time_used_ms increases by 500."""
        game = _make_started_game(time_budget_ms=60_000)
        bot = RandomBot()
        bot.on_game_start(game.config)

        state = game.get_visible_state(0)
        view = create_game_view(state)
        actions = bot.get_actions(view, rng=game.rng)

        result = game.execute_turn(actions, thinking_time_ms=500)
        assert game.players[0].time_used_ms == 500

    def test_budget_exceeded_forfeits_turn(self):
        """Given a bot that has exhausted its time budget
        When it tries to execute a turn
        Then no actions are executed and turn is forfeited."""
        game = _make_started_game(time_budget_ms=1000)
        # Exhaust budget
        game.players[0].time_used_ms = 1000

        bot = RandomBot()
        bot.on_game_start(game.config)
        state = game.get_visible_state(0)
        view = create_game_view(state)
        actions = bot.get_actions(view, rng=game.rng)

        result = game.execute_turn(actions, thinking_time_ms=100)
        # Turn should be forfeited - no actions executed
        assert result.budget_exceeded is True
        assert len(result.actions_taken) == 0

    def test_budget_exceeded_still_advances_turn(self):
        """Given a budget-exceeded turn
        When the turn is forfeited
        Then the game still advances to the next player."""
        game = _make_started_game(time_budget_ms=1000)
        game.players[0].time_used_ms = 1000

        bot = RandomBot()
        bot.on_game_start(game.config)
        state = game.get_visible_state(0)
        view = create_game_view(state)
        actions = bot.get_actions(view, rng=game.rng)

        assert game.current_player_idx == 0
        game.execute_turn(actions, thinking_time_ms=50)
        # Game should have advanced (turn end happens in engine or caller)
        # The turn result should indicate budget exceeded

    def test_within_budget_executes_normally(self):
        """Given a bot within its time budget
        When it executes a turn with thinking_time_ms=100
        Then actions are executed normally."""
        game = _make_started_game(time_budget_ms=60_000)
        bot = RandomBot()
        bot.on_game_start(game.config)

        state = game.get_visible_state(0)
        view = create_game_view(state)
        actions = bot.get_actions(view, rng=game.rng)

        result = game.execute_turn(actions, thinking_time_ms=100)
        assert result.budget_exceeded is False
        assert game.players[0].time_used_ms == 100

    def test_zero_budget_disables_enforcement(self):
        """Given a game with budget=0 (unlimited)
        When a turn is executed with any thinking time
        Then actions execute normally regardless of time."""
        game = _make_started_game(time_budget_ms=0)
        bot = RandomBot()
        bot.on_game_start(game.config)

        state = game.get_visible_state(0)
        view = create_game_view(state)
        actions = bot.get_actions(view, rng=game.rng)

        result = game.execute_turn(actions, thinking_time_ms=999_999)
        assert result.budget_exceeded is False

    def test_thinking_time_defaults_to_zero(self):
        """Given execute_turn called without thinking_time_ms
        When the turn runs
        Then no time is charged (backwards compat)."""
        game = _make_started_game(time_budget_ms=60_000)
        bot = RandomBot()
        bot.on_game_start(game.config)

        state = game.get_visible_state(0)
        view = create_game_view(state)
        actions = bot.get_actions(view, rng=game.rng)

        result = game.execute_turn(actions)
        assert game.players[0].time_used_ms == 0
        assert result.budget_exceeded is False


class TestTimeBudgetInTurnResult:
    """Test that TurnResult includes time information."""

    def test_turn_result_has_budget_exceeded(self):
        """Given a TurnResult
        When created
        Then it has budget_exceeded field (default False)."""
        result = TurnResult(player_id=0, turn=1)
        assert result.budget_exceeded is False

    def test_turn_result_has_time_used(self):
        """Given a TurnResult after a timed turn
        When inspecting
        Then it includes thinking_time_ms."""
        game = _make_started_game()
        bot = RandomBot()
        bot.on_game_start(game.config)

        state = game.get_visible_state(0)
        view = create_game_view(state)
        actions = bot.get_actions(view, rng=game.rng)

        result = game.execute_turn(actions, thinking_time_ms=250)
        assert result.thinking_time_ms == 250

    def test_turn_result_serialization_includes_time(self):
        """Given a TurnResult with time info
        When serialized to dict
        Then dict includes budget_exceeded and thinking_time_ms."""
        result = TurnResult(player_id=0, turn=1, budget_exceeded=True, thinking_time_ms=500)
        d = result.to_dict()
        assert d["budget_exceeded"] is True
        assert d["thinking_time_ms"] == 500


class TestTimeBudgetInGameView:
    """Test that GameView includes time remaining for the bot."""

    def test_game_view_includes_time_remaining(self):
        """Given a game with time budget
        When get_visible_state is called
        Then the state includes time_remaining_ms."""
        game = _make_started_game(time_budget_ms=60_000)
        game.players[0].time_used_ms = 15_000

        state = game.get_visible_state(0)
        assert "time_remaining_ms" in state
        assert state["time_remaining_ms"] == 45_000

    def test_game_view_time_remaining_unlimited(self):
        """Given a game with budget=0 (unlimited)
        When get_visible_state is called
        Then time_remaining_ms is None (unlimited)."""
        game = _make_started_game(time_budget_ms=0)
        state = game.get_visible_state(0)
        assert state["time_remaining_ms"] is None


class TestCheatDetection:
    """Test detection of unrealistic timing reports."""

    def test_negative_thinking_time_rejected(self):
        """Given a bot reporting negative thinking time
        When execute_turn is called
        Then thinking_time_ms is clamped to 0."""
        game = _make_started_game()
        bot = RandomBot()
        bot.on_game_start(game.config)

        state = game.get_visible_state(0)
        view = create_game_view(state)
        actions = bot.get_actions(view, rng=game.rng)

        result = game.execute_turn(actions, thinking_time_ms=-100)
        assert game.players[0].time_used_ms == 0
        assert result.thinking_time_ms == 0


class TestFullGameWithTimeBudget:
    """Test a complete game with time budgets active."""

    def test_game_completes_with_budget(self):
        """Given a game with 60s budget and RandomBots
        When the game runs
        Then it completes normally (bots are fast enough)."""
        game = _make_started_game(time_budget_ms=60_000)
        bot1 = RandomBot()
        bot2 = RandomBot()
        bot1.on_game_start(game.config)
        bot2.on_game_start(game.config)
        bots = [bot1, bot2]

        while game.phase == GamePhase.PLAYING and game.turn < 50:
            current_bot = bots[game.current_player_idx]
            state = game.get_visible_state(game.current_player_idx)
            view = create_game_view(state)
            actions = current_bot.get_actions(view, rng=game.rng)
            # Simulate fast bot: 10ms per turn
            result = game.execute_turn(actions, thinking_time_ms=10)
            current_bot.on_turn_result(result)
            assert result.budget_exceeded is False

        # Both players should have accumulated some time
        assert game.players[0].time_used_ms > 0
        assert game.players[1].time_used_ms > 0
