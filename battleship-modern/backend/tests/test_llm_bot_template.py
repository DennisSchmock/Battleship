"""
Ward 6: LLM Bot Reference Wrapper Tests

BDD tests for the LLM bot template that demonstrates how to build
an LLM-powered bot for Fleet Commander.
"""
import pytest
import json
import sys
import os

# Add example_bot to path so we can import from it
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'example_bot'))


class TestTemplateImport:
    """Test that the template can be imported without errors."""

    def test_imports_without_error(self):
        """Given llm_bot_template.py
        When imported
        Then no ImportError or SyntaxError occurs."""
        import llm_bot_template
        assert hasattr(llm_bot_template, 'LLMBotTemplate')

    def test_no_hard_dependencies(self):
        """Given llm_bot_template.py
        When imported without openai/anthropic installed
        Then it still imports (LLM providers are optional)."""
        import llm_bot_template
        # Should have the class available regardless of LLM SDKs
        bot = llm_bot_template.LLMBotTemplate(llm_call=lambda prompt: '{"actions": []}')
        assert bot is not None


class TestPromptFormatting:
    """Test game state to prompt conversion."""

    def test_format_game_state_as_prompt(self):
        """Given a game view dict
        When formatted as prompt
        Then it contains ship info and enemy info."""
        from llm_bot_template import LLMBotTemplate

        bot = LLMBotTemplate(llm_call=lambda p: '{"actions": []}')

        view = {
            "turn": 5,
            "my_player_id": 0,
            "grid_size": [16, 16, 8],
            "my_ships": [
                {"id": "s1", "ship_type": "destroyer", "hp": 4, "max_hp": 4,
                 "positions": [[2, 3, 4]], "can_act": True, "can_fire": True,
                 "can_move": True, "action_points": 3, "fire_range": 4},
            ],
            "visible_enemy_ships": [
                {"id": "e1", "positions": [[10, 5, 3]], "ship_type": "cruiser"},
            ],
            "time_remaining_ms": 45000,
        }

        prompt = bot.format_game_state(view)
        assert "turn" in prompt.lower() or "Turn" in prompt
        assert "destroyer" in prompt.lower()
        assert "cruiser" in prompt.lower()

    def test_prompt_shorter_with_low_time(self):
        """Given a view with low time remaining (< 10s)
        When formatted as prompt
        Then prompt is shorter than with full time."""
        from llm_bot_template import LLMBotTemplate

        bot = LLMBotTemplate(llm_call=lambda p: '{"actions": []}')

        view_full = {
            "turn": 5, "my_player_id": 0, "grid_size": [16, 16, 8],
            "my_ships": [
                {"id": "s1", "ship_type": "destroyer", "hp": 4, "max_hp": 4,
                 "positions": [[2, 3, 4]], "can_act": True, "can_fire": True,
                 "can_move": True, "action_points": 3, "fire_range": 4},
            ],
            "visible_enemy_ships": [
                {"id": "e1", "positions": [[10, 5, 3]], "ship_type": "cruiser"},
            ],
            "time_remaining_ms": 50000,
        }

        view_low = {**view_full, "time_remaining_ms": 5000}

        prompt_full = bot.format_game_state(view_full)
        prompt_low = bot.format_game_state(view_low)

        assert len(prompt_low) < len(prompt_full)


class TestJSONParsing:
    """Test JSON parsing with retry and fallback."""

    def test_valid_json_parsed(self):
        """Given an LLM that returns valid JSON actions
        When parsing the response
        Then actions are extracted correctly."""
        from llm_bot_template import LLMBotTemplate

        response = json.dumps({
            "actions": [
                {"type": "fire", "ship_id": "s1", "target": [10, 5, 3]},
                {"type": "move", "ship_id": "s2", "path": [[3, 4, 5]]},
            ]
        })

        bot = LLMBotTemplate(llm_call=lambda p: response)
        actions = bot.parse_llm_response(response)
        assert len(actions) == 2
        assert actions[0]["type"] == "fire"

    def test_invalid_json_returns_empty(self):
        """Given an LLM that returns invalid JSON
        When parsing the response
        Then an empty list is returned (fallback)."""
        from llm_bot_template import LLMBotTemplate

        bot = LLMBotTemplate(llm_call=lambda p: "not valid json at all")
        actions = bot.parse_llm_response("not valid json at all")
        assert actions == []

    def test_json_with_markdown_fences(self):
        """Given an LLM response wrapped in ```json fences
        When parsing
        Then the JSON is extracted and parsed."""
        from llm_bot_template import LLMBotTemplate

        response = '```json\n{"actions": [{"type": "fire", "ship_id": "s1", "target": [1,2,3]}]}\n```'
        bot = LLMBotTemplate(llm_call=lambda p: response)
        actions = bot.parse_llm_response(response)
        assert len(actions) == 1

    def test_json_extraction_from_text(self):
        """Given an LLM response with JSON embedded in text
        When parsing
        Then the JSON object is extracted."""
        from llm_bot_template import LLMBotTemplate

        response = 'Sure! Here is my move:\n{"actions": [{"type": "move", "ship_id": "s1", "path": [[5,5,5]]}]}\nHope that works!'
        bot = LLMBotTemplate(llm_call=lambda p: response)
        actions = bot.parse_llm_response(response)
        assert len(actions) == 1


class TestFallbackBehavior:
    """Test fallback when LLM fails."""

    def test_llm_exception_falls_back(self):
        """Given an LLM that raises an exception
        When get_actions is called
        Then fallback random actions are returned (not crash)."""
        from llm_bot_template import LLMBotTemplate

        def failing_llm(prompt):
            raise RuntimeError("API error")

        bot = LLMBotTemplate(llm_call=failing_llm)

        view = {
            "turn": 5, "my_player_id": 0, "grid_size": [16, 16, 8],
            "my_ships": [
                {"id": "s1", "ship_type": "destroyer", "hp": 4, "max_hp": 4,
                 "positions": [[2, 3, 4]], "can_act": True, "can_fire": True,
                 "can_move": True, "action_points": 3, "fire_range": 4},
            ],
            "visible_enemy_ships": [],
            "time_remaining_ms": 50000,
        }

        actions = bot.decide_actions(view)
        assert isinstance(actions, list)

    def test_llm_returns_garbage_falls_back(self):
        """Given an LLM that returns non-JSON garbage
        When get_actions is called
        Then fallback actions are returned."""
        from llm_bot_template import LLMBotTemplate

        bot = LLMBotTemplate(llm_call=lambda p: "I'm not sure what to do here")

        view = {
            "turn": 5, "my_player_id": 0, "grid_size": [16, 16, 8],
            "my_ships": [
                {"id": "s1", "ship_type": "destroyer", "hp": 4, "max_hp": 4,
                 "positions": [[2, 3, 4]], "can_act": True, "can_fire": True,
                 "can_move": True, "action_points": 3, "fire_range": 4},
            ],
            "visible_enemy_ships": [],
            "time_remaining_ms": 50000,
        }

        actions = bot.decide_actions(view)
        assert isinstance(actions, list)
