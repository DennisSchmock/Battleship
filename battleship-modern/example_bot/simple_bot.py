#!/usr/bin/env python3
"""
Simple Fleet Commander Bot Example

This is a minimal bot that connects via WebSocket and plays against baseline bots.
Use this as a starting point for your own bot!

Usage:
    python simple_bot.py [--server URL] [--opponent BOT_TYPE]

Example:
    python simple_bot.py --server ws://localhost:8000 --opponent aggressive
"""

import asyncio
import json
import argparse
import random
from typing import List, Dict, Any, Optional


class SimpleBot:
    """
    A simple bot that demonstrates the WebSocket protocol.

    Strategy:
    - Move ships toward enemies
    - Fire when in range
    - Uses AP system: can move AND fire in same turn
    """

    def __init__(self):
        self.config: Optional[Dict] = None
        self.my_player_id: Optional[int] = None

    def handle_game_start(self, data: Dict) -> None:
        """Called when game starts with configuration."""
        self.config = data.get("config", {})
        print(f"Game started! Grid: {self.config.get('grid_size')}")

    def handle_place_fleet(self, data: Dict) -> Dict:
        """
        Place your fleet in the given zone.
        Returns placement message to send back.
        """
        zone_x_min = data["zone_x_min"]
        zone_x_max = data["zone_x_max"]
        grid_size = self.config.get("grid_size", [32, 32, 16])

        print(f"Placing fleet in zone x={zone_x_min}-{zone_x_max}")

        # Get fleet ships from config (or use default)
        fleet_ships = self.config.get("fleet_ships", [
            "destroyer", "destroyer",
            "cruiser", "support",
            "carrier", "artillery", "minelayer"
        ])

        # Ship sizes for proper spacing
        ship_sizes = {
            "destroyer": 3, "cruiser": 4, "support": 3,
            "carrier": 5, "artillery": 3, "minelayer": 2
        }

        placements = []
        zone_center_x = (zone_x_min + zone_x_max) // 2
        z_center = grid_size[2] // 2

        # Place ships in a grid pattern within the zone
        # All ships face north to extend in positive Y
        y_pos = 2  # Start with some margin

        for i, ship_type in enumerate(fleet_ships):
            ship_size = ship_sizes.get(ship_type, 3)

            # Alternate X positions between zone_center_x and zone_center_x-1
            x_offset = i % 2
            x_pos = zone_x_min + 1 + x_offset

            placement = {
                "ship_type": ship_type,
                "position": [x_pos, y_pos, z_center],
                "direction": "north"
            }
            placements.append(placement)

            # Move Y for every 2 ships (since we alternate X)
            if i % 2 == 1:
                y_pos += 6  # Leave space for largest ship (5) + 1

        return {
            "type": "fleet_placement",
            "placements": placements
        }

    def handle_get_actions(self, data: Dict) -> Dict:
        """
        Decide actions for this turn.
        Returns actions message to send back.
        """
        view = data["view"]
        self.my_player_id = view.get("my_player_id")
        turn = view.get("turn", 0)
        my_ships = view.get("my_ships", [])
        enemies = view.get("visible_enemy_ships", [])

        print(f"\n=== Turn {turn} ===")
        print(f"My ships: {len(my_ships)}, Enemies visible: {len(enemies)}")

        actions = []

        # Collect enemy positions
        enemy_positions = []
        for enemy in enemies:
            for pos in enemy.get("positions", []):
                enemy_positions.append(pos)

        # Process each ship that can act
        for ship in my_ships:
            if not ship.get("can_act", False):
                continue

            ship_actions = self.decide_ship_actions(ship, enemy_positions, view)
            actions.extend(ship_actions)

        print(f"Sending {len(actions)} actions")

        return {
            "type": "actions",
            "actions": actions
        }

    def decide_ship_actions(self, ship: Dict, enemies: List, view: Dict) -> List[Dict]:
        """
        Decide actions for a single ship.
        Can return multiple actions if AP allows!
        """
        actions = []
        ship_id = ship["id"]
        ship_type = ship.get("ship_type", "unknown")
        positions = ship.get("positions", [])

        if not positions:
            return actions

        # Get ship center
        center = positions[len(positions) // 2]

        # Track AP usage
        ap = ship.get("action_points", 0)
        fire_range = ship.get("fire_range", 4)
        movement_remaining = ship.get("movement_remaining", 0)

        # Find closest enemy
        closest_enemy = None
        closest_dist = float('inf')

        for enemy_pos in enemies:
            dist = abs(center[0] - enemy_pos[0]) + abs(center[1] - enemy_pos[1]) + abs(center[2] - enemy_pos[2])
            if dist < closest_dist:
                closest_dist = dist
                closest_enemy = enemy_pos

        # Strategy: If enemy in range, fire first then maybe move
        # If not in range, move toward enemy

        if closest_enemy and closest_dist <= fire_range:
            # FIRE! (costs 1 AP typically)
            fire_cost = 1
            if ap >= fire_cost:
                actions.append({
                    "action_type": "fire",
                    "ship_id": ship_id,
                    "target": closest_enemy
                })
                ap -= fire_cost
                print(f"  {ship_type}: FIRE at {closest_enemy} (dist={closest_dist})")

        # Move toward enemy with remaining AP
        if closest_enemy and ap > 0 and movement_remaining > 0:
            # Calculate direction toward enemy
            dx = 1 if closest_enemy[0] > center[0] else (-1 if closest_enemy[0] < center[0] else 0)
            dy = 1 if closest_enemy[1] > center[1] else (-1 if closest_enemy[1] < center[1] else 0)
            dz = 1 if closest_enemy[2] > center[2] else (-1 if closest_enemy[2] < center[2] else 0)

            # Move up to AP limit or movement limit
            steps = min(ap, movement_remaining)
            path = []

            current = list(center)
            for _ in range(steps):
                # Prioritize x movement, then y, then z
                if dx != 0:
                    current = [current[0] + dx, current[1], current[2]]
                elif dy != 0:
                    current = [current[0], current[1] + dy, current[2]]
                elif dz != 0:
                    current = [current[0], current[1], current[2] + dz]
                else:
                    break
                path.append(list(current))

            if path:
                actions.append({
                    "action_type": "move",
                    "ship_id": ship_id,
                    "path": path
                })
                print(f"  {ship_type}: MOVE {len(path)} steps toward enemy")

        return actions

    def handle_turn_result(self, data: Dict) -> None:
        """Called after each turn with results."""
        result = data.get("result", {})
        actions = result.get("actions_taken", [])

        hits = sum(1 for a in actions if a.get("ships_hit"))
        print(f"Turn result: {len(actions)} actions, {hits} hits")

    def handle_game_end(self, data: Dict) -> None:
        """Called when game ends."""
        won = data.get("won", False)
        reason = data.get("reason", "Unknown")

        if won:
            print(f"\n🎉 VICTORY! {reason}")
        else:
            print(f"\n💀 DEFEAT! {reason}")


async def run_bot(server_url: str, opponent: str):
    """Connect to server and run the bot."""
    import websockets

    # Build connection URL
    ws_url = f"{server_url}/ws/fleet-commander?player1_type=websocket&player2_type={opponent}"

    print(f"Connecting to {ws_url}...")

    bot = SimpleBot()

    async with websockets.connect(ws_url) as websocket:
        print("Connected!")

        while True:
            try:
                # Receive message from server
                message = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                data = json.loads(message)
                msg_type = data.get("type", "")

                # Handle different message types
                if msg_type == "game_start":
                    bot.handle_game_start(data)

                elif msg_type == "place_fleet":
                    response = bot.handle_place_fleet(data)
                    await websocket.send(json.dumps(response))

                elif msg_type == "get_actions":
                    response = bot.handle_get_actions(data)
                    await websocket.send(json.dumps(response))

                elif msg_type == "turn_result":
                    bot.handle_turn_result(data)

                elif msg_type == "game_end":
                    bot.handle_game_end(data)
                    break

                elif msg_type == "error":
                    print(f"ERROR: {data.get('message')}")

            except asyncio.TimeoutError:
                print("Timeout waiting for server message")
                break
            except Exception as e:
                print(f"Error: {e}")
                break

    print("Disconnected")


def main():
    parser = argparse.ArgumentParser(description="Simple Fleet Commander Bot")
    parser.add_argument("--server", default="ws://localhost:8000",
                        help="WebSocket server URL")
    parser.add_argument("--opponent", default="aggressive",
                        choices=["tactical", "aggressive", "defensive", "random"],
                        help="Opponent bot type")

    args = parser.parse_args()

    print("""
╔═══════════════════════════════════════╗
║     Fleet Commander - Simple Bot      ║
╠═══════════════════════════════════════╣
║  A minimal example bot to get started ║
╚═══════════════════════════════════════╝
    """)

    asyncio.run(run_bot(args.server, args.opponent))


if __name__ == "__main__":
    main()
