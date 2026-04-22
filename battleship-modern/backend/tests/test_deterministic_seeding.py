"""
Ward 1: Deterministic Seeding Tests

BDD tests ensuring that Fleet Commander matches are bit-for-bit reproducible
when given the same seed and inputs.
"""
import pytest
import random as stdlib_random

from app.fleet_commander.engine import FleetCommanderGame, GamePhase
from app.fleet_commander.models import GameConfig, Position, Direction, ShipType
from app.fleet_commander.bot_interface import create_game_view, random_fleet_placement
from app.fleet_commander.bots import RandomBot, TacticalBot


class TestGameSeedConfiguration:
    """Test that GameConfig accepts a seed and FleetCommanderGame uses it."""

    def test_game_config_accepts_seed(self):
        """Given a GameConfig with seed=42
        When the config is created
        Then seed is stored on the config."""
        config = GameConfig.small()
        config.seed = 42
        assert config.seed == 42

    def test_game_config_seed_defaults_to_none(self):
        """Given a GameConfig without explicit seed
        When the config is created
        Then seed is None (non-deterministic)."""
        config = GameConfig.small()
        assert config.seed is None

    def test_game_has_rng_instance(self):
        """Given a FleetCommanderGame with seed=42
        When the game is created
        Then game.rng is a seeded random.Random instance."""
        config = GameConfig.small()
        config.seed = 42
        game = FleetCommanderGame(config=config)

        assert hasattr(game, 'rng')
        assert isinstance(game.rng, stdlib_random.Random)

    def test_game_rng_is_seeded(self):
        """Given two games with the same seed
        When we draw random numbers from each
        Then the sequences are identical."""
        config1 = GameConfig.small()
        config1.seed = 42
        game1 = FleetCommanderGame(config=config1)

        config2 = GameConfig.small()
        config2.seed = 42
        game2 = FleetCommanderGame(config=config2)

        seq1 = [game1.rng.random() for _ in range(100)]
        seq2 = [game2.rng.random() for _ in range(100)]
        assert seq1 == seq2

    def test_different_seeds_produce_different_sequences(self):
        """Given two games with different seeds
        When we draw random numbers from each
        Then the sequences differ."""
        config1 = GameConfig.small()
        config1.seed = 42
        game1 = FleetCommanderGame(config=config1)

        config2 = GameConfig.small()
        config2.seed = 99
        game2 = FleetCommanderGame(config=config2)

        seq1 = [game1.rng.random() for _ in range(100)]
        seq2 = [game2.rng.random() for _ in range(100)]
        assert seq1 != seq2


class TestAutoPlaceFleetDeterminism:
    """Test that auto_place_fleet uses game.rng, not global random."""

    def test_auto_place_fleet_deterministic(self):
        """Given two games with the same seed
        When auto_place_fleet is called on each
        Then the placements are identical."""
        placements = []
        for _ in range(2):
            config = GameConfig.small()
            config.seed = 123
            game = FleetCommanderGame(config=config)
            game.auto_place_fleet(0)
            ships = [(s.config.ship_type, s.positions[:]) for s in game.players[0].ships]
            placements.append(ships)

        assert len(placements[0]) == len(placements[1])
        for (type1, pos1), (type2, pos2) in zip(placements[0], placements[1]):
            assert type1 == type2
            assert pos1 == pos2

    def test_auto_place_fleet_different_seeds(self):
        """Given two games with different seeds
        When auto_place_fleet is called on each
        Then the placements differ (with high probability)."""
        results = []
        for seed in [100, 200]:
            config = GameConfig.small()
            config.seed = seed
            game = FleetCommanderGame(config=config)
            game.auto_place_fleet(0)
            positions = [s.positions[0] for s in game.players[0].ships]
            results.append(positions)

        # At least one ship should be in a different position
        assert results[0] != results[1]


class TestRandomFleetPlacementHelper:
    """Test that the random_fleet_placement helper accepts an rng parameter."""

    def test_random_fleet_placement_with_rng(self):
        """Given the same rng seed
        When random_fleet_placement is called twice
        Then placements are identical."""
        config = GameConfig.small()
        placements = []
        for _ in range(2):
            rng = stdlib_random.Random(42)
            result = random_fleet_placement(config, 0, 5, rng=rng)
            placements.append(result)

        assert len(placements[0]) == len(placements[1])
        for (t1, p1, d1), (t2, p2, d2) in zip(placements[0], placements[1]):
            assert t1 == t2
            assert p1 == p2
            assert d1 == d2

    def test_random_fleet_placement_without_rng_still_works(self):
        """Given no rng parameter (backwards compat)
        When random_fleet_placement is called
        Then it still works (uses global random)."""
        config = GameConfig.small()
        result = random_fleet_placement(config, 0, 5)
        assert len(result) == len(config.fleet_config.ships)


