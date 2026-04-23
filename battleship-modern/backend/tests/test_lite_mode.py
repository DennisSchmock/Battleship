"""
Ward 5: Fleet Commander Lite Tests

BDD tests for a simplified game variant designed for small LLMs.
"""
import pytest

from app.fleet_commander.engine import FleetCommanderGame, GamePhase
from app.fleet_commander.models import (
    GameConfig, ShipType, AbilityType, SHIP_CONFIGS, FleetConfig,
)
from app.fleet_commander.bot_interface import create_game_view
from app.fleet_commander.bots import RandomBot, TacticalBot


class TestLiteConfig:
    """Test GameConfig.lite() factory method."""

    def test_lite_config_exists(self):
        """Given GameConfig
        When calling lite()
        Then a valid config is returned."""
        config = GameConfig.lite()
        assert config is not None

    def test_lite_grid_size(self):
        """Given a Lite config
        When inspecting grid size
        Then it is 16x16x8."""
        config = GameConfig.lite()
        assert config.grid_size == (16, 16, 8)

    def test_lite_has_three_ship_types(self):
        """Given a Lite config
        When inspecting fleet
        Then there are exactly 3 ships: Destroyer, Cruiser, Support."""
        config = GameConfig.lite()
        ships = config.fleet_config.ships
        assert len(ships) == 3
        assert ShipType.DESTROYER in ships
        assert ShipType.CRUISER in ships
        assert ShipType.SUPPORT in ships

    def test_lite_no_storm(self):
        """Given a Lite config
        When inspecting storm settings
        Then storm is effectively disabled (start turn > max turns)."""
        config = GameConfig.lite()
        assert config.storm_start_turn > config.max_turns

    def test_lite_zones_fit_grid(self):
        """Given a Lite config
        When inspecting player zones
        Then zones are within the 16-wide grid."""
        config = GameConfig.lite()
        assert config.player1_zone[0] >= 0
        assert config.player1_zone[1] < 16
        assert config.player2_zone[0] >= 0
        assert config.player2_zone[1] < 16

    def test_lite_has_reasonable_max_turns(self):
        """Given a Lite config
        When inspecting max_turns
        Then it allows a reasonable game length."""
        config = GameConfig.lite()
        assert 50 <= config.max_turns <= 200


class TestLiteShipAbilities:
    """Test that Lite ships only have move and fire (no special abilities)."""

    def test_lite_ships_only_move_and_fire(self):
        """Given a Lite game
        When inspecting ship abilities
        Then each ship only has MOVE-compatible and FIRE abilities (no specials)."""
        config = GameConfig.lite()
        allowed = {AbilityType.FIRE, AbilityType.MOVE, AbilityType.SCAN}

        for ship_type in config.fleet_config.ships:
            ship_config = config.get_ship_config(ship_type)
            for ability in ship_config.abilities:
                assert ability.ability_type in allowed, (
                    f"{ship_type.value} has disallowed ability {ability.ability_type.value}"
                )

    def test_lite_no_burst_fire(self):
        """Given a Lite config
        When checking abilities
        Then no ship has BURST_FIRE."""
        config = GameConfig.lite()
        for ship_type in config.fleet_config.ships:
            ship_config = config.get_ship_config(ship_type)
            ability_types = {a.ability_type for a in ship_config.abilities}
            assert AbilityType.BURST_FIRE not in ability_types

    def test_lite_no_area_bombardment(self):
        """Given a Lite config
        When checking abilities
        Then no ship has AREA_BOMBARDMENT."""
        config = GameConfig.lite()
        for ship_type in config.fleet_config.ships:
            ship_config = config.get_ship_config(ship_type)
            ability_types = {a.ability_type for a in ship_config.abilities}
            assert AbilityType.AREA_BOMBARDMENT not in ability_types


class TestLiteEndToEnd:
    """Test that a Lite game runs correctly end-to-end."""

    def test_lite_game_creates_successfully(self):
        """Given a Lite config with seed
        When creating a game
        Then it initializes without error."""
        config = GameConfig.lite()
        config.seed = 42
        game = FleetCommanderGame(config=config)
        assert game.phase == GamePhase.SETUP

    def test_lite_auto_place_fleet(self):
        """Given a Lite game
        When auto-placing fleets
        Then both players get 3 ships each."""
        config = GameConfig.lite()
        config.seed = 42
        game = FleetCommanderGame(config=config)
        game.auto_place_fleet(0)
        game.auto_place_fleet(1)

        assert len(game.players[0].ships) == 3
        assert len(game.players[1].ships) == 3

    def test_lite_random_bot_can_play(self):
        """Given a Lite game with two RandomBots
        When the game runs to completion
        Then it finishes with a winner or max turns."""
        config = GameConfig.lite()
        config.seed = 42
        game = FleetCommanderGame(config=config)
        game.auto_place_fleet(0)
        game.auto_place_fleet(1)
        game.start_game()

        bot1 = RandomBot()
        bot2 = RandomBot()
        bot1.on_game_start(config)
        bot2.on_game_start(config)
        bots = [bot1, bot2]

        while game.phase == GamePhase.PLAYING and game.turn < config.max_turns:
            bot = bots[game.current_player_idx]
            state = game.get_visible_state(game.current_player_idx)
            view = create_game_view(state)
            actions = bot.get_actions(view, rng=game.rng)
            result = game.execute_turn(actions)
            bot.on_turn_result(result)

        # Game should have ended
        assert game.phase == GamePhase.FINISHED or game.turn >= config.max_turns

    def test_tactical_bot_beats_random_bot(self):
        """Given 20 Lite games: TacticalBot vs RandomBot
        When all games are played
        Then TacticalBot wins more than RandomBot."""
        tactical_wins = 0

        for seed in range(20):
            config = GameConfig.lite()
            config.seed = seed + 100
            game = FleetCommanderGame(config=config)
            game.auto_place_fleet(0)
            game.auto_place_fleet(1)
            game.start_game()

            bot1 = TacticalBot()
            bot2 = RandomBot()
            bot1.on_game_start(config)
            bot2.on_game_start(config)
            bots = [bot1, bot2]

            while game.phase == GamePhase.PLAYING and game.turn < config.max_turns:
                bot = bots[game.current_player_idx]
                state = game.get_visible_state(game.current_player_idx)
                view = create_game_view(state)
                actions = bot.get_actions(view, rng=game.rng)
                result = game.execute_turn(actions)
                bot.on_turn_result(result)

            if game.winner == 0:  # TacticalBot is player 0
                tactical_wins += 1

        assert tactical_wins >= 10, f"TacticalBot only won {tactical_wins}/20"

    def test_lite_no_storm_damage(self):
        """Given a Lite game
        When played for many turns
        Then no storm damage is dealt."""
        config = GameConfig.lite()
        config.seed = 42
        game = FleetCommanderGame(config=config)
        game.auto_place_fleet(0)
        game.auto_place_fleet(1)
        game.start_game()

        bot1 = RandomBot()
        bot2 = RandomBot()
        bot1.on_game_start(config)
        bot2.on_game_start(config)
        bots = [bot1, bot2]

        storm_damage_seen = False
        turns = 0
        while game.phase == GamePhase.PLAYING and turns < 80:
            bot = bots[game.current_player_idx]
            state = game.get_visible_state(game.current_player_idx)
            view = create_game_view(state)
            actions = bot.get_actions(view, rng=game.rng)
            result = game.execute_turn(actions)
            if result.storm_damage_taken:
                storm_damage_seen = True
            bot.on_turn_result(result)
            turns += 1

        assert not storm_damage_seen, "Storm damage should not occur in Lite mode"
