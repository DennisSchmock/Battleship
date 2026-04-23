#!/usr/bin/env python3
"""
LLM Bot Template for Fleet Commander

A reference implementation showing how to build an LLM-powered bot.
Works with any LLM provider (OpenAI, Anthropic, local llama.cpp, etc.)

This is a TEMPLATE — adapt the llm_call function to your provider.

Usage:
    # With a custom LLM call:
    bot = LLMBotTemplate(llm_call=my_llm_function)

    # The llm_call function signature:
    def my_llm_function(prompt: str) -> str:
        # Call your LLM and return the response text
        ...
"""
import json
import re
import random
from typing import List, Dict, Any, Optional, Callable


class LLMBotTemplate:
    """
    A bot that uses an LLM to decide actions.

    Requires a `llm_call` function: (prompt: str) -> str
    that sends a prompt to any LLM and returns the response text.
    """

    def __init__(self, llm_call: Callable[[str], str]):
        self.llm_call = llm_call
        self.config: Optional[Dict] = None

    def decide_actions(self, view: Dict) -> List[Dict]:
        """Main entry point: given a game view, return actions."""
        prompt = self.format_game_state(view)

        try:
            response = self.llm_call(prompt)
            actions = self.parse_llm_response(response)
            if actions:
                return actions
        except Exception:
            pass

        # Fallback: random simple actions
        return self._fallback_actions(view)

    def format_game_state(self, view: Dict) -> str:
        """Format game state as an LLM prompt."""
        time_remaining = view.get("time_remaining_ms")
        low_time = time_remaining is not None and time_remaining < 10_000

        if low_time:
            return self._format_compact(view)
        return self._format_full(view)

    def _format_full(self, view: Dict) -> str:
        """Full prompt with detailed game state."""
        lines = [
            "You are playing Fleet Commander, a 3D space combat game.",
            f"Turn: {view.get('turn', '?')}",
            f"Grid: {view.get('grid_size', '?')}",
            f"Time remaining: {view.get('time_remaining_ms', 'unlimited')}ms",
            "",
            "YOUR SHIPS:",
        ]

        for ship in view.get("my_ships", []):
            if ship.get("hp", 0) <= 0:
                continue
            pos = ship.get("positions", [[0, 0, 0]])[0]
            lines.append(
                f"  {ship.get('ship_type', '?')} (id={ship['id']}) "
                f"at {pos}, HP={ship.get('hp')}/{ship.get('max_hp')}, "
                f"AP={ship.get('action_points', 0)}, "
                f"fire_range={ship.get('fire_range', 0)}, "
                f"can_fire={ship.get('can_fire')}, can_move={ship.get('can_move')}"
            )

        lines.append("")
        lines.append("VISIBLE ENEMIES:")
        enemies = view.get("visible_enemy_ships", [])
        if enemies:
            for enemy in enemies:
                pos = enemy.get("positions", [[0, 0, 0]])[0]
                lines.append(f"  {enemy.get('ship_type', '?')} (id={enemy['id']}) at {pos}")
        else:
            lines.append("  None visible")

        lines.extend([
            "",
            "Respond with JSON: {\"actions\": [{\"type\": \"fire\"|\"move\", \"ship_id\": \"...\", ...}]}",
            "Fire: {\"type\": \"fire\", \"ship_id\": \"ID\", \"target\": [x,y,z]}",
            "Move: {\"type\": \"move\", \"ship_id\": \"ID\", \"path\": [[x,y,z]]}",
            "Only use ships that can_act=True. Stay within grid bounds.",
        ])

        return "\n".join(lines)

    def _format_compact(self, view: Dict) -> str:
        """Compact prompt for low time situations."""
        ships = [s for s in view.get("my_ships", []) if s.get("hp", 0) > 0 and s.get("can_act")]
        enemies = view.get("visible_enemy_ships", [])

        ship_info = ", ".join(
            f"{s['id']}@{s.get('positions',[[0,0,0]])[0]}"
            for s in ships
        )
        enemy_info = ", ".join(
            f"{e['id']}@{e.get('positions',[[0,0,0]])[0]}"
            for e in enemies
        ) or "none"

        return (
            f"Fleet Commander turn {view.get('turn')}. "
            f"Ships: [{ship_info}]. Enemies: [{enemy_info}]. "
            f"LOW TIME. Reply JSON: {{\"actions\": [{{\"type\":\"fire\",\"ship_id\":\"ID\",\"target\":[x,y,z]}}]}}"
        )

    def parse_llm_response(self, response: str) -> List[Dict]:
        """Parse LLM response, handling markdown fences and embedded JSON."""
        # Try direct parse
        parsed = self._try_parse_json(response)
        if parsed is not None:
            return parsed.get("actions", [])

        # Try extracting from markdown fences
        fence_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', response, re.DOTALL)
        if fence_match:
            parsed = self._try_parse_json(fence_match.group(1).strip())
            if parsed is not None:
                return parsed.get("actions", [])

        # Try finding a JSON object in the text by locating {"actions" and matching braces
        idx = response.find('{"actions"')
        if idx == -1:
            idx = response.find('{ "actions"')
        if idx >= 0:
            depth = 0
            for i in range(idx, len(response)):
                if response[i] == '{':
                    depth += 1
                elif response[i] == '}':
                    depth -= 1
                    if depth == 0:
                        parsed = self._try_parse_json(response[idx:i+1])
                        if parsed is not None:
                            return parsed.get("actions", [])
                        break

        return []

    def _try_parse_json(self, text: str) -> Optional[Dict]:
        """Try to parse text as JSON, return None on failure."""
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return None

    def _fallback_actions(self, view: Dict) -> List[Dict]:
        """Generate simple random actions as fallback."""
        actions = []
        for ship in view.get("my_ships", []):
            if not ship.get("can_act") or ship.get("hp", 0) <= 0:
                continue

            enemies = view.get("visible_enemy_ships", [])
            if enemies and ship.get("can_fire"):
                enemy = random.choice(enemies)
                target = enemy.get("positions", [[0, 0, 0]])[0]
                actions.append({
                    "type": "fire",
                    "ship_id": ship["id"],
                    "target": target,
                })
            elif ship.get("can_move"):
                pos = ship.get("positions", [[0, 0, 0]])[0]
                # Move toward center
                grid = view.get("grid_size", [16, 16, 8])
                cx, cy, cz = grid[0] // 2, grid[1] // 2, grid[2] // 2
                dx = 1 if pos[0] < cx else -1 if pos[0] > cx else 0
                dy = 1 if pos[1] < cy else -1 if pos[1] > cy else 0
                new_pos = [pos[0] + dx, pos[1] + dy, pos[2]]
                actions.append({
                    "type": "move",
                    "ship_id": ship["id"],
                    "path": [new_pos],
                })
        return actions