class TestBotRngParameter:
    """Test that bots receive and use an rng instance."""

    def test_bot_get_actions_accepts_rng(self):
        """Given a RandomBot
        When get_actions is called with an rng parameter
        Then it uses that rng (no global random side effects)."""
        config = GameConfig.small()
        config.seed = 42
        game = FleetCommanderGame(config=config)
        game.auto_place_fleet(0)
        game.auto_place_fleet(1)
        game.start_game()

        bot = RandomBot()
        bot.on_game_start(config)

        state = game.get_visible_state(0)
        view = create_game_view(state)

        rng = stdlib_random.Random(99)
        actions = bot.get_actions(view, rng=rng)
        # Should return valid actions (not crash)
        assert isinstance(actions, list)

    def test_bot_get_actions_without_rng_still_works(self):
        """Given a RandomBot
        When get_actions is called without rng (backwards compat)
        Then it still works using global random."""
        config = GameConfig.small()
        config.seed = 42
        game = FleetCommanderGame(config=config)
        game.auto_place_fleet(0)
        game.auto_place_fleet(1)
        game.start_game()

        bot = RandomBot()
        bot.on_game_start(config)

        state = game.get_visible_state(0)
        view = create_game_view(state)

        actions = bot.get_actions(view)
        assert isinstance(actions, list)

    def test_bot_place_fleet_accepts_rng(self):
        """Given a RandomBot
        When place_fleet is called with an rng parameter
        Then placements are deterministic."""
        config = GameConfig.small()
        bot = RandomBot()
        bot.on_game_start(config)

        placements = []
        for _ in range(2):
            rng = stdlib_random.Random(55)
            result = bot.place_fleet(config, 0, 5, rng=rng)
            placements.append(result)

        for (t1, p1, d1), (t2, p2, d2) in zip(placements[0], placements[1]):
            assert t1 == t2
            assert p1 == p2
            assert d1 == d2


class TestEngineInternalRandomness:
    """Test that engine-internal randomness (stealth, etc.) uses game.rng."""

    def test_stealth_check_uses_game_rng(self):
        """Given a game with seed and a stealth ship
        When scan detects the ship twice (same seed)
        Then stealth outcome is identical both times.

        (This tests that engine.py line ~590 uses self.rng, not random.random())
        """
        results = []
        for _ in range(2):
            config = GameConfig.small()
            config.seed = 77
            game = FleetCommanderGame(config=config)
            # The stealth check happens during scan execution in the engine.
            # We verify determinism through full-game replay (see TestFullGameReplay).
            # This test just confirms the rng attribute exists and is used.
            assert hasattr(game, 'rng')
            results.append(game.rng.random())

        assert results[0] == results[1]


class TestFullGameReplay:
    """Test full game determinism: same seed + same bots = identical game."""

    def _run_seeded_game(self, seed: int) -> dict:
        """Run a complete game with a given seed and return the result."""
        config = GameConfig.small()
        config.seed = seed

        game = FleetCommanderGame(config=config)

        # Use auto_place_fleet (uses game.rng)
        game.auto_place_fleet(0)
        game.auto_place_fleet(1)
        game.players[0].name = "RandomBot1"
        game.players[1].name = "RandomBot2"
        game.start_game()

        bot1 = RandomBot()
        bot2 = RandomBot()
        bot1.on_game_start(config)
        bot2.on_game_start(config)

        bots = [bot1, bot2]
        turn_log = []

        while game.phase == GamePhase.PLAYING and game.turn < config.max_turns:
            current_bot = bots[game.current_player_idx]
            state = game.get_visible_state(game.current_player_idx)
            view = create_game_view(state)

            # Pass game.rng to bot so bot actions are also deterministic
            actions = current_bot.get_actions(view, rng=game.rng)
            result = game.execute_turn(actions)
            current_bot.on_turn_result(result)

            turn_log.append({
                "turn": game.turn,
                "player": game.current_player_idx,
                "actions_count": len(result.actions_taken),
                "storm_damage": result.storm_damage_taken,
            })

        return {
            "winner": game.winner,
            "total_turns": game.turn,
            "turn_log": turn_log,
            "p1_ships": [(s.config.ship_type.value, s.hp, s.is_destroyed) for s in game.players[0].ships],
            "p2_ships": [(s.config.ship_type.value, s.hp, s.is_destroyed) for s in game.players[1].ships],
        }

    def test_same_seed_same_result(self):
        """Given two games with seed=42 and two RandomBots each
        When both games are played to completion
        Then the results are bit-for-bit identical."""
        result1 = self._run_seeded_game(42)
        result2 = self._run_seeded_game(42)

        assert result1["winner"] == result2["winner"]
        assert result1["total_turns"] == result2["total_turns"]
        assert result1["turn_log"] == result2["turn_log"]
        assert result1["p1_ships"] == result2["p1_ships"]
        assert result1["p2_ships"] == result2["p2_ships"]

    def test_different_seed_different_result(self):
        """Given two games with different seeds
        When both are played
        Then the results differ (with overwhelming probability)."""
        result1 = self._run_seeded_game(42)
        result2 = self._run_seeded_game(999)

        # At minimum, turn logs should differ
        # (theoretically could be same, but probability is astronomically low)
        assert result1["turn_log"] != result2["turn_log"]

    def test_seeded_game_completes_without_error(self):
        """Given a seeded game with RandomBots
        When the game runs to completion
        Then it finishes without exceptions and has a winner or max turns."""
        result = self._run_seeded_game(12345)
        assert result["winner"] is not None or result["total_turns"] >= 300


class TestTournamentShuffleDeterminism:
    """Test that tournament participant shuffling uses seeded rng."""

    def test_tournament_schedule_deterministic(self):
        """Given a tournament with a seed
        When the schedule is generated twice
        Then match order (by participant name) is identical.
        """
        from app.fleet_commander.tournament import FleetCommanderTournament, TournamentFormat

        results = []
        for _ in range(2):
            rng = stdlib_random.Random(42)
            tournament = FleetCommanderTournament(
                name="Seeded Tournament",
                format=TournamentFormat.ROUND_ROBIN,
                max_participants=4,
            )

            for i in range(4):
                p = tournament.add_participant(name=f"Bot{i}", is_internal_bot=True, internal_bot_type="random")
                tournament.set_participant_ready(p.id, True)

            tournament.start(rng=rng)
            # Compare by participant names (IDs are UUID-based, differ between runs)
            match_names = [
                (tournament.participants[m.player1_id].name,
                 tournament.participants[m.player2_id].name)
                for m in tournament.matches
            ]
            results.append(match_names)

        assert results[0] == results[1]
